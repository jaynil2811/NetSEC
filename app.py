import ipaddress
import json
import os
import platform
import queue
import re
import socket
import ssl
import subprocess
import xml.etree.ElementTree as ET
import threading
import time
import uuid
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    import whois
except ImportError:
    pass
from stem import Signal
from stem.control import Controller

from datetime import datetime
from playwright.sync_api import sync_playwright

import requests
import shutil
from flask import Flask, Response, jsonify, render_template, request, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
import dns.resolver
import shodan

app = Flask(__name__, static_folder="static", template_folder="templates")
limiter = Limiter(get_remote_address, app=app, default_limits=["120 per minute"])

JOB_STORE = {}
JOB_LOCK = threading.Lock()
OSINT_CONFIG = {
    "geo_provider": "ipapi",
    "geo_token": "",
    "abuseipdb_token": "ENTER_YOUR_API_KEY",
    "vt_token": "ENTER_YOUR_API_KEY",
    "shodan_token": "ENTER_YOUR_API_KEY",
    "censys_token": "ENTER_YOUR_API_KEY",
    "ipinfo_token": "ENTER_YOUR_API_KEY",
    "otx_token": "ENTER_YOUR_API_KEY",
}
LATEST_IP_SCAN = []
LATEST_NMAP = {}
LATEST_LOCK = threading.Lock()

COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 139, 143, 443, 445, 3389, 8080, 8443]
DEFAULT_ADV_PORTS = COMMON_PORTS + [135, 161, 389, 636, 3306, 5432, 6379, 27017, 5900]
PORT_RISK = {
    21: ("FTP", "medium"),
    22: ("SSH", "low"),
    23: ("Telnet", "high"),
    25: ("SMTP", "low"),
    53: ("DNS", "low"),
    80: ("HTTP", "low"),
    110: ("POP3", "medium"),
    139: ("NetBIOS", "medium"),
    143: ("IMAP", "medium"),
    443: ("HTTPS", "low"),
    445: ("SMB", "high"),
    3389: ("RDP", "high"),
    8080: ("HTTP-ALT", "medium"),
    8443: ("HTTPS-ALT", "medium"),
}

VULN_HINTS = {
    21: ["Weak FTP auth exposure"],
    23: ["Unencrypted Telnet access"],
    445: ["SMB exposure risk"],
    3389: ["RDP brute force risk"],
    8080: ["Web app exposure"],
}

SERVICE_MAP = {
    21: "ftp",
    22: "ssh",
    23: "telnet",
    25: "smtp",
    53: "dns",
    80: "http",
    110: "pop3",
    139: "netbios-ssn",
    143: "imap",
    443: "https",
    445: "smb",
    3389: "rdp",
    8080: "http",
    8443: "https",
}


def new_job(job_type):
    job_id = str(uuid.uuid4())
    data = {
        "id": job_id,
        "type": job_type,
        "created_at": time.time(),
        "queue": queue.Queue(),
        "done": False,
        "result": None,
    }
    with JOB_LOCK:
        JOB_STORE[job_id] = data
    return data


def push_event(job, event, payload):
    job["queue"].put({"event": event, "payload": payload})


def finish_job(job, result):
    job["result"] = result
    job["done"] = True
    push_event(job, "done", result)


def parse_ip_range(raw, expand_single=True):
    raw = raw.strip()
    if not raw:
        raise ValueError("IP range required")
    if "-" in raw:
        start, end = [part.strip() for part in raw.split("-", 1)]
        start_ip = ipaddress.ip_address(start)
        end_ip = ipaddress.ip_address(end)
        if start_ip.version != end_ip.version:
            raise ValueError("IP versions do not match")
        if int(end_ip) < int(start_ip):
            raise ValueError("Invalid IP range")
        targets = []
        current = int(start_ip)
        end_val = int(end_ip)
        while current <= end_val:
            targets.append(str(ipaddress.ip_address(current)))
            current += 1
        return targets
    if "/" in raw:
        network = ipaddress.ip_network(raw, strict=False)
        return [str(ip) for ip in network.hosts()]
    ip_obj = ipaddress.ip_address(raw)
    if isinstance(ip_obj, ipaddress.IPv4Address) and expand_single:
        octets = raw.split(".")
        end_ip = ipaddress.ip_address(f"{octets[0]}.{octets[1]}.{octets[2]}.255")
        targets = []
        current = int(ip_obj)
        end_val = int(end_ip)
        while current <= end_val:
            targets.append(str(ipaddress.ip_address(current)))
            current += 1
        return targets
    return [raw]


def clamp_targets(targets, limit=2048):
    if len(targets) > limit:
        return targets[:limit]
    return targets


def ping_host(ip):
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", "1", "-w", "500", ip] # Increased timeout to 500ms
    else:
        cmd = ["ping", "-c", "1", "-W", "1", ip]
    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = int((time.time() - start) * 1000)
    output = result.stdout + result.stderr
    alive = result.returncode == 0
    match = re.search(r"time[=<]\s*(\d+)\s*ms", output)
    if match:
        elapsed = int(match.group(1))
    ttl_match = re.search(r"ttl[=\s](\d+)", output, re.IGNORECASE)
    ttl = int(ttl_match.group(1)) if ttl_match else None
    return alive, elapsed, ttl


