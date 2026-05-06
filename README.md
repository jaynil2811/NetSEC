```text
███╗   ██╗███████╗████████╗███████╗███████╗ ██████╗
████╗  ██║██╔════╝╚══██╔══╝██╔════╝██╔════╝██╔════╝
██╔██╗ ██║█████╗     ██║   ███████╗█████╗  ██║
██║╚██╗██║██╔══╝     ██║   ╚════██║██╔══╝  ██║
██║ ╚████║███████╗   ██║   ███████║███████╗╚██████╗
╚═╝  ╚═══╝╚══════╝   ╚═╝   ╚══════╝╚══════╝ ╚═════╝
```

<div align="center">

### Neural Interface Terminal v4.2
**A free, self-hosted, full-stack Network Security & OSINT Intelligence Platform**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-22d3ee?style=for-the-badge)](LICENSE)
[![Open Source](https://img.shields.io/badge/Open%20Source-Free-4ade80?style=for-the-badge&logo=github)](https://github.com)
[![Status](https://img.shields.io/badge/Status-Active-00ff88?style=for-the-badge)]()

<br/>

> **Zero cost. Zero subscriptions. Zero vendor lock-in.**
> Run it locally. Own your intelligence.

[🚀 Quick Start](#-quick-start) · [📖 Modules](#-modules) · [⚙️ API Setup](#️-api-configuration) · [📄 PDF Reports](#-pdf-reports) · [🤝 Contributing](#-contributing)

</div>

---


---

## 🧭 What Is NetSEC?

**NetSEC** is a self-hosted, browser-based cybersecurity operations platform. It combines network scanning, open-source intelligence, threat intelligence aggregation, subdomain enumeration, disposable browsing, and professional PDF reporting — all in one dark-themed terminal UI accessible from your browser at `http://localhost:8000`.

It was built because powerful security tools shouldn't cost thousands of dollars a year. NetSEC pulls from the same data sources used by enterprise platforms — **Shodan, VirusTotal, AbuseIPDB, Censys, AlienVault OTX, ThreatFox, URLhaus, Robtex, Pulsedive, BGPView, CISA KEV** — and puts them all in one place, free.

---

## ✨ Feature Overview

| Module | What It Does |
|--------|-------------|
| 🖥️ **Dashboard** | Live risk score, global threat level, SOC feed, Kaspersky Cybermap |
| 🔍 **IP Scanner** | Multi-threaded subnet sweep with MAC, hostname, TTL, port detection |
| 🛡️ **Nmap Engine** | 8 scan types, NSE scripts, OS/service detection, internal Python fallback |
| 🔎 **OSINT Intel** | VirusTotal + AbuseIPDB + Shodan + Geo map + DNS + WHOIS in one view |
| 🧠 **Advanced Intel** | 10 threat intel sources: Censys, OTX, ThreatFox, URLhaus, Robtex & more |
| 🌐 **Subdomain Recon** | 4 passive sources: OTX, CertSpotter, Anubis, crt.sh — auto-deduplicated |
| 🔴 **Reddit Intel** | Threat-aware Reddit search with free AI summarization |
| 🔍 **Google Dork** | DuckDuckGo/Bing dorking with quick operator buttons + AI summary |
| 🕵️ **Disposable Browser** | Sandboxed iframe + Playwright Chromium with auto proxy rotation |
| 🖥️ **System Logs** | Color-coded, module-tagged, timestamped real-time terminal |
| 📄 **PDF Reports** | One-click professional dossier covering all modules |

---

## 💰 What This Replaces

| Paid Tool | Category | Cost |
|-----------|----------|------|
| Shodan Monitor | Internet exposure monitoring | $49–$899/mo |
| Maltego | OSINT graphing & entity mapping | $999+/yr |
| Nessus | Vulnerability scanning | $3,500+/yr |
| SpiderFoot | Automated OSINT | $200–$1,500/yr |
| Censys | Internet-wide host search | $500+/mo |
| Recorded Future | Threat intelligence | Enterprise $$$ |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- `pip`
- (Optional) [Nmap](https://nmap.org/download.html) installed on your system for native scan support
- (Optional) [Playwright](https://playwright.dev/python/) for the Disposable Browser module

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/netsec.git
cd netsec

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Install Playwright browser for Disposable Browser module
playwright install chromium

# 5. Run the app
python app.py
```

Then open your browser and navigate to:
```
http://localhost:8000
```

---

## ⚙️ API Configuration

NetSEC works out of the box for network scanning with zero API keys. The intelligence modules are enhanced with free-tier API keys from the following providers:

Open `app.py` and locate the `OSINT_CONFIG` block near the top:

```python
OSINT_CONFIG = {
    "geo_provider":    "ipapi",      # "ipapi" (free) or "ipinfo"
    "geo_token":       "",           # ipinfo.io token (optional)
    "abuseipdb_token": "YOUR_KEY",   # abuseipdb.com → Free: 1,000 req/day
    "vt_token":        "YOUR_KEY",   # virustotal.com → Free: 4 req/min
    "shodan_token":    "YOUR_KEY",   # shodan.io      → Free: basic search
    "censys_token":    "YOUR_KEY",   # censys.io      → Free: 250 req/month
    "ipinfo_token":    "YOUR_KEY",   # ipinfo.io      → Free: 50k req/month
    "otx_token":       "",           # otx.alienvault.com → Free (optional)
}
```

### Where to Get Free API Keys

| Service | Free Tier | Link |
|---------|-----------|------|
| AbuseIPDB | 1,000 requests/day | [abuseipdb.com/register](https://www.abuseipdb.com/register) |
| VirusTotal | 4 requests/min | [virustotal.com](https://www.virustotal.com/gui/join-us) |
| Shodan | Basic host lookup | [shodan.io](https://account.shodan.io/register) |
| Censys | 250 queries/month | [censys.io](https://accounts.censys.io/register) |
| IPinfo | 50,000 req/month | [ipinfo.io/signup](https://ipinfo.io/signup) |
| AlienVault OTX | Free | [otx.alienvault.com](https://otx.alienvault.com) |

> **Note:** The app runs fully without any API keys. Keys only enhance the OSINT and Advanced Intel modules with richer data.

---

## 📦 Project Structure

```
netsec/
├── app.py                  # Main Flask application & all API routes
├── requirements.txt        # Python dependencies
├── templates/
│   └── index.html          # Single-page frontend UI (Tailwind + Leaflet)
├── static/
│   ├── css/
│   │   └── style.css       # Custom neon/terminal styles
│   └── js/
│       └── app.js          # All frontend logic (SSE, maps, cards, tabs)
└── scan-report-*.pdf       # Auto-generated PDF reports (gitignored)
```

---

## 📖 Modules

### 🖥️ Dashboard

The always-on mission control panel. Loaded with live data on every page visit.

- **AI Risk Score** — Composite 0–100 score from scanned ports weighted by risk level (high/medium/low)
- **Global Threat Level** — Live from [ISC SANS Infocon API](https://isc.sans.edu) — LOW / ELEVATED / HIGH / CRITICAL
- **CVE Counter** — Real-time total from the [NVD API](https://nvd.nist.gov)
- **Threat Intel Feed** — Latest cybersecurity headlines from The Hacker News RSS
- **Live Cyber Attack Map** — Kaspersky Cybermap embedded in the dashboard
- **Global SOC Feed** — Three live sources:
  - 🔴 **CISA KEV** — Actively exploited vulnerabilities (updated daily)
  - 🟠 **Feodo Tracker** — Active C2 botnet IPs (Emotet, QakBot, etc.)
  - 🟡 **AbuseIPDB Blacklist** — IPs with ≥95% confidence abuse score

---

### 🔍 IP Scanner

Multi-threaded subnet sweeper with configurable discovery modes.

**Input Formats:**
```
Single IP:    192.168.1.1
CIDR Range:   192.168.1.0/24
Dash Range:   10.0.0.1-10.0.0.254
```

**Features:**
- Alive detection via ICMP ping or TCP connect probe
- Parallel port scanning with configurable port list (`22,80,443` or `1-1000`)
- Per-host: Latency (ms), Hostname (reverse DNS), MAC (ARP), Open Ports, TTL, OS guess
- TTL-based OS fingerprinting: `≤64` → Linux, `≤128` → Windows, `>128` → Network device
- Live progress via Server-Sent Events (SSE)
- Export as **CSV** or **JSON**
- Sortable, filterable results table

---

### 🛡️ Nmap Engine

Full port scanner supporting real system Nmap or internal Python engine.

**Scan Types:**

| Flag | Name | Use Case |
|------|------|----------|
| `-sS` | TCP SYN | Stealthy, fast, default |
| `-sT` | TCP Connect | No root required |
| `-sU` | UDP | Discover UDP services |
| `-sA` | ACK | Firewall rule mapping |
| `-sW` | Window | ACK variant |
| `-sN` | Null | IDS evasion |
| `-sF` | FIN | IDS evasion |
| `-sX` | Xmas | IDS evasion |

**NSE Script Categories:** Default, Vuln, Exploit, Auth, Brute Force, Discovery, Safe

**Detection Modes:**
- `-sV` Service version detection (exact software + version)
- `-O` OS fingerprinting
- `-A` Aggressive (all of the above + traceroute + default scripts)

**Engine Logic:**
1. If system `nmap` is on `PATH` → runs native Nmap, parses XML output
2. If not → falls back to multi-threaded Python socket engine (300 workers)

---

### 🔎 OSINT Intel

Complete threat profile for any IP address or domain in a single lookup.

**For IP Addresses:**
- VirusTotal — Donut gauge with malicious/suspicious/harmless/undetected breakdown from 90+ AV engines
- AbuseIPDB — Confidence score %, total reports, last reported timestamp
- Shodan — Open ports, banners, hostnames, ISP, country
- Geolocation — Leaflet.js map + country/city/region/org/ASN details
- WHOIS/RDAP — Queried from ARIN → RIPE → APNIC → AFRINIC → LACNIC

**For Domains:**
- VirusTotal domain reputation
- DNS Records — A, AAAA, MX, TXT, NS, SOA, CNAME, PTR

---

### 🧠 Advanced Intel

Ten specialized threat intelligence sources queried simultaneously.

| Card | Source | Data |
|------|--------|------|
| Censys | censys.io | Exposed services, ports, transport, banners |
| AlienVault OTX | otx.alienvault.com | Threat pulses, reputation, country |
| IPinfo.io | ipinfo.io | Full IP metadata, timezone, org |
| Pulsedive | pulsedive.com | Risk level, indicator type, last seen |
| Onyphe | onyphe.io | Passive internet scan data |
| BGPView | bgpview.io | ASN, prefixes, BGP routing info |
| ThreatFox | abuse.ch | IOC list: malware family, type, confidence |
| URLhaus | abuse.ch | Malware distribution URLs associated with target |
| Robtex | robtex.com | Passive DNS history, active DNS, BGP route |
| WHOIS (Local) | python-whois | Registrar, dates, nameservers |

---

### 🌐 Subdomain Recon

Passive multi-source subdomain enumeration — no active brute force, no noise.

| Source | Method |
|--------|--------|
| AlienVault OTX | Passive DNS records |
| CertSpotter | SSL/TLS certificate transparency |
| Anubis (jldc.me) | Passive crawl + public datasets |
| crt.sh | Certificate Transparency Log fallback |

Results are automatically deduplicated, sorted, and wildcard entries are filtered out.

---

### 🔴 Reddit Intel

Turns Reddit's community knowledge into a threat intelligence source.

- Searches both `hot` (top active) and `new` (latest) posts simultaneously
- Filters posts older than 3 years automatically
- Each post card: title, subreddit, author, score, upvote ratio, comments, top 2 replies
- **AI Summarization chain** (no API key needed):
  1. Pollinations.ai (free ChatGPT / OpenAI)
  2. HuggingFace DistilBART (fallback)
  3. Local extractive summarization (final fallback)

---

### 🔍 Google Dork

Web OSINT through advanced search operators — completely free.

**Quick Dork Operators:**
```
site:pastebin.com       filetype:pdf
inurl:admin             intitle:index.of
intext:password
```

**Engine chain:** DuckDuckGo HTML scraping → Bing HTML fallback

---

### 🕵️ Disposable Browser

Safely visit suspicious URLs in an isolated session.

**Two Modes:**
1. **Iframe proxy** — Server-side stripping of `X-Frame-Options` and `Content-Security-Policy` headers; `<base>` tag injected for relative links
2. **Playwright Chromium** — Full browser launched on host system, invisible to browser history

**IP Rotation (Playwright mode):**
- Fetches working proxies from ProxyScrape
- Auto-rotates every 3 minutes
- Shows current proxy IP and countdown timer
- Old context closed before new one opens (single window guaranteed)

---

### 📄 PDF Reports

One-click generation of a full security dossier.

**Sections:**

| # | Section | Contents |
|---|---------|----------|
| Cover | Report Metadata | Classification, risk score, risk level, report ID, timestamp |
| 1 | Overview | Module run status (COMPLETED / NOT RUN) |
| 2 | IP Scan | Full host table: IP, status, latency, hostname, MAC, open ports |
| 3 | Nmap | Per-host: OS, risk, vulns, port/service/version/script breakdown |
| 4 | OSINT | Geo, VirusTotal, AbuseIPDB, Shodan, DNS, WHOIS/RDAP |
| 5 | Advanced Intel | IPinfo, Censys, OTX, Pulsedive, BGPView, ThreatFox, URLhaus, Robtex |
| 6 | Subdomains | Three-column grid of all discovered subdomains per domain |

**Styling:** Dark header rows, alternating row backgrounds, color-coded risk cells (red/amber/green), monospace for technical data — generated with ReportLab.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, Flask 3.0, Flask-Limiter |
| Scanning | Socket, Threading, ThreadPoolExecutor, subprocess (Nmap) |
| Frontend | HTML5, TailwindCSS (CDN), Vanilla JS |
| Maps | Leaflet.js |
| Browser | Playwright (Chromium) |
| PDF | ReportLab |
| DNS | dnspython |
| Streaming | Server-Sent Events (SSE) |
| Fonts | Google Fonts — Orbitron + Inter |

---

## 📋 Requirements

```txt
Flask==3.0.2
Flask-Limiter==3.5.0
requests==2.32.3
reportlab==4.2.0
shodan==1.27.0
dnspython==2.6.1
playwright  (install separately via: playwright install chromium)
python-whois (install separately via: pip install python-whois)
stem (install separately via: pip install stem)
```

---

## 🔒 Rate Limiting

The API is rate-limited to prevent abuse:

| Endpoint | Limit |
|----------|-------|
| Host Discovery | 12 per minute |
| Nmap Scan | 6 per minute |
| OSINT Lookup | 30 per minute |
| Advanced Intel | 20 per minute |
| Subdomain Recon | 10 per minute |
| Reddit Search | 20 per minute |
| Google Dork | 20 per minute |
| Sandbox | 50 per minute |
| Default (all others) | 120 per minute |

---

## ⚠️ Legal Disclaimer

> NetSEC is intended for **authorized security testing, educational research, and defensive security analysis only.**
>
> Scanning IP addresses, networks, or domains **without explicit permission** from the owner may be illegal in your jurisdiction. Always obtain written authorization before performing any scans against systems you do not own.
>
> The authors accept **no liability** for misuse of this software.

---

## 🤝 Contributing

Contributions are welcome! If you have ideas for new modules, integrations, or improvements:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-module`)
3. Commit your changes (`git commit -m 'Add new module'`)
4. Push to the branch (`git push origin feature/new-module`)
5. Open a Pull Request

---

## 📜 License

This project is licensed under the **MIT License** — free to use, modify, and distribute.

---

<div align="center">

**Built with 🩵 for the security community**

*If NetSEC saved you time or money, drop a ⭐ — it means a lot.*

[![Star](https://img.shields.io/github/stars/yourusername/netsec?style=social)](https://github.com/yourusername/netsec)

</div>