def tcp_probe(ip, ports, timeout=0.5): # Increased default timeout to 0.5s
    open_ports = []
    
    def scan_single(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            try:
                start = time.time()
                result = sock.connect_ex((ip, port))
                if result == 0:
                    return {"port": port, "latency_ms": int((time.time() - start) * 1000)}
            except OSError:
                pass
        return None

    with ThreadPoolExecutor(max_workers=min(100, len(ports))) as executor:
        futures = [executor.submit(scan_single, port) for port in ports]
        for future in as_completed(futures):
            res = future.result()
            if res:
                open_ports.append(res)
                
    return sorted(open_ports, key=lambda x: x["port"])


def resolve_hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return None

def dns_lookup(domain):
    records = {}
    try:
        # Check if input is IP and do reverse lookup
        ip_obj = ipaddress.ip_address(domain)
        is_ip = True
        try:
            # Try multiple reverse DNS lookups
            names = []
            try:
                name, alias, addresslist = socket.gethostbyaddr(domain)
                names.append(name)
            except Exception:
                pass
            
            # Use dns.resolver for PTR specifically
            try:
                reversed_ip = ipaddress.ip_address(domain).reverse_pointer
                answers = dns.resolver.resolve(reversed_ip, "PTR")
                for rdata in answers:
                    names.append(str(rdata).rstrip('.'))
            except Exception:
                pass
            
            if names:
                records["Reverse DNS"] = sorted(list(set(names)))
                domain = names[0] # Use the first resolved name for further lookups
            else:
                records["Reverse DNS"] = ["No PTR record found"]
                if is_ip:
                    return records
        except Exception:
            records["Reverse DNS"] = ["Lookup failed"]
            if is_ip:
                return records
    except ValueError:
        is_ip = False

    # Forward lookups for domain or resolved hostname
    for record_type in ["A", "AAAA", "MX", "TXT", "NS", "SOA", "CNAME"]:
        try:
            resolver = dns.resolver.Resolver()
            resolver.timeout = 2
            resolver.lifetime = 2
            answers = resolver.resolve(domain, record_type)
            records[record_type] = sorted([str(rdata).rstrip('.') for rdata in answers])
        except Exception:
            records[record_type] = []
    return records


def lookup_mac(ip):
    system = platform.system().lower()
    if system == "windows":
        cmd = ["arp", "-a", ip]
    else:
        cmd = ["arp", "-n", ip]
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout
    match = re.search(r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}", output)
    return match.group(0) if match else None


def compute_risk_summary(hosts):
    score = 0
    vuln_hits = 0
    for host in hosts:
        for port in host.get("open_ports", []):
            risk = PORT_RISK.get(port["port"], (None, "low"))[1]
            score += {"low": 2, "medium": 6, "high": 10}.get(risk, 2)
            if port["port"] in VULN_HINTS:
                vuln_hits += len(VULN_HINTS[port["port"]])
    score = min(100, score)
    level = "low"
    if score >= 70:
        level = "critical"
    elif score >= 45:
        level = "high"
    elif score >= 20:
        level = "medium"
    return {"score": score, "level": level, "vulnerabilities": vuln_hits}


def guess_os_from_ttl(ttl):
    if ttl is None:
        return None
    if ttl <= 64:
        return "linux/unix"
    if ttl <= 128:
        return "windows"
    return "network-device"


def refine_os_guess(ttl, open_ports):
    base = guess_os_from_ttl(ttl)
    ports = {p["port"] for p in open_ports}
    if 445 in ports or 3389 in ports:
        return "windows"
    if 22 in ports and 445 not in ports:
        return base or "linux/unix"
    return base


def host_discovery_worker(job, targets, ports, fetchers, alive_method):
    total = len(targets)
    results = []
    push_event(job, "log", "Initializing IP scan sweep")
    for index, ip in enumerate(targets):
        if alive_method == "tcp":
            probe_ports = ports[:1] if ports else [80]
            open_ports = tcp_probe(ip, probe_ports)
            alive = bool(open_ports)
            latency = open_ports[0]["latency_ms"] if open_ports else None
            ttl = None
        else:
            alive, latency, ttl = ping_host(ip)
            open_ports = []
        hostname = resolve_hostname(ip) if alive else None
        if "ports" in fetchers and alive:
            open_ports = tcp_probe(ip, ports)
        mac = lookup_mac(ip) if alive else None
        status = "up" if alive else "down"
        host = {
            "ip": ip,
            "status": status,
            "latency_ms": latency if alive else None if "latency" in fetchers else None,
            "hostname": hostname if "hostname" in fetchers else None,
            "open_ports": open_ports if "ports" in fetchers else [],
            "mac": mac if "mac" in fetchers else None,
            "ttl": ttl if "ttl" in fetchers else None,
        }
        results.append(host)
        progress = int(((index + 1) / total) * 100)
        push_event(job, "progress", {"progress": progress, "current_ip": ip})
        push_event(job, "log", f"Scanned {ip} status={status}")
    risk = compute_risk_summary(results)
    with LATEST_LOCK:
        global LATEST_IP_SCAN
        LATEST_IP_SCAN = results
    finish_job(job, {"hosts": results, "risk": risk})


def validate_ports(raw, max_ports=1024, default_ports=None):
    if not raw:
        return default_ports or COMMON_PORTS
    if not re.fullmatch(r"[0-9,\-]+", raw):
        raise ValueError("Invalid port format")
    ports = set()
    for part in raw.split(","):
        if "-" in part:
            start, end = part.split("-", 1)
            start = int(start)
            end = int(end)
            for p in range(start, end + 1):
                if 1 <= p <= 65535:
                    ports.add(p)
        else:
            p = int(part)
            if 1 <= p <= 65535:
                ports.add(p)
    ports_list = sorted(ports)
    if len(ports_list) > max_ports:
        return ports_list[:max_ports]
    return ports_list


def validate_target(target):
    target = target.strip()
    if not target:
        raise ValueError("Target required")
    if "-" in target or "/" in target:
        parse_ip_range(target, expand_single=False)
        return target
    ipaddress.ip_address(target)
    return target


def parse_target_list(target):
    target = target.strip()
    if "-" in target or "/" in target:
        return parse_ip_range(target, expand_single=False)
    ipaddress.ip_address(target)
    return [target]


def socket_connect(host, port, timeout):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    return sock


def grab_banner(host, port, timeout=1.0, use_ssl=False, payload=None):
    try:
        sock = socket_connect(host, port, timeout)
        if use_ssl:
            context = ssl.create_default_context()
            sock = context.wrap_socket(sock, server_hostname=host)
        sock.connect((host, port))
        if payload:
            sock.sendall(payload)
        sock.settimeout(timeout)
        data = sock.recv(4096)
        sock.close()
        return data.decode(errors="ignore").strip()
    except Exception:
        return None


def detect_service_banner(host, port):
    if port in (80, 8080):
        banner = grab_banner(host, port, payload=b"HEAD / HTTP/1.0\r\n\r\n")
        server = None
        if banner:
            match = re.search(r"Server:\s*(.+)", banner)
            server = match.group(1).strip() if match else None
        return "http", server, None
    if port in (443, 8443):
        banner = grab_banner(host, port, use_ssl=True, payload=b"HEAD / HTTP/1.0\r\n\r\n")
        server = None
        if banner:
            match = re.search(r"Server:\s*(.+)", banner)
            server = match.group(1).strip() if match else None
        return "https", server, None
    if port == 22:
        banner = grab_banner(host, port)
        return "ssh", banner, None
    if port == 21:
        banner = grab_banner(host, port)
        return "ftp", banner, None
    if port == 25:
        banner = grab_banner(host, port)
        return "smtp", banner, None
    if port == 110:
        banner = grab_banner(host, port)
        return "pop3", banner, None
    if port == 143:
        banner = grab_banner(host, port)
        return "imap", banner, None
    return SERVICE_MAP.get(port), None, None


def scan_tcp_port(host, port, timeout, service_detection):
    state = "filtered"
    service = None
    product = None
    version = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        if result == 0:
            state = "open"
        elif result in (10061, 111):
            state = "closed"
        elif result in (10060, 110, 113, 10065, 101):
            state = "filtered"
        else:
            state = "filtered"
        sock.close()
    except OSError:
        state = "filtered"
    if state == "open":
        service = SERVICE_MAP.get(port)
        if service_detection:
            service, product, version = detect_service_banner(host, port)
    return {
        "port": port,
        "protocol": "tcp",
        "state": state,
        "service": service,
        "product": product,
        "version": version,
    }


def scan_udp_port(host, port, timeout):
    state = "open|filtered"
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.sendto(b"", (host, port))
        try:
            data, _ = sock.recvfrom(1024)
            if data:
                state = "open"
        except socket.timeout:
            state = "open|filtered"
        sock.close()
    except OSError:
        state = "closed"
    return {
        "port": port,
        "protocol": "udp",
        "state": state,
        "service": SERVICE_MAP.get(port),
        "product": None,
        "version": None,
    }


def extract_http_title(text):
    match = re.search(r"<title>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    return None


def extract_http_allow(text):
    match = re.search(r"^Allow:\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
    if match:
        return [item.strip().upper() for item in match.group(1).split(",") if item.strip()]
    return []


def run_script_checks(host, port_info, scripts):
    findings = []
    service = port_info.get("service")
    if ("default" in scripts or "http-title" in scripts) and service in ("http", "https"):
        banner = grab_banner(
            host,
            port_info["port"],
            use_ssl=service == "https",
            payload=b"GET / HTTP/1.0\r\nHost: " + host.encode() + b"\r\n\r\n",
        )
        if banner:
            title = extract_http_title(banner)
            if title:
                findings.append({"name": "http-title", "output": title})
        methods = grab_banner(
            host,
            port_info["port"],
            use_ssl=service == "https",
            payload=b"OPTIONS / HTTP/1.0\r\nHost: " + host.encode() + b"\r\n\r\n",
        )
        if methods:
            allow = extract_http_allow(methods)
            if allow:
                risky = [method for method in allow if method in {"TRACE", "PUT", "DELETE", "TRACK"}]
                output = f"allow={','.join(allow)}"
                if risky:
                    output = f"{output}; risky={','.join(risky)}"
                findings.append({"name": "http-methods", "output": output})
    if "default" in scripts and port_info.get("product"):
        findings.append({"name": "banner", "output": port_info.get("product")})
    if "vuln" in scripts and port_info["port"] in VULN_HINTS:
        for hint in VULN_HINTS[port_info["port"]]:
            findings.append({"name": "vuln", "output": hint})
    return findings


def analyze_nmap_results(hosts):
    enriched = []
    for host in hosts:
        vulns = []
        risk_score = 0
        for port in host.get("ports", []):
            if port["state"] != "open":
                continue
            risk = PORT_RISK.get(port["port"], (None, "low"))[1]
            risk_score += {"low": 2, "medium": 6, "high": 12}.get(risk, 2)
            if port["port"] in VULN_HINTS:
                vulns.extend(VULN_HINTS[port["port"]])
        level = "low"
        if risk_score >= 80:
            level = "critical"
        elif risk_score >= 45:
            level = "high"
        elif risk_score >= 20:
            level = "medium"
        enriched.append(
            {
                **host,
                "vulnerabilities": list(set(vulns)),
                "risk_level": level,
                "risk_score": min(risk_score, 100),
            }
        )
    return enriched


def parse_nmap_xml(xml_text):
    root = ET.fromstring(xml_text)
    results = []
    for host in root.findall("host"):
        addr_el = host.find("address")
        ip = addr_el.get("addr") if addr_el is not None else "unknown"
        status_el = host.find("status")
        status = status_el.get("state") if status_el is not None else "unknown"
        hostnames = host.find("hostnames")
        hostname = None
        if hostnames is not None:
            name_el = hostnames.find("hostname")
            if name_el is not None:
                hostname = name_el.get("name")
        os_guess = None
        os_el = host.find("os")
        if os_el is not None:
            os_match = os_el.find("osmatch")
            if os_match is not None:
                os_guess = os_match.get("name")
        ports_el = host.find("ports")
        ports = []
        if ports_el is not None:
            for port_el in ports_el.findall("port"):
                portid = int(port_el.get("portid"))
                proto = port_el.get("protocol")
                state_el = port_el.find("state")
                state = state_el.get("state") if state_el is not None else "unknown"
                service_el = port_el.find("service")
                service = service_el.get("name") if service_el is not None else None
                product = service_el.get("product") if service_el is not None else None
                version = service_el.get("version") if service_el is not None else None
                scripts = []
                for script_el in port_el.findall("script"):
                    scripts.append({"name": script_el.get("id"), "output": script_el.get("output")})
                ports.append(
                    {
                        "port": portid,
                        "protocol": proto,
                        "state": state,
                        "service": service,
                        "product": product,
                        "version": version,
                        "scripts": scripts,
                    }
                )
        results.append(
            {"ip": ip, "status": status, "hostname": hostname, "ports": ports, "os_guess": os_guess}
        )
    return results


def build_nmap_args(options, target):
    args = ["nmap", "-oX", "-"]
    scan_type = options.get("scan_type", "syn")
    
    # Advanced Scan Types Mapping
    scan_type_map = {
        "syn": "-sS",
        "connect": "-sT",
        "udp": "-sU",
        "ack": "-sA",
        "window": "-sW",
        "null": "-sN",
        "fin": "-sF",
        "xmas": "-sX"
    }
    args.append(scan_type_map.get(scan_type, "-sS"))

    if options.get("service_version"):
        args.append("-sV")
    if options.get("os_detect"):
        args.append("-O")
    if options.get("aggressive"):
        args.append("-A")
    
    ports = options.get("ports")
    if ports:
        args.extend(["-p", ports])
    
    scripts = options.get("scripts") or []
    if scripts:
        args.extend(["--script", ",".join(scripts)])
    
    # Performance & Accuracy
    args.extend(["--max-retries", "2", "--host-timeout", "10m", "-T4"])
    
    args.append(target)
    return args


def count_port_states(hosts):
    counts = {"open": 0, "closed": 0, "filtered": 0, "open|filtered": 0}
    for host in hosts:
        for port in host.get("ports", []):
            state = port.get("state")
            if state in counts:
                counts[state] += 1
    return counts


def nmap_scan_worker(job, target, options):
    targets = clamp_targets(parse_target_list(target), limit=512)
    scan_type = options.get("scan_type", "syn")
    service_version = options.get("service_version") or options.get("aggressive")
    os_detect = options.get("os_detect") or options.get("aggressive")
    scripts = set(options.get("scripts") or [])
    if options.get("aggressive"):
        scripts.update({"default", "vuln"})
    
    # Performance Optimization: Tighter timeouts
    timeout = 0.5 if options.get("aggressive") else 0.3
    ports = options.get("ports") or DEFAULT_ADV_PORTS
    
    if isinstance(ports, str):
        try:
            ports = validate_ports(ports)
        except ValueError:
            ports = DEFAULT_ADV_PORTS

    ports = ports[:1024]
    push_event(job, "log", f"Targets loaded: {len(targets)}. Total ports to scan per target: {len(ports)}")
    
    # Check for system Nmap if requested
    if options.get("use_nmap") and shutil.which("nmap"):
        push_event(job, "log", "Running system Nmap engine for accuracy...")
        args = build_nmap_args(options, target)
        try:
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            push_event(job, "progress", {"progress": 50, "current_ip": "Scanning..."})
            stdout, stderr = process.communicate()
            if process.returncode == 0:
                hosts = parse_nmap_xml(stdout)
                analyzed = analyze_nmap_results(hosts)
                risk = compute_risk_summary(analyzed)
                with LATEST_LOCK:
                    for host in analyzed:
                        LATEST_NMAP[host["ip"]] = host
                counts = count_port_states(analyzed)
                summary = {
                    "targets": len(analyzed),
                    "open_ports": counts["open"],
                    "engine": "nmap",
                }
                push_event(job, "progress", {"progress": 100, "current_ip": "Done"})
                finish_job(job, {"hosts": analyzed, "summary": summary, "risk": risk})
                return
            else:
                push_event(job, "log", f"System Nmap failed (code {process.returncode}), falling back to internal engine", "warn")
        except Exception as e:
            push_event(job, "log", f"Error running system Nmap: {e}, falling back to internal engine", "warn")

    # Internal Engine (Optimized)
    push_event(job, "log", "Running internal scanning engine (multi-threaded)...")
    if scan_type == "syn":
        # Internal engine doesn't support raw SYN on all platforms easily without root
        scan_type = "connect"
        
    results = []
    for index, host in enumerate(targets):
        alive, latency, ttl = ping_host(host)
        hostname = resolve_hostname(host) if alive else None
        host_ports = []
        
        # Performance: Use ThreadPoolExecutor with higher concurrency
        workers = min(300, len(ports))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            if scan_type == "udp":
                futures = [executor.submit(scan_udp_port, host, port, timeout + 0.2) for port in ports]
            else:
                futures = [
                    executor.submit(scan_tcp_port, host, port, timeout, service_version or "default" in scripts)
                    for port in ports
                ]
            
            for future in as_completed(futures):
                res = future.result()
                if res["state"] == "open":
                    host_ports.append(res)
        
        # Run scripts only on open ports
        for port_info in host_ports:
            port_info["scripts"] = run_script_checks(host, port_info, scripts)
            
        status = "up" if alive or host_ports else "down"
        os_guess = refine_os_guess(ttl, host_ports) if os_detect else None
        
        results.append({
            "ip": host,
            "status": status,
            "hostname": hostname,
            "ports": sorted(host_ports, key=lambda p: (p["protocol"], p["port"])),
            "os_guess": os_guess,
        })
        
        progress = int(((index + 1) / len(targets)) * 100)
        push_event(job, "progress", {"progress": progress, "current_ip": host})

    for host_data in results:
        host_data["open_ports"] = [p for p in host_data["ports"] if p["state"] == "open"]

    analyzed = analyze_nmap_results(results)
    risk = compute_risk_summary(analyzed)
    with LATEST_LOCK:
        for host in analyzed:
            LATEST_NMAP[host["ip"]] = host
            
    counts = count_port_states(analyzed)
    summary = {
        "targets": len(analyzed),
        "open_ports": counts["open"],
        "engine": "internal",
    }
    finish_job(job, {"hosts": analyzed, "summary": summary, "risk": risk})



@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/scan/host-discovery/start", methods=["POST"])
@limiter.limit("12 per minute")
def start_host_discovery():
    payload = request.get_json(force=True)
    ip_range = payload.get("ip_range", "")
    ports = payload.get("ports")
    fetchers = payload.get("fetchers") or ["latency", "hostname", "mac", "ports", "ttl"]
    alive_method = payload.get("alive_method", "icmp")
    try:
        ports = validate_ports(ports)
        targets = clamp_targets(parse_ip_range(ip_range, expand_single=True))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    job = new_job("host_discovery")
    thread = threading.Thread(
        target=host_discovery_worker, args=(job, targets, ports, fetchers, alive_method), daemon=True
    )
    thread.start()
    return jsonify({"job_id": job["id"], "targets": len(targets)})


@app.route("/api/scan/nmap/start", methods=["POST"])
@limiter.limit("6 per minute")
def start_nmap_scan():
    payload = request.get_json(force=True)
    try:
        target = validate_target(payload.get("target", ""))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    
    ports = payload.get("ports", "")
    # Note: If it's a list, we leave it as is for internal engine.
    # If it's a string, we validate it.
    if isinstance(ports, str) and ports:
        try:
            validate_ports(ports)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
            
    options = {
        "scan_type": payload.get("scan_type", "syn"),
        "service_version": bool(payload.get("service_version")),
        "os_detect": bool(payload.get("os_detect")),
        "aggressive": bool(payload.get("aggressive")),
        "ports": ports,
        "scripts": payload.get("scripts", []),
        "use_nmap": bool(payload.get("use_nmap")),
    }
    job = new_job("nmap_scan")
    thread = threading.Thread(target=nmap_scan_worker, args=(job, target, options), daemon=True)
    thread.start()
    return jsonify({"job_id": job["id"]})


@app.route("/api/scan/stream/<job_id>")
def stream_job(job_id):
    with JOB_LOCK:
        job = JOB_STORE.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    def event_stream():
        while True:
            try:
                event = job["queue"].get(timeout=1)
                yield f"event: {event['event']}\ndata: {json.dumps(event['payload'])}\n\n"
                if event["event"] == "done":
                    break
            except queue.Empty:
                if job["done"]:
                    break
        yield "event: close\ndata: {}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


def parse_asn(text):
    if not text:
        return None
    match = re.search(r"\bAS(\d+)\b", text)
    if match:
        return f"AS{match.group(1)}"
    return None


def geo_lookup(ip):
    provider = OSINT_CONFIG.get("geo_provider") or "ipapi"
    token = OSINT_CONFIG.get("geo_token") or ""
    if provider == "ipinfo":
        url = f"https://ipinfo.io/{ip}/json"
        if token:
            url = f"{url}?token={token}"
        try:
            response = requests.get(url, timeout=6)
            if response.status_code == 200:
                data = response.json()
                loc = data.get("loc", "")
                lat, lon = (loc.split(",") + [None, None])[:2]
                return {
                    "lat": float(lat) if lat else None,
                    "lon": float(lon) if lon else None,
                    "city": data.get("city"),
                    "region": data.get("region"),
                    "country": data.get("country"),
                    "org": data.get("org"),
                    "asn": parse_asn(data.get("org")),
                }
        except requests.RequestException:
            pass
        return {}
    
    url = f"http://ip-api.com/json/{ip}?fields=status,message,lat,lon,city,regionName,country,org,as"
    try:
        response = requests.get(url, timeout=6)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return {
                    "lat": data.get("lat"),
                    "lon": data.get("lon"),
                    "city": data.get("city"),
                    "region": data.get("regionName"),
                    "country": data.get("country"),
                    "org": data.get("org"),
                    "asn": parse_asn(data.get("as")),
                }
    except requests.RequestException:
        pass
    return {}

def shodan_lookup(ip):
    token = OSINT_CONFIG.get("shodan_token")
    if not token:
        return None
    try:
        api = shodan.Shodan(token)
        # host() method is more reliable and includes ports
        results = api.host(ip)
        return results
    except shodan.APIError as e:
        print(f"Shodan API Error: {e}")
        # Fallback to direct request if library fails
        try:
            url = f"https://api.shodan.io/shodan/host/{ip}?key={token}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
    except Exception as e:
        print(f"Shodan Error: {e}")
    return None


def rdap_lookup(ip):
    endpoints = [
        "https://rdap.arin.net/registry/ip/",
        "https://rdap.ripe.net/ip/",
        "https://rdap.apnic.net/ip/",
        "https://rdap.afrinic.net/rdap/ip/",
        "https://rdap.lacnic.net/rdap/ip/",
    ]
    for base in endpoints:
        try:
            response = requests.get(f"{base}{ip}", timeout=6)
        except requests.RequestException:
            continue
        if response.status_code == 200:
            return response.json()
    return {}


def abuseipdb_lookup(ip):
    token = OSINT_CONFIG.get("abuseipdb_token")
    if not token:
        return {}
    url = "https://api.abuseipdb.com/api/v2/check"
    querystring = {
        "ipAddress": ip,
        "maxAgeInDays": "90",
    }
    headers = {
        "Accept": "application/json",
        "Key": token,
    }
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=6)
        if response.status_code == 200:
            return response.json()
    except requests.RequestException:
        pass
    return {}


def virustotal_lookup(observable):
    token = OSINT_CONFIG.get("vt_token")
    if not token:
        return {}
    
    # Check if IP or Domain
    try:
        ipaddress.ip_address(observable)
        url = f"https://www.virustotal.com/api/v3/ip_addresses/{observable}"
    except ValueError:
        url = f"https://www.virustotal.com/api/v3/domains/{observable}"
        
    headers = {
        "x-apikey": token
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
    except requests.RequestException:
        pass
    return {}




def censys_lookup(ip):
    token = OSINT_CONFIG.get("censys_token")
    if not token: return None
    try:
        # Support for new Censys API Key (Bearer)
        url = f"https://search.censys.io/api/v2/hosts/{ip}"
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        # Fallback to old ID:Secret if token contains a colon
        if ":" in token:
            api_id, api_secret = token.split(":", 1)
            response = requests.get(url, auth=(api_id, api_secret), timeout=10)
            return response.json() if response.status_code == 200 else None
        return None
    except: return None

def alienvault_otx_lookup(ip):
    # Free public API (no token needed for basic info, but token improves limits)
    token = OSINT_CONFIG.get("otx_token")
    url = f"https://otx.alienvault.com/api/v1/indicators/IPv4/{ip}/general"
    headers = {"X-OTX-API-KEY": token} if token else {}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.json() if response.status_code == 200 else None
    except: return None

def pulsedive_lookup(ip):
    try:
        url = f"https://pulsedive.com/api/info.php?indicator={ip}"
        response = requests.get(url, timeout=10)
        return response.json() if response.status_code == 200 else None
    except: return None

def onyphe_lookup(ip):
    try:
        url = f"https://www.onyphe.io/api/v2/summary/ip/{ip}"
        response = requests.get(url, timeout=10)
        return response.json() if response.status_code == 200 else None
    except: return None

def ipinfo_lookup(ip):
    token = OSINT_CONFIG.get("ipinfo_token")
    url = f"https://ipinfo.io/{ip}/json"
    if token: url += f"?token={token}"
    try:
        response = requests.get(url, timeout=10)
        return response.json() if response.status_code == 200 else None
    except: return None

def hackertarget_lookup(target):
    results = {}
    return results # Obsoleted due to aggressive rate limiting

def bgpview_lookup(ip):
    try:
        url = f"https://api.bgpview.io/ip/{ip}"
        response = requests.get(url, timeout=10)
        return response.json() if response.status_code == 200 else None
    except: return None

def threatfox_lookup(ip):
    try:
        url = "https://threatfox-api.abuse.ch/api/v1/"
        payload = {"query": "get_iocs", "search_term": ip}
        response = requests.post(url, json=payload, timeout=10)
        return response.json() if response.status_code == 200 else None
    except: return None

def urlhaus_lookup(domain):
    try:
        url = "https://urlhaus-api.abuse.ch/v1/host/"
        payload = {"host": domain}
        response = requests.post(url, data=payload, timeout=10)
        return response.json() if response.status_code == 200 else None
    except: return None

def robtex_lookup(ip):
    try:
        url = f"https://freeapi.robtex.com/ipquery/{ip}"
        response = requests.get(url, timeout=10)
        return response.json() if response.status_code == 200 else None
    except: return None

@app.route("/api/intel/advanced", methods=["POST"])
@limiter.limit("20 per minute")
def advanced_intel():
    payload = request.get_json(force=True)
    target = payload.get("target", "").strip()
    if not target: return jsonify({"error": "Target required"}), 400
    
    is_ip = False
    try:
        ipaddress.ip_address(target)
        is_ip = True
    except: pass

    results = {}
    if is_ip:
        results["censys"] = censys_lookup(target)
        results["ipinfo"] = ipinfo_lookup(target)
        results["otx"] = alienvault_otx_lookup(target)
        results["pulsedive"] = pulsedive_lookup(target)
        results["onyphe"] = onyphe_lookup(target)
        results["bgpview"] = bgpview_lookup(target)
        results["threatfox"] = threatfox_lookup(target)
        results["robtex"] = robtex_lookup(target)
    
    results["urlhaus"] = urlhaus_lookup(target)
    
    try:
        w = whois.whois(target)
        results["whois"] = {"data": str(w)}
    except Exception as e:
        results["whois"] = {"data": f"Error resolving whois locally: {e}"}
        
    return jsonify(results)


@app.route("/api/osint/lookup", methods=["POST"])
@limiter.limit("30 per minute")
def osint_lookup():
    payload = request.get_json(force=True)
    observable = payload.get("observable", "").strip()
    if not observable:
        return jsonify({"error": "Observable required"}), 400
    
    try:
        ipaddress.ip_address(observable)
        is_ip = True
    except ValueError:
        is_ip = False

    geo = geo_lookup(observable) if is_ip else {}
    try:
        abuse = abuseipdb_lookup(observable) if is_ip else {}
        vt = virustotal_lookup(observable)
        dns_data = dns_lookup(observable)
        shodan_data = shodan_lookup(observable) if is_ip else None
        whois_data = rdap_lookup(observable) if is_ip else None
    except Exception as e:
        push_event(job, "log", f"OSINT lookup failed: {e}", "error")
        finish_job(job, {"error": "OSINT lookup failed"})
        return

    vt_summary = {}
    if vt and "data" in vt:
        attributes = vt["data"]["attributes"]
        stats = attributes.get("last_analysis_stats", {})
        vt_summary = {
            "malicious": stats.get("malicious", 0),
            "suspicious": stats.get("suspicious", 0),
            "undetected": stats.get("undetected", 0),
            "harmless": stats.get("harmless", 0),
            "reputation": attributes.get("reputation", 0),
            "tags": attributes.get("tags", []),
            "whois": attributes.get("whois", "N/A")[:500],
            "last_analysis_date": attributes.get("last_analysis_date", 0)
        }

    threat_intel = []
    if abuse and "data" in abuse:
        abuse_data = abuse["data"]
        threat_intel.append({
            "source": "AbuseIPDB",
            "score": abuse_data.get("abuseConfidenceScore", 0),
            "reports": abuse_data.get("totalReports", 0),
            "last_report": abuse_data.get("lastReportedAt", "N/A")
        })

    return jsonify({
        "observable": observable,
        "geo": geo,
        "vt": vt_summary,
        "threat_intel": threat_intel,
        "shodan": shodan_data,
        "dns": dns_data,
        "whois": whois_data
    })


@app.route("/api/report", methods=["POST"])
@limiter.limit("20 per minute")
def generate_report():
    try:
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT

        payload = request.get_json(force=True)
        report_id = str(uuid.uuid4())[:8]
        filename = f"scan-report-{report_id}.pdf"
        filepath = os.path.join(app.root_path, filename)

        doc = SimpleDocTemplate(filepath, pagesize=letter,
                                leftMargin=36, rightMargin=36,
                                topMargin=54, bottomMargin=36)

        title_s = ParagraphStyle("T1", fontSize=22, textColor=colors.HexColor("#0ea5e9"),
                                 spaceAfter=4, alignment=TA_CENTER, fontName="Helvetica-Bold")
        h2_s    = ParagraphStyle("H2", fontSize=13, textColor=colors.HexColor("#0284c7"),
                                 spaceBefore=14, spaceAfter=6, fontName="Helvetica-Bold")
        h3_s    = ParagraphStyle("H3", fontSize=10, textColor=colors.HexColor("#0369a1"),
                                 spaceBefore=8, spaceAfter=4, fontName="Helvetica-Bold")
        norm_s  = ParagraphStyle("NM", fontSize=8,  textColor=colors.HexColor("#1e293b"),
                                 spaceAfter=2, fontName="Helvetica")
        mono_s  = ParagraphStyle("MN", fontSize=7,  textColor=colors.HexColor("#334155"),
                                 fontName="Courier", leading=10)
        meta_s  = ParagraphStyle("MT", fontSize=8,  textColor=colors.HexColor("#64748b"),
                                 alignment=TA_CENTER, spaceAfter=2)

        HDR = colors.HexColor("#0f172a"); FG = colors.whitesmoke
        RB  = colors.HexColor("#f1f5f9"); RA = colors.HexColor("#e2e8f0")
        GR  = colors.HexColor("#cbd5e1"); W  = 539

        def ts(extra=None):
            base = [
                ("BACKGROUND",    (0,0),(-1,0),  HDR),
                ("TEXTCOLOR",     (0,0),(-1,0),  FG),
                ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
                ("FONTSIZE",      (0,0),(-1,0),  8),
                ("FONTSIZE",      (0,1),(-1,-1), 7),
                ("ALIGN",         (0,0),(-1,-1), "LEFT"),
                ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
                ("GRID",          (0,0),(-1,-1), 0.4, GR),
                ("ROWBACKGROUNDS",(0,1),(-1,-1), [RB, RA]),
                ("TOPPADDING",    (0,0),(-1,-1), 4),
                ("BOTTOMPADDING", (0,0),(-1,-1), 4),
                ("LEFTPADDING",   (0,0),(-1,-1), 6),
                ("RIGHTPADDING",  (0,0),(-1,-1), 6),
            ]
            if extra: base.extend(extra)
            return TableStyle(base)

        el = []

        # Cover
        el.append(Spacer(1,60))
        el.append(Paragraph("NetSEC Recon Report", title_s))
        el.append(Paragraph("Comprehensive Security Intelligence Dossier", meta_s))
        el.append(Spacer(1,8))
        el.append(Paragraph(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC", meta_s))
        el.append(Spacer(1,24))

        summary    = payload.get("summary", {})
        hosts      = payload.get("hosts", [])
        osint_data = payload.get("osint", {})
        adv_intel  = payload.get("adv_intel", {})
        subdomains = payload.get("subdomains", {})

        risk_score = summary.get("risk", {}).get("score", "n/a")
        risk_level = str(summary.get("risk", {}).get("level", "n/a")).upper()
        risk_col   = colors.HexColor("#dc2626") if risk_level in ("CRITICAL","HIGH") \
                     else colors.HexColor("#f59e0b") if risk_level == "MEDIUM" \
                     else colors.HexColor("#16a34a")

        cov_data = [
            ["Report Field",   "Value"],
            ["Classification", "CONFIDENTIAL — Internal Use Only"],
            ["Targets Scanned",str(summary.get("targets","0"))],
            ["Open Ports",     str(summary.get("open_ports","0"))],
            ["Risk Score",     f"{risk_score} / 100"],
            ["Risk Level",     risk_level],
            ["Report ID",      report_id],
            ["Scan Engine",    "NetSEC v4.2 — Neural Interface Terminal"],
        ]
        ct = Table(cov_data, colWidths=[180,359])
        ct.setStyle(ts([("TEXTCOLOR",(1,4),(1,4),risk_col),("FONTNAME",(1,4),(1,4),"Helvetica-Bold")]))
        el.append(ct); el.append(PageBreak())

        # Sec 1: Overview
        nmap_hosts = [h for h in hosts if h.get("ports")]
        el.append(Paragraph("1. Overview", h2_s))
        el.append(Paragraph("This dossier consolidates results from every module executed in this session.", norm_s))
        el.append(Spacer(1,8))
        toc = [["#","Module","Status"]]
        mods = [("2","IP Scan",bool(hosts)),("3","Nmap Port Scan",bool(nmap_hosts)),
                ("4","OSINT Intelligence",bool(osint_data)),("5","Advanced Intel",bool(adv_intel)),
                ("6","Domain / Subdomains",bool(subdomains))]
        ext_toc=[]
        for i,(n,lbl,ran) in enumerate(mods,1):
            toc.append([n,lbl,"COMPLETED" if ran else "NOT RUN"])
            ext_toc.append(("TEXTCOLOR",(2,i),(2,i),colors.HexColor("#16a34a") if ran else colors.HexColor("#94a3b8")))
        tt=Table(toc,colWidths=[40,260,239]); tt.setStyle(ts(ext_toc)); el.append(tt); el.append(PageBreak())

        # Sec 2: IP Scan
        el.append(Paragraph("2. IP Scan Results", h2_s))
        if hosts:
            alive=sum(1 for h in hosts if h.get("status")=="up")
            tot_op=sum(len(h.get("open_ports") or []) for h in hosts)
            el.append(Paragraph(f"{len(hosts)} hosts scanned · {alive} alive · {tot_op} open ports total", norm_s))
            el.append(Spacer(1,6))
            rows=[["IP","Status","Latency ms","Hostname","MAC","Open Ports"]]
            ce=[]
            for i,h in enumerate(hosts,1):
                prts=h.get("open_ports") or []
                pnums=[str(p.get("port",p) if isinstance(p,dict) else p) for p in prts]
                rows.append([h.get("ip","-"),h.get("status","-"),str(h.get("latency_ms") or "-"),
                              Paragraph(h.get("hostname") or "-",mono_s),
                              h.get("mac") or "-",
                              Paragraph(", ".join(pnums) or "None",mono_s)])
                ce.append(("TEXTCOLOR",(1,i),(1,i),colors.HexColor("#16a34a") if h.get("status")=="up" else colors.HexColor("#dc2626")))
            t=Table(rows,repeatRows=1,colWidths=[85,45,60,110,90,149]); t.setStyle(ts(ce)); el.append(t)
        else:
            el.append(Paragraph("IP Scan was not executed in this session.", norm_s))
        el.append(PageBreak())

        # Sec 3: Nmap
        el.append(Paragraph("3. Nmap Port Scan Results", h2_s))
        if nmap_hosts:
            for h in nmap_hosts:
                el.append(Paragraph(f"Host: {h.get('ip')}  |  Status: {h.get('status','?')}  |  OS: {h.get('os_guess') or 'Unknown'}  |  Risk: {str(h.get('risk_level','?')).upper()}", h3_s))
                vulns=h.get("vulnerabilities") or []
                if vulns: el.append(Paragraph("Vulnerabilities: "+(", ".join(vulns)),norm_s))
                port_list=h.get("ports") or h.get("open_ports") or []
                if port_list:
                    nr=[["Port","Proto","State","Service","Product/Version","Scripts"]]
                    se=[]
                    for i,p in enumerate(port_list,1):
                        sc2="; ".join(f"{s['name']}: {s['output']}" for s in (p.get("scripts") or []) if s.get("output"))
                        nr.append([str(p.get("port","-")),p.get("protocol","-"),p.get("state","-"),p.get("service") or "-",
                                   Paragraph(f"{p.get('product') or ''} {p.get('version') or ''}".strip() or "-",mono_s),
                                   Paragraph(sc2 or "-",mono_s)])
                        se.append(("TEXTCOLOR",(2,i),(2,i),
                                   colors.HexColor("#16a34a") if p.get("state")=="open" else
                                   colors.HexColor("#f59e0b") if p.get("state")=="filtered" else
                                   colors.HexColor("#dc2626")))
                    nt=Table(nr,repeatRows=1,colWidths=[42,38,48,70,150,191]); nt.setStyle(ts(se)); el.append(nt)
                else:
                    el.append(Paragraph("No open ports found.",norm_s))
                el.append(Spacer(1,10))
        else:
            el.append(Paragraph("Nmap scan was not executed in this session.", norm_s))
        el.append(PageBreak())

        # Sec 4: OSINT
        el.append(Paragraph("4. OSINT Intelligence", h2_s))
        if osint_data:
            for obs, data in osint_data.items():
                el.append(Paragraph(f"Target: {obs}", h3_s))
                geo = data.get("geo") or {}
                if any(geo.values()):
                    el.append(Paragraph("Geolocation", h3_s))
                    gr=[["Field","Value"],["Country",geo.get("country") or "-"],["City",geo.get("city") or "-"],
                        ["Region",geo.get("region") or "-"],["Org/ISP",geo.get("org") or "-"],
                        ["ASN",geo.get("asn") or "-"],
                        ["Coords",f"{geo.get('lat')}, {geo.get('lon')}" if geo.get("lat") else "-"]]
                    gt=Table(gr,colWidths=[130,409]); gt.setStyle(ts()); el.append(gt); el.append(Spacer(1,6))
                vt = data.get("vt") or {}
                if vt:
                    el.append(Paragraph("VirusTotal Analysis", h3_s))
                    mal=vt.get("malicious",0)
                    vr=[["Metric","Value"],["Malicious Detections",str(mal)],
                        ["Suspicious",str(vt.get("suspicious",0))],["Harmless",str(vt.get("harmless",0))],
                        ["Undetected",str(vt.get("undetected",0))],["Reputation",str(vt.get("reputation","N/A"))],
                        ["Tags",", ".join(vt.get("tags") or []) or "None"]]
                    ve=[("TEXTCOLOR",(1,1),(1,1),colors.HexColor("#dc2626")),("FONTNAME",(1,1),(1,1),"Helvetica-Bold")] if mal>0 else []
                    vt2=Table(vr,colWidths=[160,379]); vt2.setStyle(ts(ve)); el.append(vt2); el.append(Spacer(1,6))
                threat=data.get("threat_intel") or []
                abuse=next((x for x in threat if x.get("source")=="AbuseIPDB"),None)
                if abuse:
                    el.append(Paragraph("AbuseIPDB Threat Intelligence", h3_s))
                    sc3=abuse.get("score",0)
                    ar=[["Metric","Value"],["Confidence Score",f"{sc3}%"],
                        ["Total Reports",str(abuse.get("reports",0))],
                        ["Last Reported",str(abuse.get("last_report") or "Never")]]
                    ae=[("TEXTCOLOR",(1,1),(1,1),colors.HexColor("#dc2626")),("FONTNAME",(1,1),(1,1),"Helvetica-Bold")] if sc3>50 else []
                    at2=Table(ar,colWidths=[160,379]); at2.setStyle(ts(ae)); el.append(at2); el.append(Spacer(1,6))
                sh = data.get("shodan")
                if sh and isinstance(sh,dict) and not sh.get("error"):
                    el.append(Paragraph("Shodan Scan Data", h3_s))
                    sr=[["Field","Value"],["Hostnames",", ".join(sh.get("hostnames") or []) or "-"],
                        ["Country",sh.get("country_name") or "-"],["Organization",sh.get("org") or "-"],
                        ["Open Ports",", ".join(str(p) for p in (sh.get("ports") or [])) or "-"],
                        ["Last Update",str(sh.get("last_update") or "-")]]
                    st2=Table(sr,colWidths=[130,409]); st2.setStyle(ts()); el.append(st2); el.append(Spacer(1,6))
                dns = data.get("dns") or {}
                if dns:
                    el.append(Paragraph("DNS Records", h3_s))
                    dr=[["Type","Values"]]
                    for rtype,rvals in dns.items():
                        if rvals: dr.append([rtype,Paragraph(", ".join(str(v) for v in rvals),mono_s)])
                    if len(dr)>1:
                        dt2=Table(dr,repeatRows=1,colWidths=[70,469]); dt2.setStyle(ts()); el.append(dt2); el.append(Spacer(1,6))
                whois = data.get("whois")
                if whois:
                    el.append(Paragraph("WHOIS / RDAP", h3_s))
                    if isinstance(whois,dict):
                        name=whois.get("name") or whois.get("handle") or ""
                        org2="-"
                        for ent in (whois.get("entities") or [])[:2]:
                            vc=ent.get("vcardArray",[])
                            if vc and len(vc)>1:
                                for prop in vc[1]:
                                    if prop[0]=="fn": org2=prop[3]; break
                        wt=f"Handle: {name}  |  Org: {org2}  |  Type: {whois.get('type','')}"
                    else:
                        wt=str(whois)[:500]
                    el.append(Paragraph(wt,mono_s)); el.append(Spacer(1,6))
                el.append(Spacer(1,14))
        else:
            el.append(Paragraph("OSINT scan was not executed in this session.", norm_s))
        el.append(PageBreak())

        # Sec 5: Advanced Intel
        el.append(Paragraph("5. Advanced Threat Intelligence", h2_s))
        if adv_intel:
            for target, intel in adv_intel.items():
                el.append(Paragraph(f"Target: {target}", h3_s))
                ipinfo=intel.get("ipinfo")
                if ipinfo:
                    el.append(Paragraph("IPinfo.io", h3_s))
                    ir=[["Field","Value"],["City",ipinfo.get("city") or "-"],["Region",ipinfo.get("region") or "-"],
                        ["Country",ipinfo.get("country") or "-"],["Org",ipinfo.get("org") or "-"],
                        ["Timezone",ipinfo.get("timezone") or "-"],["Location",ipinfo.get("loc") or "-"]]
                    it=Table(ir,colWidths=[130,409]); it.setStyle(ts()); el.append(it); el.append(Spacer(1,6))
                censys=intel.get("censys")
                if censys:
                    el.append(Paragraph("Censys", h3_s))
                    result=censys.get("result") or censys; svcs=result.get("services") or []
                    if svcs:
                        cr=[["Port","Service","Transport","Banner"]]
                        for svc in svcs[:20]:
                            cr.append([str(svc.get("port") or "-"),svc.get("service_name") or "-",
                                       svc.get("transport_protocol") or "-",
                                       Paragraph((svc.get("banner") or "-")[:80],mono_s)])
                        crt=Table(cr,repeatRows=1,colWidths=[50,120,80,289]); crt.setStyle(ts()); el.append(crt)
                    else:
                        el.append(Paragraph(str(censys)[:300],mono_s))
                    el.append(Spacer(1,6))
                otx=intel.get("otx")
                if otx:
                    el.append(Paragraph("AlienVault OTX", h3_s))
                    pc=otx.get("pulse_info",{}).get("count",0)
                    or2=[["Field","Value"],["Pulse Count",str(pc)],["Reputation",str(otx.get("reputation","-"))],
                         ["Type",str(otx.get("type") or otx.get("type_title") or "-")],
                         ["Country",str(otx.get("country_name") or "-")],["Indicator",str(otx.get("indicator") or "-")]]
                    oe=[("TEXTCOLOR",(1,1),(1,1),colors.HexColor("#dc2626")),("FONTNAME",(1,1),(1,1),"Helvetica-Bold")] if pc>0 else []
                    ot2=Table(or2,colWidths=[130,409]); ot2.setStyle(ts(oe)); el.append(ot2); el.append(Spacer(1,6))
                pd2=intel.get("pulsedive")
                if pd2:
                    el.append(Paragraph("Pulsedive", h3_s))
                    pr=[["Field","Value"],["Risk",str(pd2.get("risk") or "-")],
                        ["Indicator",str(pd2.get("indicator") or "-")],["Type",str(pd2.get("type") or "-")],
                        ["Last Seen",str(pd2.get("stamp_seen") or pd2.get("stamp_updated") or "-")]]
                    pt2=Table(pr,colWidths=[130,409]); pt2.setStyle(ts()); el.append(pt2); el.append(Spacer(1,6))
                bgpv=intel.get("bgpview")
                if bgpv and bgpv.get("data"):
                    el.append(Paragraph("BGPView", h3_s))
                    bd=bgpv["data"]; pfx=bd.get("prefixes") or bd.get("ipv4_prefixes") or []; asns2=bd.get("asns") or []
                    br=[["Field","Value"],["Prefixes",", ".join(p.get("prefix",str(p)) for p in pfx[:10]) or "-"],
                        ["ASNs",", ".join(str(a.get("asn","")) for a in asns2) or "-"],["Name",bd.get("name") or "-"]]
                    bt2=Table(br,colWidths=[130,409]); bt2.setStyle(ts()); el.append(bt2); el.append(Spacer(1,6))
                tf=intel.get("threatfox")
                if tf:
                    el.append(Paragraph("ThreatFox IOCs", h3_s))
                    iocs=tf.get("data") or []
                    if iocs:
                        tfr=[["IOC","Type","Malware","Confidence"]]
                        for ioc in (iocs if isinstance(iocs,list) else [iocs])[:15]:
                            tfr.append([Paragraph(str(ioc.get("ioc") or ioc.get("ioc_value") or "-"),mono_s),
                                        str(ioc.get("ioc_type") or "-"),
                                        str(ioc.get("malware") or ioc.get("malware_printable") or "-"),
                                        str(ioc.get("confidence_level") or "-")])
                        tft=Table(tfr,repeatRows=1,colWidths=[180,80,150,129]); tft.setStyle(ts()); el.append(tft)
                    else:
                        el.append(Paragraph("No IOCs found.",norm_s))
                    el.append(Spacer(1,6))
                uh=intel.get("urlhaus")
                if uh:
                    el.append(Paragraph("URLhaus Malware URLs", h3_s))
                    uh_urls=uh.get("urls") or []
                    uhr=[["Field","Value"],["Query Status",uh.get("query_status") or "-"],["URLs Found",str(len(uh_urls))]]
                    for u in uh_urls[:10]:
                        uhr.append([Paragraph(str(u.get("url") or "-"),mono_s),str(u.get("url_status") or "-")])
                    uht=Table(uhr,colWidths=[260,279]); uht.setStyle(ts()); el.append(uht); el.append(Spacer(1,6))
                rb=intel.get("robtex")
                if rb:
                    el.append(Paragraph("Robtex Network Intelligence", h3_s))
                    rr=[["Field","Value"],["Passive DNS",str(len(rb.get("pas") or []))],
                        ["Active DNS",str(len(rb.get("act") or []))],["AS",str(rb.get("as") or "-")],
                        ["AS Name",str(rb.get("asname") or "-")],["BGP Route",str(rb.get("bgproute") or "-")]]
                    rbt=Table(rr,colWidths=[160,379]); rbt.setStyle(ts()); el.append(rbt); el.append(Spacer(1,6))
                wa=intel.get("whois")
                if wa and wa.get("data"):
                    el.append(Paragraph("WHOIS (Advanced)", h3_s))
                    el.append(Paragraph(str(wa["data"])[:600],mono_s)); el.append(Spacer(1,6))
                el.append(Spacer(1,14))
        else:
            el.append(Paragraph("Advanced Intel module was not executed in this session.", norm_s))
        el.append(PageBreak())

        # Sec 6: Subdomains
        el.append(Paragraph("6. Domain Details & Subdomain Recon", h2_s))
        if subdomains:
            for domain, subs in subdomains.items():
                el.append(Paragraph(f"Domain: {domain}  —  {len(subs)} subdomains discovered", h3_s))
                if subs:
                    col_sz=max(1,(len(subs)+2)//3)
                    chunks=[subs[i:i+col_sz] for i in range(0,len(subs),col_sz)]
                    while len(chunks)<3: chunks.append([])
                    max_r=max(len(c) for c in chunks)
                    gr2=[["Subdomain","Subdomain","Subdomain"]]
                    for i in range(max_r):
                        gr2.append([Paragraph(chunks[0][i] if i<len(chunks[0]) else "",mono_s),
                                    Paragraph(chunks[1][i] if i<len(chunks[1]) else "",mono_s),
                                    Paragraph(chunks[2][i] if i<len(chunks[2]) else "",mono_s)])
                    st3=Table(gr2,repeatRows=1,colWidths=[W//3,W//3,W//3]); st3.setStyle(ts()); el.append(st3)
                else:
                    el.append(Paragraph("No subdomains were found.",norm_s))
                el.append(Spacer(1,14))
        else:
            el.append(Paragraph("Subdomain Recon was not executed in this session.", norm_s))

        doc.build(el)
        return send_file(filepath, as_attachment=True, download_name=filename)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": f"Failed to generate PDF report: {e}"}), 500



def get_subdomains(domain):
    subdomains = set()
    
    # 1. AlienVault OTX
    try:
        url = f"https://otx.alienvault.com/api/v1/indicators/domain/{domain}/passive_dns"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            for item in resp.json().get('passive_dns', []):
                subdomains.add(item['hostname'].lower())
    except: pass

    # 2. CertSpotter
    try:
        url = f"https://api.certspotter.com/v1/issuances?domain={domain}&include_subdomains=true&expand=dns_names"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            for item in resp.json():
                for name in item.get('dns_names', []):
                    subdomains.add(name.lower())
    except: pass
    
    # 3. Anubis
    try:
        url = f"https://jldc.me/anubis/subdomains/{domain}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            for sub in resp.json():
                subdomains.add(sub.lower())
    except: pass

    # 4. crt.sh Backup
    if len(subdomains) < 5:
        try:
            url = f"https://crt.sh/?q=%.{domain}&output=json"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                for entry in resp.json():
                    for name in entry.get("name_value", "").split("\n"):
                        subdomains.add(name.strip().lower())
        except: pass
    
    return sorted(list(s for s in subdomains if s.endswith(domain) and '*' not in s))


@app.route("/api/scan/subdomains", methods=["POST"])
@limiter.limit("10 per minute")
def subdomain_recon():
    payload = request.get_json(force=True)
    domain = payload.get("domain", "").strip()
    if not domain:
        return jsonify({"error": "Domain required"}), 400
    
    subdomains = get_subdomains(domain)
    return jsonify({"domain": domain, "subdomains": subdomains})


@app.route("/api/sandbox_proxy")
@limiter.limit("50 per minute")
def sandbox_proxy():
    url = request.args.get("url")
    if not url:
        return "No URL provided", 400
    try:
        if not url.startswith("http"):
            url = "https://" + url
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        resp = requests.get(url, headers=headers, timeout=10, verify=False)
        
        # Inject base tag to fix relative links inside the iframe
        content = resp.text
        if "<head>" in content.lower():
            content = re.sub(r"(<head[^>]*>)", f"\\1\n<base href='{url}'>", content, flags=re.IGNORECASE)
        
        response = Response(content, status=resp.status_code)
        response.headers["Content-Type"] = resp.headers.get("Content-Type", "text/html")
        
        # Remove framing restrictions to allow the iframe to load
        for header in ["X-Frame-Options", "Content-Security-Policy", "X-Content-Type-Options"]:
            if header in response.headers:
                del response.headers[header]
                
        return response
    except Exception as e:
        return f"Error loading sandbox URL: {e}", 500

PLAYWRIGHT_SESSION = {"browser": None, "context": None, "page": None, "stop_event": threading.Event()}

def fetch_working_proxy():
    try:
        r = requests.get("https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all", timeout=10)
        if r.status_code == 200:
            proxies = [line.strip() for line in r.text.split('\n') if line.strip()]
            random.shuffle(proxies)
            for p in proxies[:10]:
                try:
                    proxy_addr = "http://" + p
                    res = requests.get("https://www.google.com", proxies={"http": proxy_addr, "https": proxy_addr}, timeout=3)
                    if res.status_code == 200:
                        return proxy_addr
                except:
                    pass
    except:
        pass
    return None
        
def launch_playwright_browser(url, use_proxy):
    try:
        with sync_playwright() as p:
            PLAYWRIGHT_SESSION["stop_event"].clear()
            
            # Use a fast free proxy service if proxy is enabled
            proxy = None
            if use_proxy:
                PLAYWRIGHT_SESSION["current_proxy"] = "Fetching..."
                PLAYWRIGHT_SESSION["next_rotation"] = time.time() + 180
                working_proxy = fetch_working_proxy()
                if working_proxy:
                    proxy = {"server": working_proxy}
                    PLAYWRIGHT_SESSION["current_proxy"] = working_proxy
                else:
                    PLAYWRIGHT_SESSION["current_proxy"] = "Failed to find proxy"
            
            browser = p.chromium.launch(headless=False, proxy=proxy)
            PLAYWRIGHT_SESSION["browser"] = browser
            
            context = browser.new_context()
            page = context.new_page()
            PLAYWRIGHT_SESSION["context"] = context
            PLAYWRIGHT_SESSION["page"] = page
            
            try:
                page.goto(url, timeout=20000)
            except Exception:
                pass
            
            # Wait for browser to be closed by user or stop event, rotating proxy if needed
            while not PLAYWRIGHT_SESSION["stop_event"].is_set():
                if use_proxy:
                    stopped = PLAYWRIGHT_SESSION["stop_event"].wait(1)
                    if stopped:
                        break
                    
                    if time.time() >= PLAYWRIGHT_SESSION.get("next_rotation", 0):
                        PLAYWRIGHT_SESSION["next_rotation"] = time.time() + 180
                        PLAYWRIGHT_SESSION["current_proxy"] = "Fetching..."
                        working_proxy = fetch_working_proxy()
                        if working_proxy:
                            try:
                                PLAYWRIGHT_SESSION["current_proxy"] = working_proxy
                                print(f"Rotating to new proxy: {working_proxy}")
                                
                                old_context = PLAYWRIGHT_SESSION["context"]
                                current_url = url
                                if PLAYWRIGHT_SESSION["page"] and PLAYWRIGHT_SESSION["page"].url and PLAYWRIGHT_SESSION["page"].url != "about:blank":
                                    current_url = PLAYWRIGHT_SESSION["page"].url
                                    
                                # Rotate proxy by creating new context and page
                                # MUST close old context BEFORE creating new one to avoid multiple windows
                                if old_context:
                                    old_context.close()
                                
                                context = browser.new_context(proxy={"server": working_proxy})
                                page = context.new_page()
                                
                                PLAYWRIGHT_SESSION["context"] = context
                                PLAYWRIGHT_SESSION["page"] = page
                                
                                page.goto(current_url, timeout=20000)
                            except Exception as e:
                                print(f"Error rotating proxy: {e}")
                else:
                    # Normal browser, just wait indefinitely until stop event
                    PLAYWRIGHT_SESSION["stop_event"].wait()
                    break
    except Exception as e:
        print(f"Playwright error: {e}")
    finally:
        PLAYWRIGHT_SESSION["stop_event"].set()
        if PLAYWRIGHT_SESSION.get("browser"):
            try: PLAYWRIGHT_SESSION["browser"].close()
            except: pass
        PLAYWRIGHT_SESSION["browser"] = None
        PLAYWRIGHT_SESSION["context"] = None
        PLAYWRIGHT_SESSION["page"] = None
        PLAYWRIGHT_SESSION["current_proxy"] = None
        PLAYWRIGHT_SESSION["next_rotation"] = 0

@app.route("/api/sandbox/status", methods=["GET"])
def sandbox_status():
    active = not PLAYWRIGHT_SESSION["stop_event"].is_set() and PLAYWRIGHT_SESSION.get("browser") is not None
    time_left = max(0, int(PLAYWRIGHT_SESSION.get("next_rotation", 0) - time.time())) if active else 0
    return jsonify({
        "active": active,
        "current_proxy": PLAYWRIGHT_SESSION.get("current_proxy"),
        "time_left": time_left
    })

@app.route("/api/sandbox/launch", methods=["POST"])
@limiter.limit("50 per minute")
def sandbox_launch():
    payload = request.get_json(force=True)
    url = payload.get("url")
    use_proxy = payload.get("use_proxy", False)
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    
    if not url.startswith("http"):
        url = "https://" + url

    # Ensure only one instance at a time by closing the previous one
    PLAYWRIGHT_SESSION["stop_event"].set()
    if PLAYWRIGHT_SESSION.get("browser"):
        try:
            PLAYWRIGHT_SESSION["browser"].close()
        except Exception:
            pass
    time.sleep(1)

    threading.Thread(target=launch_playwright_browser, args=(url, use_proxy), daemon=True).start()
    return jsonify({"status": "launched", "message": "Isolated browser launched on host system."})

@app.route("/api/sandbox/destroy", methods=["POST"])
def sandbox_destroy():
    PLAYWRIGHT_SESSION["stop_event"].set()
    if PLAYWRIGHT_SESSION.get("browser"):
        try:
            PLAYWRIGHT_SESSION["browser"].close()
        except Exception:
            pass
    return jsonify({"status": "destroyed"})


# ---- Reddit Intelligence ------------------------------------------

REDDIT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}


def fetch_full_reddit_post(permalink, limit=2):
    """Fetch full post data + top comments for a given Reddit permalink via .json"""
    try:
        json_url = "https://www.reddit.com" + permalink + ".json?limit=5&sort=top"
        r = requests.get(json_url, headers=REDDIT_HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        
        # 1. Extract Post Data
        if not data or not isinstance(data, list) or not data[0].get("data", {}).get("children"):
            return None
            
        p = data[0]["data"]["children"][0]["data"]
        
        # 2. Extract Comments
        comments = []
        if len(data) > 1:
            for child in data[1]["data"]["children"][:limit+3]:
                c = child.get("data", {})
                body = c.get("body", "")
                if body and body not in ("[deleted]", "[removed]") and len(body) > 15:
                    comments.append({
                        "author": c.get("author", ""),
                        "score":  c.get("score", 0),
                        "body":   body[:280],
                    })
                if len(comments) >= limit:
                    break
                    
        return {
            "id":           p.get("id", ""),
            "title":        p.get("title", ""),
            "author":       p.get("author", ""),
            "subreddit":    p.get("subreddit_name_prefixed", ""),
            "permalink":    p.get("permalink", ""),
            "url":          "https://www.reddit.com" + p.get("permalink", ""),
            "external_url": p.get("url", ""),
            "score":        p.get("score", 0),
            "upvote_ratio": p.get("upvote_ratio", 0),
            "num_comments": p.get("num_comments", 0),
            "created_utc":  p.get("created_utc", 0),
            "selftext":     (p.get("selftext", "") or "")[:600],
            "domain":       p.get("domain", ""),
            "is_self":      p.get("is_self", False),
            "link_flair":   p.get("link_flair_text", ""),
            "thumbnail":    p.get("thumbnail", ""),
            "gilded":       p.get("gilded", 0),
            "comments":     comments,
        }
    except Exception as ex:
        print("fetch_full_reddit_post error:", ex)
        return None


def reddit_search(query, limit=10):
    """
    Search Reddit using native JSON for the exact behavior of the mobile app,
    mixing 'hot' (top active) and 'new' (latest) posts.
    Filters out posts older than 3 years.
    """
    THREE_YEARS_AGO = time.time() - (3 * 365.25 * 24 * 3600)
    results = []
    try:
        hot_plinks = []
        new_plinks = []
        
        # 1. Fetch HOT (Top active)
        try:
            r = requests.get(
                "https://www.reddit.com/search.json",
                params={"q": query, "sort": "hot", "t": "all", "limit": 25, "type": "link"},
                headers=REDDIT_HEADERS, timeout=8
            )
            if r.status_code == 200:
                hot_plinks = [c["data"]["permalink"] for c in r.json().get("data", {}).get("children", [])
                              if c["data"].get("created_utc", 0) >= THREE_YEARS_AGO]
        except: pass

        # 2. Fetch NEW (Latest)
        try:
            r = requests.get(
                "https://www.reddit.com/search.json",
                params={"q": query, "sort": "new", "t": "all", "limit": 25, "type": "link"},
                headers=REDDIT_HEADERS, timeout=8
            )
            if r.status_code == 200:
                new_plinks = [c["data"]["permalink"] for c in r.json().get("data", {}).get("children", [])
                              if c["data"].get("created_utc", 0) >= THREE_YEARS_AGO]
        except: pass
        
        # 3. Interleave to get Top & Latest mixed
        permalinks = []
        seen = set()
        for i in range(max(len(hot_plinks), len(new_plinks))):
            if i < len(hot_plinks) and hot_plinks[i] not in seen:
                seen.add(hot_plinks[i])
                permalinks.append(hot_plinks[i])
            if i < len(new_plinks) and new_plinks[i] not in seen:
                seen.add(new_plinks[i])
                permalinks.append(new_plinks[i])
            if len(permalinks) >= limit * 2:
                break
                
        if not permalinks:
            return [], "No Reddit posts found within the last 3 years."

        # 4. Fetch rich data + comments for the selected permalinks
        raw_posts = []
        with ThreadPoolExecutor(max_workers=min(limit * 2, 10)) as ex:
            futures = {ex.submit(fetch_full_reddit_post, p, 2): i for i, p in enumerate(permalinks)}
            sorted_posts = [None] * len(permalinks)
            for ft in futures:
                idx = futures[ft]
                try:
                    res = ft.result()
                    if res:
                        # Double-check age filter on fetched post
                        if res.get("created_utc", 0) >= THREE_YEARS_AGO:
                            sorted_posts[idx] = res
                except: pass
                
            raw_posts = [p for p in sorted_posts if p]

        results = raw_posts[:limit]
    except Exception as ex:
        return results, str(ex)
    return results, None



def fetch_reddit_post(reddit_url):
    """Fetch full content of a Reddit post via its .json endpoint."""
    try:
        json_url = reddit_url.rstrip("/") + ".json?limit=5"
        r = requests.get(json_url, headers=REDDIT_HEADERS, timeout=10)
        if r.status_code != 200:
            return ""
        data = r.json()
        post = data[0]["data"]["children"][0]["data"] if data else {}
        text = post.get("selftext", "") or post.get("title", "")
        if len(data) > 1:
            for child in data[1]["data"]["children"][:5]:
                body = child.get("data", {}).get("body", "")
                if body and len(body) > 30:
                    text += "\n\n" + body[:500]
        return text.strip()
    except Exception:
        return ""


def extractive_summarize(query, texts):
    """Local frequency-based extractive summarization - no API needed."""
    combined = "Query: %s\n\n" % query
    for i, t in enumerate(texts, 1):
        if t:
            combined += "--- Post %d ---\n%s\n\n" % (i, t[:600])
    combined = combined[:5000]

    sentences = re.split(r"(?<=[.!?])\s+", combined)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 30][:100]

    stopwords = {
        "the","a","an","in","on","at","is","it","of","to","and","or","for",
        "with","this","that","was","are","be","by","from","as","have","has",
        "not","but","been","will","can","its","i","we","they","you","he","she",
        "post","reddit","comment","https","www","com","http",
    }
    import collections, heapq
    words = re.findall(r"\b[a-z]{3,}\b", combined.lower())
    freq = collections.Counter(w for w in words if w not in stopwords)
    if not freq:
        return "Insufficient content to generate a summary."

    scores = {}
    for sent in sentences:
        ws = re.findall(r"\b[a-z]{3,}\b", sent.lower())
        scores[sent] = sum(freq.get(w, 0) for w in ws if w not in stopwords) / max(len(ws), 1)

    top_sentences = heapq.nlargest(min(7, len(sentences)), scores, key=scores.get)
    ordered = [s for s in sentences if s in top_sentences]
    return " ".join(ordered[:7]) or "Could not generate a summary."


def ai_summarize(query, posts_content, source="Reddit"):
    """
    Summarize using Pollinations.ai (free ChatGPT, no login).
    Returns PLAIN TEXT - no markdown, no asterisks, no tables.
    Falls back to local extractive summarization.
    """
    combined_parts = []
    for i, t in enumerate(posts_content, 1):
        if t:
            combined_parts.append("Post %d: %s" % (i, t[:450]))
    combined = "\n\n".join(combined_parts)[:4000]

    prompt = (
        "You are a cybersecurity analyst. A user searched %s for: \"%s\"\n\n"
        "Here are excerpts from the top posts:\n\n%s\n\n"
        "Write a clear, professional security intelligence summary. "
        "IMPORTANT: Use PLAIN TEXT only. Do NOT use markdown, asterisks, bold text, "
        "bullet symbols, tables, or any formatting characters. "
        "Write in clear paragraphs with simple labels like: "
        "KEY FINDINGS, THREAT INDICATORS, COMMUNITY CONSENSUS, RECOMMENDATIONS. "
        "Be concise and factual."
    ) % (source, query, combined)

    # Try Pollinations.ai (free ChatGPT / OpenAI, no key needed)
    try:
        r = requests.post(
            "https://text.pollinations.ai/",
            json={
                "messages": [{"role": "user", "content": prompt}],
                "model": "openai",
                "seed": 42,
            },
            headers={"Content-Type": "application/json"},
            timeout=50,
        )
        if r.status_code == 200 and r.text.strip():
            text = r.text.strip()
            # Strip any residual markdown symbols from response
            text = re.sub(r"\*\*|__|\_|\|\*", "", text)
            text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
            text = re.sub(r"^\|.*\|.*$", "", text, flags=re.MULTILINE)
            text = re.sub(r"^[-]+$", "", text, flags=re.MULTILINE)
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            return text
    except Exception:
        pass

    # Fallback: HuggingFace
    try:
        hf_prompt = "Summarize these %s posts about %s in plain text: %s" % (source, query, combined[:2500])
        hf = requests.post(
            "https://api-inference.huggingface.co/models/sshleifer/distilbart-cnn-12-6",
            json={"inputs": hf_prompt, "parameters": {"max_length": 350, "min_length": 60}},
            headers={"Content-Type": "application/json"},
            timeout=25,
        )
        if hf.status_code == 200:
            out = hf.json()
            if isinstance(out, list) and out and out[0].get("summary_text"):
                return out[0]["summary_text"]
    except Exception:
        pass

    return extractive_summarize(query, posts_content)


# ── Google / Web Dork Search using SearXNG (free, no API key) ──────

# ---- Google / Web Dork Search via DuckDuckGo HTML (free, no API key) ---

import urllib.parse as _urlparse

_DDG_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
           "AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/124.0.0.0 Safari/537.36")
_DDG_HEADERS = {
    "User-Agent": _DDG_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _decode_ddg_url(raw_url):
    if not raw_url:
        return ""
    if raw_url.startswith("//duckduckgo.com"):
        raw_url = "https:" + raw_url
    if "duckduckgo.com/l/?" in raw_url:
        try:
            qs = _urlparse.parse_qs(_urlparse.urlparse(raw_url).query)
            return _urlparse.unquote(qs.get("uddg", [raw_url])[0])
        except Exception:
            pass
    return raw_url


def _strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def google_dork_search(query, limit=10):
    """DuckDuckGo HTML scraping — free, no API key needed. Bing as fallback."""
    results = _ddg_html_search(query, limit)
    if results:
        return results, None
    results = _bing_html_search(query, limit)
    if results:
        return results, None
    return [], "Search unavailable — check network connectivity"


def _ddg_html_search(query, limit=10):
    """Post to DuckDuckGo HTML endpoint and parse results."""
    try:
        r = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "b": "", "kl": "us-en"},
            headers=_DDG_HEADERS,
            timeout=15,
            allow_redirects=True,
        )
        if r.status_code != 200:
            return []
        html = r.content.decode("utf-8", errors="replace")

        title_matches   = re.findall(r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL)
        snippet_matches = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)

        results = []
        for i, (raw_url, raw_title) in enumerate(title_matches[:limit]):
            real_url = _decode_ddg_url(raw_url.strip())
            title    = _strip_html(raw_title)
            snippet  = _strip_html(snippet_matches[i]) if i < len(snippet_matches) else ""
            if not title or not real_url:
                continue
            results.append({
                "title":          title,
                "url":            real_url,
                "snippet":        snippet,
                "engines":        "DuckDuckGo",
                "score":          round(1.0 - i * 0.05, 2),
                "published_date": "",
                "thumbnail":      "",
            })
        return results
    except Exception as ex:
        print("DDG HTML error: " + str(ex))
        return []


def _bing_html_search(query, limit=10):
    """Bing HTML scraping fallback."""
    try:
        r = requests.get(
            "https://www.bing.com/search",
            params={"q": query, "count": str(limit), "mkt": "en-US"},
            headers=_DDG_HEADERS,
            timeout=12,
        )
        if r.status_code != 200:
            return []
        html = r.content.decode("utf-8", errors="replace")
        blocks = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)
        results = []
        for block in blocks[:limit]:
            tm = re.search(r'<h2[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', block, re.DOTALL)
            sm = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
            if not tm:
                continue
            results.append({
                "title":          _strip_html(tm.group(2)),
                "url":            tm.group(1),
                "snippet":        _strip_html(sm.group(1)) if sm else "",
                "engines":        "Bing",
                "score":          round(1.0 - len(results)*0.05, 2),
                "published_date": "",
                "thumbnail":      "",
            })
        return results
    except Exception as ex:
        print("Bing search error: " + str(ex))
        return []


def fetch_web_page_text(url):
    """Fetch simplified text from a web URL for summarization."""
    try:
        r = requests.get(url, headers={"User-Agent": _DDG_UA}, timeout=8)
        text = re.sub(r"<[^>]+>", " ", r.content.decode("utf-8", errors="replace"))
        text = re.sub(r"\s{2,}", " ", text).strip()
        return text[:800]
    except Exception:
        return ""



@app.route("/api/reddit/search", methods=["POST"])
@limiter.limit("20 per minute")
def reddit_search_route():
    payload = request.get_json(force=True)
    query = (payload.get("query") or "").strip()
    if not query:
        return jsonify({"error": "Query required"}), 400
    posts, error = reddit_search(query, limit=12)
    if error and not posts:
        return jsonify({"error": error}), 502
    return jsonify({"posts": posts, "query": query, "count": len(posts)})


@app.route("/api/reddit/analyze", methods=["POST"])
@limiter.limit("10 per minute")
def reddit_analyze_route():
    payload = request.get_json(force=True)
    query = (payload.get("query") or "").strip()
    posts = payload.get("posts", [])
    if not posts:
        return jsonify({"error": "No posts provided"}), 400

    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(fetch_reddit_post, p.get("url", "")) for p in posts[:10]]
        contents = [ft.result() for ft in futures]

    enriched = []
    for post, txt in zip(posts, contents):
        enriched.append("TITLE: %s\n%s" % (post.get("title", ""), txt))

    summary = ai_summarize(query, enriched, source="Reddit")
    return jsonify({"summary": summary, "posts_analyzed": len(enriched)})

# ------------------------------------------------------------------


@app.route("/api/google/search", methods=["POST"])
@limiter.limit("20 per minute")
def google_dork_route():
    payload = request.get_json(force=True)
    query = (payload.get("query") or "").strip()
    if not query:
        return jsonify({"error": "Query required"}), 400
    results, error = google_dork_search(query, limit=12)
    if error and not results:
        return jsonify({"error": error}), 502
    return jsonify({"results": results, "query": query, "count": len(results)})


@app.route("/api/google/analyze", methods=["POST"])
@limiter.limit("10 per minute")
def google_analyze_route():
    payload  = request.get_json(force=True)
    query    = (payload.get("query") or "").strip()
    results  = payload.get("results", [])
    if not results:
        return jsonify({"error": "No results provided"}), 400

    with ThreadPoolExecutor(max_workers=6) as ex:
        futures  = [ex.submit(fetch_web_page_text, r.get("url","")) for r in results[:8]]
        contents = [ft.result() for ft in futures]

    enriched = []
    for res, txt in zip(results, contents):
        enriched.append("TITLE: %s\nSNIPPET: %s\n%s" % (res.get("title",""), res.get("snippet",""), txt))

    summary = ai_summarize(query, enriched, source="Google")
    return jsonify({"summary": summary, "results_analyzed": len(enriched)})


@app.route("/api/threat-intel/feed", methods=["GET"])
@limiter.limit("20 per minute")
def threat_intel_feed():
    try:
        import urllib.request
        # We will use The Hacker News RSS
        req = urllib.request.Request('https://feeds.feedburner.com/TheHackersNews', headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=10).read()
        root = ET.fromstring(html)
        items = []
        for item in root.findall('.//item')[:10]:
            title = item.find('title')
            link = item.find('link')
            pub_date = item.find('pubDate')
            items.append({
                'title': title.text if title is not None else "No Title",
                'link': link.text if link is not None else "#",
                'pub_date': pub_date.text if pub_date is not None else ""
            })
        return jsonify({"feed": items})
    except Exception as e:
        return jsonify({"error": str(e), "feed": []}), 500


@app.route("/api/dashboard/live-stats", methods=["GET"])
@limiter.limit("20 per minute")
def dashboard_live_stats():
    # Attempt to fetch ISC Infocon for Global Threat
    threat_level = "ELEVATED"
    try:
        r = requests.get("https://isc.sans.edu/api/infocon?json", timeout=5)
        if r.status_code == 200:
            status = r.json().get("status", "green")
            if status == "green": threat_level = "LOW"
            elif status == "yellow": threat_level = "ELEVATED"
            elif status == "orange": threat_level = "HIGH"
            elif status == "red": threat_level = "CRITICAL"
    except Exception:
        pass

    # Fetch NVD total CVE count
    total_cve = 245000 # default realistic
    try:
        r = requests.get("https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=1", timeout=5)
        if r.status_code == 200:
            total_cve = r.json().get("totalResults", total_cve)
    except Exception:
        pass

    # Local stats
    jobs_completed = len([j for j in JOB_STORE.values() if j.get("done")])
    scanner_health = 98 # Simulate
    
    return jsonify({
        "global_threat": threat_level,
        "total_cve": total_cve,
        "jobs_completed": jobs_completed,
        "scanner_health": f"{scanner_health}%"
    })


@app.route("/api/soc/feed", methods=["GET"])
@limiter.limit("20 per minute")
def soc_feed():
    feed = []

    # ── Source 1: CISA Known Exploited Vulnerabilities (KEV) ──────────────
    # Free, no auth, 1,500+ real actively-exploited CVEs, updated daily
    try:
        r = requests.get(
            "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
            timeout=12,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if r.status_code == 200:
            vulns = r.json().get("vulnerabilities", [])
            # Sort by dateAdded descending, take 12 most recent
            recent = sorted(vulns, key=lambda x: x.get("dateAdded", ""), reverse=True)[:12]
            for v in recent:
                cve = v.get("cveID", "Unknown")
                vendor = v.get("vendorProject", "")
                product = v.get("product", "")
                host = f"{vendor} {product}".strip() or cve
                desc = v.get("shortDescription", "")[:120]
                date_added = v.get("dateAdded", "")
                tags = [v.get("vulnerabilityName", "CVE")[:20]] if v.get("vulnerabilityName") else ["exploited"]
                tags.append("KEV")
                feed.append({
                    "timestamp": date_added,
                    "host": host,
                    "tags": tags[:3],
                    "status": "online",
                    "detail": desc,
                    "cve": cve,
                    "source": "CISA-KEV"
                })
    except Exception:
        pass

    # ── Source 2: Feodo Tracker C2 Botnet IPs ────────────────────────────
    # Free, no auth, active C2 command-and-control servers (Emotet, QakBot, etc.)
    try:
        r = requests.get(
            "https://feodotracker.abuse.ch/downloads/ipblocklist.json",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if r.status_code == 200:
            bots = r.json()
            # Show online ones first, then offline
            active = [b for b in bots if b.get("status") == "online"]
            inactive = [b for b in bots if b.get("status") != "online"]
            selected = (active + inactive)[:8]
            for b in selected:
                ip = b.get("ip_address", "Unknown")
                port = b.get("port", "")
                malware = b.get("malware", "C2")
                asn = b.get("as_name", "")
                country = b.get("country", "")
                feed.append({
                    "timestamp": b.get("last_online", b.get("first_seen", ""))[:16],
                    "host": f"{ip}:{port}" if port else ip,
                    "tags": [malware, country, "C2-Botnet"],
                    "status": b.get("status", "offline"),
                    "detail": f"C2 server | AS: {asn}",
                    "cve": "",
                    "source": "Feodo-Tracker"
                })
    except Exception:
        pass

    # ── Source 3: AbuseIPDB Blacklist ─────────────────────────────────────
    # High-confidence abusive IPs (already have the API key in config)
    if len(feed) < 10:
        try:
            r = requests.get(
                "https://api.abuseipdb.com/api/v2/blacklist",
                headers={
                    "Key": OSINT_CONFIG.get("abuseipdb_token", ""),
                    "Accept": "application/json"
                },
                params={"confidenceMinimum": 95, "limit": 10},
                timeout=8
            )
            if r.status_code == 200:
                ips = r.json().get("data", [])
                for ip_data in ips[:10]:
                    feed.append({
                        "timestamp": (ip_data.get("lastReportedAt") or "")[:16],
                        "host": ip_data.get("ipAddress", "Unknown"),
                        "tags": ["abusive", "blacklisted", ip_data.get("countryCode", "??")],
                        "status": "online",
                        "detail": f"Confidence: {ip_data.get('abuseConfidenceScore', '?')}% | {ip_data.get('totalReports', '?')} reports",
                        "cve": "",
                        "source": "AbuseIPDB"
                    })
        except Exception:
            pass

    if feed:
        return jsonify({"feed": feed, "sources": list({f["source"] for f in feed})})
    return jsonify({"feed": [], "error": "All SOC feed sources temporarily unavailable"}), 200




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
