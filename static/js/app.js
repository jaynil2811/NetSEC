let liveAttackMap;
let osintMap;

function sysLog(module, message, level = "info") {
  const logContainer = document.getElementById("central-logs");
  if (!logContainer) {
    console.error("Log container not found");
    return;
  }
  
  const time = new Date().toLocaleTimeString();
  const entry = document.createElement("div");
  entry.className = "py-1 border-b border-cyan-900/10 flex gap-4";
  
  let colorClass = "text-cyan-400";
  if (level === "warn") colorClass = "text-warn";
  if (level === "error") colorClass = "text-bad";
  if (level === "success") colorClass = "text-good";

  const icon = module === "OSINT" ? "fa-fingerprint" : 
               module === "SCAN" ? "fa-network-wired" : 
               module === "NMAP" ? "fa-shield-virus" : 
               module === "SYSTEM" ? "fa-info-circle" : "fa-terminal";

  entry.innerHTML = `
    <span class="text-cyan-700 shrink-0">[${time}]</span>
    <span class="text-cyan-500 shrink-0 w-16 uppercase font-bold"><i class="fas ${icon} mr-1"></i>${module}</span>
    <span class="${colorClass} break-all">${message}</span>
  `;
  
  logContainer.appendChild(entry);
  logContainer.scrollTop = logContainer.scrollHeight;
}

const state = {
  hostResults: [],
  nmapResults: [],
  osintResults: {},
  advIntelResults: {},
  subdomainResults: {},
  risk: { score: 0, level: "low" },
  sound: false,
  currentJob: null,
};

const navLinks = document.querySelectorAll(".nav-link");
const sections = document.querySelectorAll(".section-block");
navLinks.forEach((link) => {
  link.addEventListener("click", () => {
    const target = link.dataset.target;
    sections.forEach((section) => {
      section.classList.toggle("hidden", section.id !== target);
    });
    navLinks.forEach((item) => item.classList.remove("active"));
    link.classList.add("active");

    // Fix map loading issues when switching tabs
    if (target === "overview" && liveAttackMap) {
      setTimeout(() => liveAttackMap.invalidateSize(), 100);
    }
    if (target === "intel" && osintMap) {
      setTimeout(() => osintMap.invalidateSize(), 100);
    }
  });
});
if (navLinks.length) {
  navLinks[0].click();
}

const soundToggle = document.getElementById("sound-toggle");
soundToggle.addEventListener("click", () => {
  state.sound = !state.sound;
  soundToggle.textContent = `Sound: ${state.sound ? "ON" : "OFF"}`;
});

const hostTable = document.getElementById("host-table");
const hostFilter = document.getElementById("host-filter");
let hostSortKey = "ip";
let hostSortDir = 1;

document.querySelectorAll("#host-scan th[data-sort]").forEach((th) => {
  th.addEventListener("click", () => {
    const key = th.dataset.sort;
    if (hostSortKey === key) {
      hostSortDir *= -1;
    } else {
      hostSortKey = key;
      hostSortDir = 1;
    }
    renderHostTable();
  });
});

hostFilter.addEventListener("input", renderHostTable);

function renderHostTable() {
  const filter = hostFilter.value.toLowerCase();
  const rows = [...state.hostResults]
    .filter(
      (item) =>
        item.ip.toLowerCase().includes(filter) ||
        (item.hostname || "").toLowerCase().includes(filter)
    )
    .sort((a, b) => {
      const aPriority = a.status === "up" && a.open_ports.length > 0 ? 0 : a.status === "up" ? 1 : 2;
      const bPriority = b.status === "up" && b.open_ports.length > 0 ? 0 : b.status === "up" ? 1 : 2;
      if (aPriority !== bPriority) return aPriority - bPriority;
      const aPorts = a.open_ports.length;
      const bPorts = b.open_ports.length;
      if (aPorts !== bPorts) return bPorts - aPorts;
      const av = a[hostSortKey] || "";
      const bv = b[hostSortKey] || "";
      if (typeof av === "number" && typeof bv === "number") {
        return (av - bv) * hostSortDir;
      }
      return av.toString().localeCompare(bv.toString()) * hostSortDir;
    });
  hostTable.innerHTML = rows
    .map((item) => {
      const ports = item.open_ports.map((p) => p.port).join(", ");
      const statusClass = item.status === "up" ? "text-good" : "text-bad";
      const latencyClass = item.latency_ms == null ? "text-warn" : "text-good";
      const hostnameClass = item.hostname ? "text-good" : "text-warn";
      const portsClass = ports ? "text-good" : "text-warn";
      const macClass = item.mac ? "text-good" : "text-warn";
      return `<tr>
        <td class="text-good">${item.ip}</td>
        <td class="${statusClass}">${item.status}</td>
        <td class="${latencyClass}">${item.latency_ms ?? "-"}</td>
        <td class="${hostnameClass}">${item.hostname ?? "-"}</td>
        <td class="${portsClass}">${ports || "-"}</td>
        <td class="${macClass}">${item.mac ?? "-"}</td>
      </tr>`;
    })
    .join("");
}

function updateRisk() {
  const riskScoreEl = document.getElementById("risk-score");
  const riskLevelEl = document.getElementById("risk-level");
  const activeHostsEl = document.getElementById("active-hosts");
  const openPortsEl = document.getElementById("open-ports");
  riskScoreEl.textContent = state.risk.score;
  riskLevelEl.textContent = state.risk.level.toUpperCase();
  const active = state.hostResults.filter((h) => h.status === "up").length;
  const openPorts = state.hostResults.reduce((acc, host) => acc + host.open_ports.length, 0);
  activeHostsEl.textContent = active;
  openPortsEl.textContent = openPorts;
  riskScoreEl.className = "stat-value " + (state.risk.score >= 45 ? "text-bad" : "text-good");
  riskLevelEl.className = "stat-sub " + (state.risk.score >= 45 ? "text-bad" : "text-good");
  activeHostsEl.className = "stat-value " + (active > 0 ? "text-good" : "text-warn");
  openPortsEl.className = "stat-value " + (openPorts > 0 ? "text-warn" : "text-good");
}

function playBeep() {
  if (!state.sound) return;
  const context = new (window.AudioContext || window.webkitAudioContext)();
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  oscillator.type = "square";
  oscillator.frequency.setValueAtTime(420, context.currentTime);
  gain.gain.setValueAtTime(0.05, context.currentTime);
  oscillator.connect(gain);
  gain.connect(context.destination);
  oscillator.start();
  oscillator.stop(context.currentTime + 0.2);
}

document.getElementById("start-host-scan").addEventListener("click", async () => {
  const ipRange = document.getElementById("ip-range").value;
  const ports = document.getElementById("ip-ports").value;
  const aliveMethod = document.getElementById("alive-method").value;
  
  if (!ipRange) return alert("IP Range required");
  
  addHistoryItem(`Started host scan on ${ipRange}`);
  sysLog("SCAN", `Starting discovery on ${ipRange}...`);
  const fetchers = [];
  if (document.getElementById("fetch-latency").checked) fetchers.push("latency");
  if (document.getElementById("fetch-hostname").checked) fetchers.push("hostname");
  if (document.getElementById("fetch-mac").checked) fetchers.push("mac");
  if (document.getElementById("fetch-ports").checked) fetchers.push("ports");
  if (document.getElementById("fetch-ttl").checked) fetchers.push("ttl");
  const response = await fetch("/api/scan/host-discovery/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ip_range: ipRange, ports, fetchers, alive_method: aliveMethod }),
  });
  const data = await response.json();
  if (!response.ok) {
    sysLog("SCAN", `Launch failed: ${data.error}`, "error");
    alert(data.error || "Scan failed");
    return;
  }
  document.getElementById("host-progress").style.width = "0%";
  state.hostResults = [];
  renderHostTable();
  streamJob(data.job_id, handleHostEvent);
});

function handleHostEvent(event, payload) {
  if (event === "progress") {
    document.getElementById("host-progress").style.width = `${payload.progress}%`;
    sysLog("SCAN", `Scanning ${payload.current_ip}`);
  }
  if (event === "log") {
    sysLog("SCAN", payload);
  }
  if (event === "done") {
    if (payload.error) {
      sysLog("SCAN", `Scan failed: ${payload.error}`, "error");
      alert(payload.error);
      return;
    }
    state.hostResults = payload.hosts;
    state.risk = payload.risk;
    renderHostTable();
    updateRisk();
    sysLog("SCAN", "IP scan completed successfully", "success");
    playBeep();
    saveState();
  }
}

function streamJob(jobId, handler) {
  const source = new EventSource(`/api/scan/stream/${jobId}`);
  source.addEventListener("progress", (e) => handler("progress", JSON.parse(e.data)));
  source.addEventListener("log", (e) => handler("log", JSON.parse(e.data)));
  source.addEventListener("done", (e) => {
    handler("done", JSON.parse(e.data));
    source.close();
  });
}

document.getElementById("export-host-csv").addEventListener("click", () => {
  const rows = [
    ["IP", "Status", "Latency", "Hostname", "Open Ports", "MAC"],
    ...state.hostResults.map((h) => [
      h.ip,
      h.status,
      h.latency_ms ?? "",
      h.hostname ?? "",
      h.open_ports.map((p) => p.port).join(";"),
      h.mac ?? "",
    ]),
  ];
  const csv = rows.map((row) => row.map((cell) => `"${cell}"`).join(",")).join("\n");
  downloadFile(csv, "hosts.csv", "text/csv");
});

document.getElementById("export-host-json").addEventListener("click", () => {
  downloadFile(JSON.stringify(state.hostResults, null, 2), "hosts.json", "application/json");
});

function downloadFile(content, filename, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

const nmapTable = document.getElementById("nmap-table");
const nmapPortPreset = document.getElementById("nmap-port-preset");
const nmapPortsInput = document.getElementById("nmap-ports");

nmapPortPreset.addEventListener("change", () => {
  if (nmapPortPreset.value === "custom") {
    nmapPortsInput.classList.remove("hidden");
  } else {
    nmapPortsInput.classList.add("hidden");
  }
});

document.getElementById("start-nmap-scan").addEventListener("click", async () => {
  const target = document.getElementById("nmap-target").value;
  if (!target) return alert("Target required");
  
  addHistoryItem(`Started Nmap scan on ${target}`);
  sysLog("NMAP", `Launching advanced scan on ${target}...`);
  const scanType = document.getElementById("nmap-scan-type").value;
  
  let ports = "";
  if (nmapPortPreset.value === "common") ports = "21,22,23,25,53,80,110,139,143,443,445,3389,8080,8443";
  else if (nmapPortPreset.value === "default") ports = "1-1000";
  else if (nmapPortPreset.value === "all") ports = "1-65535";
  else ports = nmapPortsInput.value;

  const scripts = Array.from(document.getElementById("nmap-scripts").selectedOptions).map(
    (opt) => opt.value
  );
  const payload = {
    target,
    scan_type: scanType,
    ports,
    service_version: document.getElementById("nmap-service").checked,
    os_detect: document.getElementById("nmap-os").checked,
    aggressive: document.getElementById("nmap-aggressive").checked,
    use_nmap: document.getElementById("nmap-use-nmap").checked,
    scripts,
  };
  
  document.getElementById("nmap-progress").style.width = "5%";
  const response = await fetch("/api/scan/nmap/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    sysLog("NMAP", `Launch failed: ${data.error}`, "error");
    alert(data.error || "Scan failed");
    document.getElementById("nmap-progress").style.width = "0%";
    return;
  }
  document.getElementById("nmap-progress").style.width = "15%";
  streamJob(data.job_id, handleNmapEvent);
});

function handleNmapEvent(event, payload) {
  if (event === "progress") {
    document.getElementById("nmap-progress").style.width = `${payload.progress}%`;
  }
  if (event === "log") {
    sysLog("NMAP", payload);
  }
  if (event === "done") {
    document.getElementById("nmap-progress").style.width = "100%";
    if (payload.error) {
      sysLog("NMAP", `Nmap failed: ${payload.error}`, "error");
      setTimeout(() => { document.getElementById("nmap-progress").style.width = "0%"; }, 2000);
      return;
    }
    state.nmapResults = payload.hosts || [];
    if (payload.risk) {
      state.risk = payload.risk;
      updateRisk();
    }
    renderNmapTable();
    const totalHosts = payload.summary?.targets ?? state.nmapResults.length;
    const openPorts = payload.summary?.open_ports ?? 0;
    const engine = payload.summary?.engine ?? "internal";
    sysLog("NMAP", `Scan finished. Found ${openPorts} open ports across ${totalHosts} hosts using ${engine} engine.`, "success");
    playBeep();
    saveState();
    setTimeout(() => { document.getElementById("nmap-progress").style.width = "0%"; }, 2000);
  }
}

function renderNmapTable() {
  const showAll = document.getElementById("nmap-show-all").checked;
  nmapTable.innerHTML = state.nmapResults
    .flatMap((host) =>
      (showAll ? host.ports : host.ports.filter((port) => port.state === "open")).map((port) => {
        const stateClass = port.state === "open" ? "text-good" : "text-bad";
        const serviceClass = port.service ? "text-good" : "text-warn";
        const riskClass =
          host.risk_level === "critical" || host.risk_level === "high"
            ? "text-bad"
            : host.risk_level === "medium"
            ? "text-warn"
            : "text-good";
        const vulnClass = host.vulnerabilities?.length ? "text-bad" : "text-warn";
        const scriptOutput = (port.scripts || [])
          .map((entry) => `${entry.name}:${entry.output}`)
          .join("; ");
        return `<tr>
          <td class="text-good">${host.ip}</td>
          <td class="${host.status === "up" ? "text-good" : "text-bad"}">${host.status}</td>
          <td class="${stateClass}">${port.port}/${port.protocol}</td>
          <td class="${stateClass}">${port.state}</td>
          <td class="${serviceClass}">${port.service || "-"}</td>
          <td class="${serviceClass}">${port.product || ""} ${port.version || ""}</td>
          <td class="${riskClass}">${host.risk_level}</td>
          <td class="${vulnClass}">${(host.vulnerabilities || []).join(", ") || "-"}</td>
          <td class="${serviceClass}">${scriptOutput || "-"}</td>
        </tr>`;
      })
    )
    .join("");
}

document.getElementById("nmap-show-all").addEventListener("change", renderNmapTable);


document.getElementById("report-btn").addEventListener("click", async () => {
  // Combine all discovered hosts
  const allHosts = [...state.hostResults];
  state.nmapResults.forEach(nh => {
    const existing = allHosts.find(eh => eh.ip === nh.ip);
    if (existing) {
      // Merge ports
      nh.ports.forEach(np => {
        if (!existing.open_ports.find(ep => ep.port === np.port)) {
          existing.open_ports.push(np);
        }
      });
      existing.risk_level = nh.risk_level || existing.risk_level;
      existing.vulnerabilities = [...new Set([...(existing.vulnerabilities || []), ...(nh.vulnerabilities || [])])];
    } else {
      // Map Nmap host format to Scan host format if needed
      allHosts.push({
        ip: nh.ip,
        status: nh.status,
        hostname: nh.hostname || "",
        open_ports: nh.ports.filter(p => p.state === "open"),
        risk_level: nh.risk_level,
        vulnerabilities: nh.vulnerabilities
      });
    }
  });

  if (allHosts.length === 0) {
    return alert("No scan results available to generate report. Run a scan first!");
  }

  sysLog("SYSTEM", "Generating comprehensive PDF report...");
  
  const summary = {
    targets: allHosts.length,
    open_ports: allHosts.reduce((acc, h) => acc + h.open_ports.length, 0),
    risk: state.risk,
    generated_at: new Date().toLocaleString()
  };

  try {
    const response = await fetch("/api/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        summary,
        hosts: allHosts,
        osint: state.osintResults,
        adv_intel: state.advIntelResults,
        subdomains: state.subdomainResults
      }),
    });

    if (!response.ok) throw new Error("Report generation failed");

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `NetSEC-Report-${new Date().toISOString().split('T')[0]}.pdf`;
    link.click();
    URL.revokeObjectURL(url);
    sysLog("SYSTEM", "PDF Report downloaded successfully.", "success");
  } catch (err) {
    sysLog("SYSTEM", `Report error: ${err.message}`, "error");
  }
});

document.getElementById("clear-logs").addEventListener("click", () => {
  document.getElementById("central-logs").innerHTML = '<div class="text-cyan-600 italic border-b border-cyan-900/30 mb-2 pb-1">Logs cleared by administrator...</div>';
});

document.getElementById("osint-btn").addEventListener("click", async () => {
  const observable = document.getElementById("osint-input").value;
  const progressEl = document.getElementById("osint-progress");
  const dashboardEl = document.getElementById("osint-dashboard");

  if (!observable) return alert("Target required");

  addHistoryItem(`Started OSINT scan on ${observable}`);
  sysLog("OSINT", `Initiating deep analysis for: ${observable}`);
  progressEl.style.width = "10%";
  dashboardEl.classList.remove("hidden");

  try {
    const response = await fetch("/api/osint/lookup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ observable }),
    });
    
    progressEl.style.width = "50%";
    const data = await response.json();
    
    if (!response.ok) {
      sysLog("OSINT", `Analysis failed: ${data.error || "Unknown error"}`, "error");
      progressEl.style.width = "0%";
      return;
    }
    
    progressEl.style.width = "100%";
    sysLog("OSINT", `Analysis successfully retrieved for ${observable}`, "success");
    
    state.osintResults[data.observable] = data;
    
    // 1. Render Map
    renderOsintMap(data.geo);

    // 2. Render VirusTotal Visuals
    const vt = data.vt || {};
    const malicious = vt.malicious || 0;
    const suspicious = vt.suspicious || 0;
    
    sysLog("OSINT", `VirusTotal: ${malicious} malicious detections found.`);
    
    // Gauge Animation
    const totalVendors = (malicious + suspicious + (vt.undetected || 0) + (vt.harmless || 0)) || 1;
    const detectionRate = ((malicious + suspicious) / totalVendors) * 100;
    const vtGauge = document.getElementById("vt-gauge");
    const vtScoreText = document.getElementById("vt-score-text");
    
    const offset = 440 - (440 * detectionRate) / 100;
    vtGauge.style.strokeDashoffset = offset;
    vtGauge.style.color = detectionRate > 10 ? "#fca5a5" : detectionRate > 0 ? "#fde047" : "#86efac";
    vtScoreText.textContent = malicious + suspicious;
    vtScoreText.className = "text-3xl font-bold " + (detectionRate > 10 ? "text-bad" : detectionRate > 0 ? "text-warn" : "text-good");

    document.getElementById("vt-malicious").textContent = malicious;
    document.getElementById("vt-suspicious").textContent = suspicious;
    document.getElementById("vt-harmless").textContent = vt.harmless || 0;
    document.getElementById("vt-undetected").textContent = vt.undetected || 0;

    // 3. Render AbuseIPDB Visuals
    const abuseList = data.threat_intel || [];
    const abuse = abuseList.find(i => i.source === "AbuseIPDB") || { score: 0, reports: 0, last_report: "N/A" };
    
    sysLog("OSINT", `AbuseIPDB: Confidence score is ${abuse.score}% with ${abuse.reports} reports.`);
    
    const abuseBar = document.getElementById("abuse-bar");
    const abuseLevelText = document.getElementById("abuse-level-text");
    const confidence = abuse.score || 0;
    
    abuseBar.style.width = `${confidence}%`;
    abuseBar.className = "h-full transition-all duration-1000 ease-out " + (confidence > 50 ? "bg-bad" : confidence > 10 ? "bg-warn" : "bg-good");
    
    abuseLevelText.textContent = confidence > 50 ? "DANGEROUS" : confidence > 10 ? "SUSPICIOUS" : "SAFE";
    abuseLevelText.className = "text-2xl font-bold mb-2 " + (confidence > 50 ? "text-bad" : confidence > 10 ? "text-warn" : "text-good");
    
    document.getElementById("abuse-confidence").textContent = `${confidence}%`;
    document.getElementById("abuse-reports").textContent = abuse.reports || 0;
    document.getElementById("abuse-last").textContent = abuse.last_report || "N/A";

    // 5. Render Geo Data
    const geo = data.geo || {};
    document.getElementById("geo-country").textContent = geo.country || "N/A";
    document.getElementById("geo-city").textContent = geo.city || "N/A";
    document.getElementById("geo-org").textContent = geo.org || "N/A";
    document.getElementById("geo-asn").textContent = geo.asn || "N/A";

    // Show map and threat profile containers
    document.getElementById("osint-map-container").classList.remove("hidden");
    document.getElementById("threat-profile-container").classList.remove("hidden");

    // Important: Invalidate map size after container is unhidden
    setTimeout(() => {
      if (osintMap) {
        osintMap.invalidateSize();
      }
    }, 100);

    // 6. Render Threat Profile
    const shodanResults = document.getElementById("shodan-results");
    if (data.shodan) {
      if (data.shodan.error) {
        shodanResults.innerHTML = `<p class="text-bad">Error: ${data.shodan.error}</p>`;
      } else if (data.shodan.ports) {
        shodanResults.innerHTML = `
          <p><strong>Hostnames:</strong> ${(data.shodan.hostnames || []).join(", ") || "N/A"}</p>
          <p><strong>Country:</strong> ${data.shodan.country_name || "N/A"}</p>
          <p><strong>Organization:</strong> ${data.shodan.org || "N/A"}</p>
          <p><strong>Open Ports:</strong> ${(data.shodan.ports || []).join(", ") || "None"}</p>
          <p><strong>Last Update:</strong> ${data.shodan.last_update || "N/A"}</p>
        `;
      } else {
        shodanResults.textContent = "No Shodan data available for this IP address.";
      }
    } else {
      shodanResults.textContent = "No Shodan data available for this IP address.";
    }

    const dnsResults = document.getElementById("dns-results");
    if (data.dns && Object.keys(data.dns).length > 0) {
      dnsResults.innerHTML = Object.entries(data.dns)
        .filter(([type, records]) => records && records.length > 0)
        .map(([type, records]) => `<p><strong>${type}:</strong> ${records.join(", ")}</p>`)
        .join("");
      if (dnsResults.innerHTML === "") {
        dnsResults.textContent = "No DNS records found for this target.";
      }
    } else {
      dnsResults.textContent = "No DNS data available.";
    }

    const whoisResults = document.getElementById("whois-results");
    if (data.whois) {
      whoisResults.innerHTML = `<pre>${JSON.stringify(data.whois, null, 2)}</pre>`;
    } else {
      whoisResults.textContent = "No WHOIS data available.";
    }

    setTimeout(() => { progressEl.style.width = "0%"; }, 1000);
    playBeep();
    saveState();
  } catch (err) {
    sysLog("OSINT", `Fatal error during analysis: ${err.message}`, "error");
    progressEl.style.width = "0%";
  }
});

// Remove configuration saving from frontend as keys are now hidden/backend-only
const configSaveBtn = document.getElementById("osint-save-config");
if (configSaveBtn) {
  configSaveBtn.parentElement.classList.add("hidden");
}

function renderOsintGraph(data) {
  const svg = document.getElementById("osint-graph");
  if (!svg) return;
  svg.innerHTML = "";
  const nodes = data.nodes || [];
  const edges = data.edges || [];
  if (!nodes.length) return;
  const width = svg.clientWidth || 600;
  const height = svg.clientHeight || 260;
  const center = { x: width / 2, y: height / 2 };
  const root = nodes[0];
  const radius = Math.min(width, height) / 2 - 20;
  const positions = {};
  positions[root.id] = center;
  const leafNodes = nodes.slice(1);
  leafNodes.forEach((node, index) => {
    const angle = (index / Math.max(leafNodes.length, 1)) * Math.PI * 2;
    positions[node.id] = {
      x: center.x + Math.cos(angle) * radius,
      y: center.y + Math.sin(angle) * radius,
    };
  });
  edges.forEach((edge) => {
    const source = positions[edge.source] || center;
    const target = positions[edge.target] || center;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", source.x);
    line.setAttribute("y1", source.y);
    line.setAttribute("x2", target.x);
    line.setAttribute("y2", target.y);
    line.setAttribute("stroke", "rgba(34,211,238,0.4)");
    svg.appendChild(line);
  });
  nodes.forEach((node) => {
    const pos = positions[node.id] || center;
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", pos.x);
    circle.setAttribute("cy", pos.y);
    circle.setAttribute("r", node.id === root.id ? 18 : 10);
    circle.setAttribute("fill", "rgba(34,211,238,0.8)");
    svg.appendChild(circle);
  });
}

let osintMarker;
function renderOsintMap(geo) {
  const mapEl = document.getElementById("osint-map");
  if (!mapEl || !window.L) return;
  if (!geo || geo.lat == null || geo.lon == null) {
    if (osintMap) {
      osintMap.setView([0, 0], 1);
      if (osintMarker) {
        osintMap.removeLayer(osintMarker);
        osintMarker = null;
      }
    }
    return;
  }
  if (!osintMap) {
    osintMap = L.map("osint-map", { zoomControl: false });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "",
    }).addTo(osintMap);
  }
  osintMap.setView([geo.lat, geo.lon], 6);
  if (osintMarker) {
    osintMarker.setLatLng([geo.lat, geo.lon]);
  } else {
    osintMarker = L.marker([geo.lat, geo.lon]).addTo(osintMap);
  }
}



function addHistoryItem(text) {
  const timeline = document.getElementById("history-timeline");
  const item = document.createElement("div");
  item.className = "timeline-item";
  item.innerHTML = `<p class="text-xs text-cyan-300">${new Date().toLocaleTimeString()}: ${text}</p>`;
  timeline.prepend(item);
  if (timeline.children.length > 10) {
    timeline.lastChild.remove();
  }
  
  // Update jobs count
  const jobsCount = document.getElementById("jobs-count");
  if (jobsCount) {
    let count = parseInt(jobsCount.textContent) || 0;
    jobsCount.textContent = count + 1;
  }
}

function matrixEffect() {
  const canvas = document.getElementById("matrix");
  const ctx = canvas.getContext("2d");
  const resize = () => {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  };
  resize();
  window.addEventListener("resize", resize);
  const letters = "01⌁⟟⟁⟠⟡⟣";
  const fontSize = 14;
  const columns = Math.floor(canvas.width / fontSize);
  const drops = Array(columns).fill(1);
  const draw = () => {
    ctx.fillStyle = "rgba(0, 0, 0, 0.08)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#22d3ee";
    ctx.font = `${fontSize}px monospace`;
    drops.forEach((y, index) => {
      const text = letters[Math.floor(Math.random() * letters.length)];
      ctx.fillText(text, index * fontSize, y * fontSize);
      if (y * fontSize > canvas.height && Math.random() > 0.975) {
        drops[index] = 0;
      }
      drops[index]++;
    });
    requestAnimationFrame(draw);
  };
  draw();
}
function saveState() {
  // Only persist user preferences - scan results always start fresh each session
  const prefs = { sound: state.sound };
  localStorage.setItem("netsecPrefs", JSON.stringify(prefs));
}

function loadState() {
  // Restore only preferences, never scan results
  const prefs = localStorage.getItem("netsecPrefs");
  if (prefs) {
    try { const p = JSON.parse(prefs); state.sound = p.sound || false; } catch(e) {}
  }
  localStorage.removeItem("netsecState"); // clear any old stale format
}


function initLiveAttackMap() {
  // Update real-time clock
  setInterval(() => {
    const timeDisplay = document.getElementById("current-time-display");
    if (timeDisplay) {
      const now = new Date();
      timeDisplay.textContent = now.toISOString().split('T')[1].replace('Z', '') + " [" + Math.random().toString(36).substring(7).toUpperCase() + "]";
    }
  }, 100);

  const threatIntelFeed = document.getElementById("threat-intel-feed");
  
  // Fetch Threat Intel Feed
  async function fetchThreatIntel() {
    try {
      const response = await fetch('/api/threat-intel/feed');
      const data = await response.json();
      if (data.feed && data.feed.length > 0) {
        threatIntelFeed.innerHTML = data.feed.map(item => `
          <div class="timeline-item mb-3">
            <a href="${item.link}" target="_blank" class="text-xs text-cyan-300 hover:text-cyan-100 transition-colors block">
              <i class="fas fa-exclamation-triangle text-warn mr-2"></i>${item.title}
            </a>
            <div class="text-[9px] text-slate-500 mt-1 ml-5">${item.pub_date || "Live Update"}</div>
          </div>
        `).join("");
      } else {
        threatIntelFeed.innerHTML = '<div class="text-xs text-cyan-500/50">Awaiting intelligence feed...</div>';
      }
    } catch (error) {
      console.error("Failed to fetch threat intel", error);
    }
  }

  // Fetch Dashboard Live Stats
  async function fetchDashboardStats() {
    try {
      const response = await fetch('/api/dashboard/live-stats');
      const data = await response.json();
      
      const gtEl = document.getElementById("global-threat-level");
      if (gtEl && data.global_threat) {
        gtEl.textContent = data.global_threat;
        gtEl.className = "stat-value " + (data.global_threat === "LOW" ? "text-good" : (data.global_threat === "ELEVATED" ? "text-warn" : "text-bad"));
      }

      const tcveEl = document.getElementById("total-cve");
      if (tcveEl && data.total_cve) tcveEl.textContent = data.total_cve.toLocaleString();
      
      const jobsEl = document.getElementById("jobs-count");
      if (jobsEl && data.jobs_completed !== undefined) jobsEl.textContent = data.jobs_completed;

      const healthEl = document.getElementById("scanner-health");
      if (healthEl && data.scanner_health) healthEl.textContent = data.scanner_health;
      
    } catch (error) {
      console.error("Failed to fetch dashboard stats", error);
    }
  }

  // Fetch SOC Feed — multi-source: CISA KEV + Feodo Tracker + AbuseIPDB
  async function fetchSOCFeed() {
    try {
      const response = await fetch('/api/soc/feed');
      const data = await response.json();
      const hudEl = document.getElementById("soc-hud-feed");
      if (!hudEl) return;
      
      if (data.feed && data.feed.length > 0) {
        // Source color scheme
        const sourceColors = {
          "CISA-KEV":      { accent: "#f87171", bg: "rgba(239,68,68,0.06)",  icon: "fa-shield-alt",        label: "CISA KEV" },
          "Feodo-Tracker": { accent: "#fb923c", bg: "rgba(251,146,60,0.06)", icon: "fa-spider",             label: "C2 Tracker" },
          "AbuseIPDB":     { accent: "#e879f9", bg: "rgba(232,121,249,0.06)",icon: "fa-exclamation-circle", label: "AbuseIPDB" },
        };

        hudEl.innerHTML = data.feed.map((item, i) => {
          const delay  = i * 0.05;
          const sc     = sourceColors[item.source] || sourceColors["AbuseIPDB"];
          const tags   = (item.tags || []).filter(t => t && t.length > 0).slice(0, 3);
          const cve    = item.cve || "";
          const detail = item.detail || "";

          return `
            <div class="opacity-0 animate-[fadeIn_0.4s_ease-out_forwards]" style="
              animation-delay:${delay}s;
              background:${sc.bg};
              border:1px solid ${sc.accent}22;
              border-left: 3px solid ${sc.accent};
              border-radius:8px;
              padding:9px 11px;
              display:flex;
              flex-direction:column;
              gap:4px;
              font-family:monospace;
              transition: border-color .2s, box-shadow .2s;
            " onmouseenter="this.style.borderColor='${sc.accent}55';this.style.boxShadow='0 0 12px ${sc.accent}18'"
               onmouseleave="this.style.borderColor='${sc.accent}22';this.style.boxShadow='none'">

              <!-- Row 1: Source label + timestamp -->
              <div style="display:flex;align-items:center;justify-content:space-between;gap:6px">
                <span style="background:${sc.accent}15;color:${sc.accent};font-size:7px;font-weight:800;text-transform:uppercase;letter-spacing:.12em;padding:1px 6px;border-radius:3px">
                  <i class="fas ${sc.icon}" style="margin-right:2px;font-size:7px"></i>${sc.label}
                </span>
                <span style="font-size:7px;color:rgba(255,255,255,0.2)">${(item.timestamp||"").slice(0,10)}</span>
              </div>

              <!-- Row 2: Host / CVE -->
              <div style="font-size:11px;color:${sc.accent};font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${item.host||""}">
                ${cve ? `<span style="background:rgba(239,68,68,0.12);color:#f87171;font-size:8px;font-weight:800;padding:1px 5px;border-radius:3px;margin-right:5px;border:1px solid rgba(239,68,68,0.2)">${cve}</span>` : ""}${item.host||"Unknown"}
              </div>

              <!-- Row 3: Detail (truncated) -->
              ${detail ? `<div style="font-size:9px;color:rgba(255,255,255,0.3);line-height:1.4;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${detail}">${detail}</div>` : ""}

              <!-- Row 4: Tags -->
              ${tags.length ? `<div style="display:flex;flex-wrap:wrap;gap:3px;margin-top:1px">
                ${tags.map(t => `<span style="background:${sc.accent}10;color:${sc.accent};font-size:7px;padding:1px 5px;border-radius:3px;border:1px solid ${sc.accent}18;opacity:0.7">${t}</span>`).join("")}
              </div>` : ""}
            </div>
          `;
        }).join("");
      } else {
        hudEl.innerHTML = `<div class="col-span-full text-center text-fuchsia-500/30 text-xs font-mono py-8">
          <i class="fas fa-satellite-dish text-2xl mb-2 block opacity-30"></i>
          Connecting to threat intelligence network...
        </div>`;
      }
    } catch (error) {
      console.error("Failed to fetch SOC feed", error);
      const hudEl = document.getElementById("soc-hud-feed");
      if (hudEl) hudEl.innerHTML = `<div class="col-span-full text-center text-fuchsia-500/30 text-xs font-mono py-6">SOC feed connection error — retrying...</div>`;
    }
  }


  // Initial fetches
  fetchThreatIntel();
  fetchDashboardStats();
  fetchSOCFeed();
  
  // Polling
  setInterval(fetchThreatIntel, 120000); // 2 minutes
  setInterval(fetchDashboardStats, 30000); // 30 seconds
  setInterval(fetchSOCFeed, 45000); // 45 seconds
}

matrixEffect();
loadState();
document.getElementById("subdomain-btn").addEventListener("click", async () => {
  const domain = document.getElementById("subdomain-input").value;
  const progressEl = document.getElementById("subdomain-progress");
  const resultsEl = document.getElementById("subdomain-results");

  if (!domain) return alert("Domain required");

  addHistoryItem(`Started subdomain recon on ${domain}`);
  sysLog("SCAN", `Fetching subdomains for: ${domain}...`);
  progressEl.style.width = "20%";
  resultsEl.textContent = "Querying HackerTarget & crt.sh (this may take a moment)...";

  try {
    const response = await fetch("/api/scan/subdomains", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ domain }),
    });
    
    progressEl.style.width = "70%";
    const data = await response.json();
    
    if (!response.ok) {
      sysLog("SCAN", `Subdomain recon failed: ${data.error || "Unknown error"}`, "error");
      resultsEl.textContent = `Error: ${data.error || "Unknown error"}`;
      progressEl.style.width = "0%";
      return;
    }
    
    progressEl.style.width = "100%";
    const count = data.subdomains.length;
    sysLog("SCAN", `Found ${count} subdomains for ${domain}`, "success");
    
    if (count > 0) {
      resultsEl.innerHTML = data.subdomains.map(sub => `<div>${sub}</div>`).join("");
      state.subdomainResults[domain] = data.subdomains;
    } else {
      resultsEl.textContent = "No subdomains found for this domain.";
      state.subdomainResults[domain] = [];
    }

    setTimeout(() => { progressEl.style.width = "0%"; }, 2000);
    playBeep();
    saveState();
  } catch (err) {
    sysLog("SCAN", `Fatal error during subdomain recon: ${err.message}`, "error");
    resultsEl.textContent = `Fatal error: ${err.message}`;
    progressEl.style.width = "0%";
  }
});

document.getElementById("adv-intel-btn").addEventListener("click", async () => {
  const target = document.getElementById("adv-intel-input").value;
  const resultsEl = document.getElementById("adv-intel-results");

  if (!target) return alert("Target required");

  addHistoryItem(`Started Advanced Recon on ${target}`);
  sysLog("OSINT", `Initiating Deep Recon for: ${target}...`);
  
  resultsEl.classList.remove("hidden");
  resultsEl.innerHTML = `
    <div class="col-span-full flex flex-col items-center py-10">
      <div class="w-16 h-16 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin mb-4"></div>
      <div class="text-cyan-400 animate-pulse uppercase tracking-widest text-sm">Gathering Intelligence from multiple sources...</div>
    </div>
  `;

  try {
    const response = await fetch("/api/intel/advanced", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target }),
    });
    
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Recon failed");
    
    state.advIntelResults[target] = data;
    resultsEl.innerHTML = "";
    sysLog("OSINT", `Deep Recon completed for ${target}`, "success");

    // ── Branded tool cards ───────────────────────────────────────
    const TOOL_META = {
      censys:    { label:"Censys",          bg:"#0d1b2a", accent:"#00d2ff", svgPath:'<circle cx="20" cy="20" r="14" stroke="#00d2ff" stroke-width="2.5" fill="none"/><path d="M13 20a7 7 0 1 1 14 0" stroke="#00d2ff" stroke-width="2" stroke-linecap="round" fill="none"/><circle cx="20" cy="20" r="2.5" fill="#00d2ff"/>' },
      otx:       { label:"AlienVault OTX",  bg:"#1a0a0a", accent:"#e8343a", svgPath:'<polygon points="20,5 35,32 5,32" stroke="#e8343a" stroke-width="2.5" fill="none" stroke-linejoin="round"/><line x1="20" y1="15" x2="20" y2="24" stroke="#e8343a" stroke-width="2.5" stroke-linecap="round"/><circle cx="20" cy="28" r="1.5" fill="#e8343a"/>' },
      ipinfo:    { label:"IPinfo.io",        bg:"#071830", accent:"#4f9df7", svgPath:'<circle cx="20" cy="20" r="14" stroke="#4f9df7" stroke-width="2.5" fill="none"/><circle cx="20" cy="14" r="2" fill="#4f9df7"/><line x1="20" y1="19" x2="20" y2="28" stroke="#4f9df7" stroke-width="2.5" stroke-linecap="round"/>' },
      pulsedive: { label:"Pulsedive",        bg:"#11012a", accent:"#a855f7", svgPath:'<path d="M20 6 Q32 13 32 20 Q32 30 20 34 Q8 30 8 20 Q8 13 20 6Z" stroke="#a855f7" stroke-width="2.5" fill="none"/><circle cx="20" cy="20" r="3" fill="#a855f7"/>' },
      onyphe:    { label:"Onyphe",           bg:"#020f1f", accent:"#38bdf8", svgPath:'<rect x="9" y="9" width="22" height="22" rx="3" stroke="#38bdf8" stroke-width="2.5" fill="none"/><circle cx="20" cy="20" r="5" fill="#38bdf8" opacity="0.3"/><circle cx="20" cy="20" r="2" fill="#38bdf8"/>' },
      bgpview:   { label:"BGPView",          bg:"#041a04", accent:"#4ade80", svgPath:'<path d="M6 32 L20 8 L34 32" stroke="#4ade80" stroke-width="2.5" stroke-linejoin="round" fill="none"/><line x1="11" y1="23" x2="29" y2="23" stroke="#4ade80" stroke-width="2"/>' },
      whois:     { label:"WHOIS Lookup",     bg:"#1a0f00", accent:"#fb923c", svgPath:'<rect x="9" y="5" width="22" height="30" rx="3" stroke="#fb923c" stroke-width="2.5" fill="none"/><line x1="13" y1="13" x2="27" y2="13" stroke="#fb923c" stroke-width="2"/><line x1="13" y1="19" x2="27" y2="19" stroke="#fb923c" stroke-width="2"/><line x1="13" y1="25" x2="21" y2="25" stroke="#fb923c" stroke-width="2"/>' },
      threatfox: { label:"ThreatFox IOCs",   bg:"#1f0000", accent:"#f87171", svgPath:'<path d="M20 5 C10 5 7 14 12 20 C7 23 9 33 20 35 C31 33 33 23 28 20 C33 14 30 5 20 5Z" stroke="#f87171" stroke-width="2.5" fill="none"/><circle cx="20" cy="21" r="3" fill="#f87171"/>' },
      urlhaus:   { label:"URLhaus Malware",  bg:"#1f0015", accent:"#f472b6", svgPath:'<path d="M8 20 Q14 8 20 8 Q26 8 32 20 Q26 32 20 32 Q14 32 8 20Z" stroke="#f472b6" stroke-width="2.5" fill="none"/><path d="M16 20 L24 20 M20 16 L20 24" stroke="#f472b6" stroke-width="2" stroke-linecap="round"/>' },
      robtex:    { label:"Robtex Network",   bg:"#001a1a", accent:"#2dd4bf", svgPath:'<circle cx="20" cy="9" r="3.5" stroke="#2dd4bf" stroke-width="2"/><circle cx="9" cy="29" r="3.5" stroke="#2dd4bf" stroke-width="2"/><circle cx="31" cy="29" r="3.5" stroke="#2dd4bf" stroke-width="2"/><line x1="20" y1="12.5" x2="9" y2="25.5" stroke="#2dd4bf" stroke-width="1.5"/><line x1="20" y1="12.5" x2="31" y2="25.5" stroke="#2dd4bf" stroke-width="1.5"/><line x1="12.5" y1="29" x2="27.5" y2="29" stroke="#2dd4bf" stroke-width="1.5"/>' },
    };

    const createBrandedCard = (key, contentLines) => {
      const meta = TOOL_META[key] || { label:key, bg:"#111827", accent:"#6b7280", svgPath:"" };
      const card = document.createElement("div");
      card.className = "relative overflow-hidden rounded-xl flex flex-col";
      card.style.cssText = `background:${meta.bg}; border:1px solid ${meta.accent}30; box-shadow:0 4px 24px ${meta.accent}18, inset 0 1px 0 ${meta.accent}15;`;
      card.innerHTML = `
        <div class="flex items-center gap-3 px-4 py-3 border-b" style="border-color:${meta.accent}20; background:${meta.accent}0a;">
          <svg width="28" height="28" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" class="shrink-0">${meta.svgPath}</svg>
          <div class="min-w-0">
            <div class="font-bold text-xs tracking-widest uppercase" style="color:${meta.accent}">${meta.label}</div>
            <div style="color:${meta.accent}60" class="text-[9px] uppercase tracking-widest">Threat Intelligence</div>
          </div>
          <div class="ml-auto w-1.5 h-1.5 rounded-full animate-pulse shrink-0" style="background:${meta.accent}"></div>
        </div>
        <div class="p-4 text-[11px] font-mono leading-relaxed overflow-auto max-h-72" style="color:${meta.accent}b0; scrollbar-width:thin; scrollbar-color:${meta.accent}30 transparent;">${contentLines}</div>
      `;
      return card;
    };

    const fmtObj = (obj) => {
      if (typeof obj === "string") return obj.replace(/\n/g, "<br>");
      return JSON.stringify(obj, null, 2).replace(/\n/g,"<br>").replace(/ /g,"&nbsp;");
    };

    if (data.censys) {
      const svcs = data.censys?.result?.services || [];
      const content = svcs.length
        ? svcs.map(s => `<b>Port ${s.port||"?"}</b> · ${s.service_name||"?"} [${s.transport_protocol||"?"}]${s.banner ? "<br>&nbsp;&nbsp;"+s.banner.slice(0,120) : ""}`).join("<br><br>")
        : fmtObj(data.censys);
      resultsEl.appendChild(createBrandedCard("censys", content));
    }
    if (data.otx) {
      const pc = data.otx?.pulse_info?.count||0;
      const badge = pc > 0 ? `<span style="color:#f87171;font-weight:bold"> ⚠ ${pc} PULSES FLAGGED</span>` : `<span style="color:#4ade80"> ✓ CLEAN</span>`;
      const content = `<b>Indicator</b>: ${data.otx.indicator||"-"}<br><b>Type</b>     : ${data.otx.type||"-"}<br><b>Country</b>  : ${data.otx.country_name||"-"}<br><b>Reputation</b>: ${data.otx.reputation??"-"}<br><b>Pulses</b>   : ${badge}`;
      resultsEl.appendChild(createBrandedCard("otx", content));
    }
    if (data.ipinfo) {
      const i = data.ipinfo;
      const content = `<b>IP</b>      : ${i.ip||"-"}<br><b>Hostname</b>: ${i.hostname||"-"}<br><b>City</b>    : ${i.city||"-"}<br><b>Region</b>  : ${i.region||"-"}<br><b>Country</b> : ${i.country||"-"}<br><b>Org/AS</b>  : ${i.org||"-"}<br><b>Timezone</b>: ${i.timezone||"-"}<br><b>Location</b>: ${i.loc||"-"}`;
      resultsEl.appendChild(createBrandedCard("ipinfo", content));
    }
    if (data.pulsedive) {
      const content = `<b>Risk</b>     : ${data.pulsedive.risk||"-"}<br><b>Indicator</b>: ${data.pulsedive.indicator||"-"}<br><b>Type</b>     : ${data.pulsedive.type||"-"}<br><b>Last Seen</b>: ${data.pulsedive.stamp_seen||data.pulsedive.stamp_updated||"-"}`;
      resultsEl.appendChild(createBrandedCard("pulsedive", content));
    }
    if (data.onyphe) {
      resultsEl.appendChild(createBrandedCard("onyphe", fmtObj(data.onyphe)));
    }
    if (data.bgpview?.data) {
      const bgp = data.bgpview.data;
      const pfx = (bgp.prefixes||bgp.ipv4_prefixes||[]).slice(0,8).map(p=>p.prefix||p).join(", ");
      const asns2 = (bgp.asns||[]).map(a=>`AS${a.asn}`).join(", ");
      const content = `<b>Name</b>    : ${bgp.name||"-"}<br><b>ASNs</b>    : ${asns2||"-"}<br><b>Prefixes</b>: ${pfx||"-"}`;
      resultsEl.appendChild(createBrandedCard("bgpview", content));
    }
    if (data.whois?.data) {
      resultsEl.appendChild(createBrandedCard("whois", (data.whois.data||"").replace(/\n/g,"<br>")));
    }
    if (data.threatfox) {
      const iocs = Array.isArray(data.threatfox.data) ? data.threatfox.data : (data.threatfox.data ? [data.threatfox.data] : []);
      const content = iocs.length ? iocs.slice(0,8).map(ioc =>
        `<b>IOC</b>    : ${ioc.ioc||ioc.ioc_value||"-"}<br><b>Type</b>   : ${ioc.ioc_type||"-"}<br><b>Malware</b>: ${ioc.malware||ioc.malware_printable||"-"}<br><b>Conf</b>   : ${ioc.confidence_level||"-"}`
      ).join("<br><hr style='border-color:#f8717130;margin:6px 0'>") : "No IOCs found in ThreatFox database.";
      resultsEl.appendChild(createBrandedCard("threatfox", content));
    }
    if (data.urlhaus) {
      const urls = (data.urlhaus.urls||[]).slice(0,6);
      const content = `<b>Status</b>: ${data.urlhaus.query_status||"-"}&nbsp;&nbsp;<b>Found</b>: ${data.urlhaus.urls?.length||0} URLs<br><br>`+
        urls.map(u=>`<span style="color:#f472b6aa">${u.url_status||"?"}</span> ${u.url||"-"}`).join("<br>");
      resultsEl.appendChild(createBrandedCard("urlhaus", content));
    }
    if (data.robtex) {
      const content = `<b>AS</b>       : ${data.robtex.as||"-"}<br><b>AS Name</b>  : ${data.robtex.asname||"-"}<br><b>BGP Route</b>: ${data.robtex.bgproute||"-"}<br><b>Passive DNS</b>: ${(data.robtex.pas||[]).length} entries<br><b>Active DNS</b> : ${(data.robtex.act||[]).length} entries`;
      resultsEl.appendChild(createBrandedCard("robtex", content));
    }

    // ── Separator: "Nothing Found" cards for tools with no data ─────────
    const TOOL_ORDER = ["censys","otx","ipinfo","pulsedive","onyphe","bgpview","whois","threatfox","urlhaus","robtex"];
    const hasData = {
      censys: !!data.censys,
      otx: !!data.otx,
      ipinfo: !!data.ipinfo,
      pulsedive: !!data.pulsedive,
      onyphe: !!data.onyphe,
      bgpview: !!(data.bgpview?.data),
      whois: !!(data.whois?.data),
      threatfox: !!data.threatfox,
      urlhaus: !!data.urlhaus,
      robtex: !!data.robtex,
    };

    const missingTools = TOOL_ORDER.filter(k => !hasData[k]);

    if (missingTools.length > 0) {
      // Separator line
      const sep = document.createElement("div");
      sep.className = "col-span-full";
      sep.innerHTML = `
        <div style="display:flex;align-items:center;gap:12px;margin:18px 0 10px">
          <div style="flex:1;height:1px;background:linear-gradient(90deg,transparent,rgba(34,211,238,0.2))"></div>
          <span style="font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:rgba(34,211,238,0.35);white-space:nowrap">No Data Returned</span>
          <div style="flex:1;height:1px;background:linear-gradient(270deg,transparent,rgba(34,211,238,0.2))"></div>
        </div>`;
      resultsEl.appendChild(sep);

      missingTools.forEach(key => {
        const meta = TOOL_META[key] || { label: key, bg: "#0a0a0a", accent: "#444", svgPath: "" };
        const card = document.createElement("div");
        card.className = "relative overflow-hidden rounded-xl flex flex-col";
        card.style.cssText = `
          background:${meta.bg};
          border:1px solid ${meta.accent}20;
          box-shadow:0 2px 12px ${meta.accent}08;
          opacity:0.65;
        `;
        card.innerHTML = `
          <div style="display:flex;align-items:center;gap:10px;padding:10px 14px 8px;border-bottom:1px solid ${meta.accent}15;background:${meta.accent}07;">
            <svg width="22" height="22" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" style="flex-shrink:0;opacity:0.5">${meta.svgPath}</svg>
            <div style="min-width:0">
              <div style="font-size:9px;font-weight:700;letter-spacing:.15em;text-transform:uppercase;color:${meta.accent};opacity:0.7">${meta.label}</div>
              <div style="font-size:8px;color:${meta.accent};opacity:0.35;text-transform:uppercase;letter-spacing:.12em">Threat Intelligence</div>
            </div>
          </div>
          <div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:22px 16px 20px;gap:8px;">
            <!-- Big red X cross -->
            <div style="position:relative;width:52px;height:52px;flex-shrink:0">
              <svg viewBox="0 0 52 52" width="52" height="52" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="26" cy="26" r="24" stroke="rgba(239,68,68,0.18)" stroke-width="2" fill="rgba(239,68,68,0.06)"/>
                <line x1="14" y1="14" x2="38" y2="38" stroke="#ef4444" stroke-width="3.5" stroke-linecap="round"/>
                <line x1="38" y1="14" x2="14" y2="38" stroke="#ef4444" stroke-width="3.5" stroke-linecap="round"/>
              </svg>
            </div>
            <div style="font-size:15px;font-weight:800;letter-spacing:.04em;color:#ef4444;text-transform:uppercase;text-align:center;line-height:1.2">Nothing Found!</div>
            <div style="font-size:10px;color:rgba(255,255,255,0.2);text-align:center;line-height:1.4">No intelligence data returned<br>for this target from ${meta.label}</div>
          </div>
        `;
        resultsEl.appendChild(card);
      });
    }

    if (resultsEl.children.length === 0) {
      resultsEl.innerHTML = `<div class="col-span-full text-center text-slate-500 py-10">No data found from integrated tools for this target.</div>`;
    }

    playBeep();
    saveState();
  } catch (err) {
    sysLog("OSINT", `Deep Recon Error: ${err.message}`, "error");
    resultsEl.innerHTML = `<div class="col-span-full text-bad text-center py-10 font-bold">Error: ${err.message}</div>`;
  }
});


// --- Sandbox Browser Logic ---
let isProxyEnabled = false; // State for Proxy functionality

document.getElementById("sandbox-go").addEventListener("click", async () => {
  const urlInput = document.getElementById("sandbox-url");
  let url = urlInput.value.trim();
  
  if (!url) return alert("Please enter a URL to browse.");
  
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    url = "https://" + url;
    urlInput.value = url;
  }

  sysLog("SYSTEM", `Launching disposable Playwright sandbox for: ${url}`, "warn");
  addHistoryItem(`Launched Secure Sandbox Window: ${url}`);
  
  const frame = document.getElementById("sandbox-frame");
  const overlay = document.getElementById("sandbox-overlay");
  
  frame.src = "about:blank"; // reset
  overlay.style.opacity = "1";
  overlay.innerHTML = `<div class="text-fuchsia-500/60 font-mono flex flex-col items-center">
    <div class="w-12 h-12 border-4 border-fuchsia-500/20 border-t-fuchsia-500 rounded-full animate-spin mb-4"></div>
    <span class="tracking-[0.2em] uppercase">Spawning Isolated Browser Window...</span>
  </div>`;

  try {
    const response = await fetch("/api/sandbox/launch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url, use_proxy: isProxyEnabled }),
    });

    const data = await response.json();
    if (response.ok) {
      overlay.innerHTML = `<div class="text-fuchsia-500/60 font-mono flex flex-col items-center">
        <i class="fas fa-check-circle text-6xl mb-4 text-good"></i>
        <span class="tracking-[0.2em] uppercase">Browser Launched Externally</span>
        <span class="text-[10px] mt-2 opacity-50">You can safely use the detached window.</span>
      </div>`;
    } else {
      throw new Error(data.error || "Failed to launch browser");
    }
  } catch (e) {
    overlay.innerHTML = `<div class="text-bad font-mono flex flex-col items-center">
      <i class="fas fa-times-circle text-6xl mb-4"></i>
      <span class="tracking-[0.2em] uppercase">Launch Error</span>
      <span class="text-xs mt-2">${e.message}</span>
    </div>`;
  }
});

document.getElementById("sandbox-clear").addEventListener("click", async () => {
  const frame = document.getElementById("sandbox-frame");
  const overlay = document.getElementById("sandbox-overlay");
  const urlInput = document.getElementById("sandbox-url");
  
  sysLog("SYSTEM", "Requesting backend to destroy sandbox session.");
  
  try {
    await fetch("/api/sandbox/destroy", { method: "POST" });
  } catch (e) {}
  
  frame.src = "about:blank";
  urlInput.value = "";
  
  overlay.style.display = "flex";
  setTimeout(() => overlay.style.opacity = "1", 10);
  overlay.innerHTML = `<div class="text-fuchsia-500/60 font-mono flex flex-col items-center">
    <i class="fas fa-shield-alt text-6xl mb-4 animate-pulse"></i>
    <span class="tracking-[0.3em] uppercase">Secure Sandbox Environment</span>
    <span class="text-[10px] mt-2 opacity-50">Session Destroyed. Awaiting Target URL...</span>
  </div>`;
  
  sysLog("SYSTEM", "Sandbox session destroyed and memory wiped.");
});

document.getElementById("sandbox-fullscreen").addEventListener("click", () => {
  const frame = document.getElementById("sandbox-frame");
  if (frame.requestFullscreen) {
    frame.requestFullscreen();
  } else if (frame.mozRequestFullScreen) { /* Firefox */
    frame.mozRequestFullScreen();
  } else if (frame.webkitRequestFullscreen) { /* Chrome, Safari and Opera */
    frame.webkitRequestFullscreen();
  } else if (frame.msRequestFullscreen) { /* IE/Edge */
    frame.msRequestFullscreen();
  }
  sysLog("SYSTEM", "Toggled sandbox iframe fullscreen mode.");
});

document.getElementById("sandbox-proxy").addEventListener("click", (event) => {
  isProxyEnabled = !isProxyEnabled;
  const proxyButton = event.currentTarget;
  const proxySpan = proxyButton.querySelector("span");
  if (isProxyEnabled) {
    proxySpan.textContent = "ON";
    proxyButton.classList.remove("text-blue-400", "border-blue-400");
    proxyButton.classList.add("text-green-400", "border-green-400");
    sysLog("SYSTEM", "Fast IP Rotation enabled for disposable browser.", "warn");
  } else {
    proxySpan.textContent = "OFF";
    proxyButton.classList.remove("text-green-400", "border-green-400");
    proxyButton.classList.add("text-blue-400", "border-blue-400");
    sysLog("SYSTEM", "IP Rotation disabled for sandbox.", "info");
  }
});

let sandboxStatusInterval;
function startSandboxStatusPolling() {
  if (sandboxStatusInterval) clearInterval(sandboxStatusInterval);
  sandboxStatusInterval = setInterval(async () => {
    try {
      const res = await fetch("/api/sandbox/status");
      const data = await res.json();
      const statusEl = document.getElementById("sandbox-status-display");
      if (statusEl) {
        if (data.active) {
          if (isProxyEnabled) {
             statusEl.innerHTML = `<span class="text-green-400 font-bold">Active</span> <span class="mx-2 opacity-50">|</span> <span class="text-blue-300">Proxy: ${data.current_proxy || "Fetching..."}</span> <span class="mx-2 opacity-50">|</span> <span class="text-orange-300">Next Rotation: ${data.time_left}s</span>`;
          } else {
             statusEl.innerHTML = `<span class="text-green-400 font-bold">Active</span> <span class="mx-2 opacity-50">|</span> <span class="text-slate-400">Direct Connection (No Proxy)</span>`;
          }
        } else {
          statusEl.innerHTML = `<span class="text-slate-500">Inactive</span>`;
        }
      }
    } catch (e) {}
  }, 1000);
}
startSandboxStatusPolling();

initLiveAttackMap();

// ── Feature Ideas Lab ─────────────────────────────────────────

// ---- Shared Intelligence Utilities ---------------------------------

function timeAgo(utc) {
  if (!utc) return "";
  const d = Math.floor((Date.now()/1000) - utc);
  if (d < 60)      return d + "s";
  if (d < 3600)    return Math.floor(d/60) + "m";
  if (d < 86400)   return Math.floor(d/3600) + "h";
  if (d < 2592000) return Math.floor(d/86400) + "d";
  return Math.floor(d/2592000) + "mo";
}
function fmt(n) {
  if (!n) return "0";
  return n >= 1000 ? (n/1000).toFixed(1)+"k" : String(n);
}
function stripMd(text) {
  return (text||"")
    .replace(/\*\*|__/g,"").replace(/\*|_/g,"").replace(/^#{1,6}\s/gm,"")
    .replace(/^[|].*$/gm,"").replace(/^[-=]{3,}$/gm,"")
    .replace(/\n{3,}/g,"\n\n").trim();
}
function intelSpinner(color) {
  return `<div style="padding:48px;text-align:center">
    <div style="width:44px;height:44px;border:3px solid ${color}22;border-top-color:${color};border-radius:50%;animation:spin 0.7s linear infinite;margin:0 auto 14px"></div>
    <div style="color:${color};font-size:11px;text-transform:uppercase;letter-spacing:0.12em;opacity:0.8">Searching...</div>
  </div>`;
}

// ---- Reddit Intelligence Tab ----------------------------------------

let redditPosts = [];

// ---- Google Dork Intelligence Tab -----------------------------------

let googleResults = [];

function buildGoogleCard(result) {
  const color = "#4285F4";
  const icons = {"Google":"🔵","Bing":"🟠","DDG":"🟡"};
  const engLabel = (result.engines||"").split(",")[0].trim();

  const card = document.createElement("div");
  card.className = "relative overflow-hidden";
  card.style.cssText = `
    background:#0d1117;border:1px solid rgba(66,133,244,0.18);border-radius:12px;
    box-shadow:0 2px 20px rgba(66,133,244,0.06),inset 0 1px 0 rgba(66,133,244,0.05);
    transition:border-color 0.2s,box-shadow 0.2s;
  `;
  card.onmouseenter = () => {
    card.style.borderColor = "rgba(66,133,244,0.45)";
    card.style.boxShadow = "0 4px 28px rgba(66,133,244,0.14)";
  };
  card.onmouseleave = () => {
    card.style.borderColor = "rgba(66,133,244,0.18)";
    card.style.boxShadow = "0 2px 20px rgba(66,133,244,0.06)";
  };

  const urlObj = (() => { try { return new URL(result.url); } catch(e) { return null; } })();
  const domain = urlObj ? urlObj.hostname : result.url;

  card.innerHTML = `
    <div style="height:2px;background:linear-gradient(90deg,#4285F4,#34A853,#FBBC05,#EA4335);border-radius:12px 12px 0 0"></div>
    <div style="padding:14px 16px 12px">
      <!-- Domain + engine -->
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
        <img src="https://www.google.com/s2/favicons?domain=${domain}&sz=16" style="width:16px;height:16px;border-radius:3px" onerror="this.style.display='none'">
        <span style="font-size:11px;color:#4285F4;font-weight:500">${domain}</span>
        <span style="margin-left:auto;font-size:10px;background:rgba(66,133,244,0.1);color:#4285F4;padding:1px 7px;border-radius:10px">${engLabel}</span>
      </div>

      <!-- Title -->
      <a href="${result.url}" target="_blank" rel="noopener noreferrer"
        style="display:block;font-size:14px;font-weight:600;color:#D7DADC;text-decoration:none;line-height:1.45;margin-bottom:7px;transition:color 0.15s"
        onmouseenter="this.style.color='#4285F4'" onmouseleave="this.style.color='#D7DADC'">
        ${result.title||result.url}
      </a>

      <!-- Snippet -->
      ${result.snippet ? `<p style="font-size:12px;color:#8899a6;line-height:1.6;margin-bottom:10px">${result.snippet.slice(0,300).replace(/</g,"&lt;")}${result.snippet.length>300?"…":""}</p>` : ""}

      <!-- Meta bar -->
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
        <a href="${result.url}" target="_blank" rel="noopener noreferrer"
          style="display:flex;align-items:center;gap:5px;font-size:11px;font-weight:600;color:#818384;text-decoration:none;padding:4px 8px;border-radius:4px;transition:background 0.15s"
          onmouseenter="this.style.background='rgba(66,133,244,0.1)';this.style.color='#4285F4'" onmouseleave="this.style.background='transparent';this.style.color='#818384'">
          <i class="fas fa-external-link-alt" style="font-size:10px"></i> Open
        </a>
        ${result.published_date ? `<span style="font-size:10px;color:#818384"><i class="fas fa-calendar-alt" style="margin-right:4px;font-size:9px"></i>${result.published_date}</span>` : ""}
        ${result.score ? `<span style="font-size:10px;color:#818384;margin-left:auto">Score: ${result.score}</span>` : ""}
      </div>
    </div>`;
  return card;
}

document.getElementById("google-search-btn")?.addEventListener("click", async () => {
  const query       = (document.getElementById("google-query")?.value||"").trim();
  const progressEl  = document.getElementById("google-progress");
  const analyzeBtn  = document.getElementById("google-analyze-btn");
  const container   = document.getElementById("google-results-container");
  const grid        = document.getElementById("google-results-grid");
  const summaryPanel= document.getElementById("google-summary-panel");
  const countEl     = document.getElementById("google-count");
  if (!query) return alert("Please enter a search query or dork.");

  progressEl.style.width = "20%";
  summaryPanel.classList.add("hidden");
  analyzeBtn.style.display = "none";
  container.classList.remove("hidden");
  grid.innerHTML = intelSpinner("#4285F4");
  sysLog("OSINT","Google Dork searching: "+query,"info");

  try {
    progressEl.style.width = "50%";
    const res  = await fetch("/api/google/search",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query})});
    progressEl.style.width = "88%";
    const data = await res.json();
    if (!res.ok) throw new Error(data.error||"Search failed");
    googleResults = data.results||[];
    progressEl.style.width = "100%";
    countEl.textContent = googleResults.length + " results found";
    sysLog("OSINT","Found "+googleResults.length+" web results for: "+query,"success");
    grid.innerHTML="";
    if (!googleResults.length) {
      grid.innerHTML = `<div style="padding:40px;text-align:center;color:#818384">No results found. Try a different query or dork operator.</div>`;
    } else {
      googleResults.forEach(r => grid.appendChild(buildGoogleCard(r)));
      analyzeBtn.style.display = "";
    }
    setTimeout(()=>{progressEl.style.width="0%";},900);
  } catch(err) {
    sysLog("OSINT","Google error: "+err.message,"error");
    grid.innerHTML = `<div style="padding:30px;text-align:center;color:#ef4444">${err.message}</div>`;
    progressEl.style.width="0%";
  }
});

document.getElementById("google-analyze-btn")?.addEventListener("click", async () => {
  if (!googleResults.length) return;
  const panel = document.getElementById("google-summary-panel");
  const text  = document.getElementById("google-summary-text");
  const spin  = document.getElementById("google-summary-spinner");
  const query = (document.getElementById("google-query")?.value||"").trim();
  panel.classList.remove("hidden"); text.textContent=""; spin.classList.remove("hidden");
  sysLog("OSINT","ChatGPT analyzing "+googleResults.length+" Google results...","warn");
  try {
    const res  = await fetch("/api/google/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query,results:googleResults.slice(0,8).map(r=>({url:r.url,title:r.title,snippet:r.snippet}))})});
    const data = await res.json();
    spin.classList.add("hidden");
    if (!res.ok) throw new Error(data.error||"Analysis failed");
    text.textContent = stripMd(data.summary);
    sysLog("OSINT","ChatGPT Google summary done for: "+query,"success");
  } catch(err) {
    spin.classList.add("hidden"); text.textContent="Error: "+err.message;
    sysLog("OSINT","AI error: "+err.message,"error");
  }
});

document.getElementById("google-query")?.addEventListener("keypress",e=>{if(e.key==="Enter")document.getElementById("google-search-btn")?.click();});

// ── Reddit Cards (modern layout matching Reddit 2024 design) ─────────

function buildRedditCard(post) {
  const score    = post.score || 0;
  const ratio    = Math.round((post.upvote_ratio || 0) * 100);
  const age      = timeAgo(post.created_utc);
  const comments = post.comments || [];
  const AC       = "#FF4500";  // Reddit orange

  // Format score display
  function fmtK(n) {
    if (Math.abs(n) >= 1000) return (n/1000).toFixed(1) + "k";
    return String(n);
  }

  // Build top comments HTML
  const commentsHTML = comments.length ? `
    <div style="margin:10px 0 0;padding:10px 0 0;border-top:1px solid rgba(255,255,255,0.06)">
      <div style="font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:rgba(255,255,255,0.3);margin-bottom:8px">
        <svg style="vertical-align:-2px;margin-right:4px" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        Top Comments
      </div>
      ${comments.map(c => `
        <div style="display:flex;gap:8px;margin-bottom:8px">
          <div style="width:20px;height:20px;border-radius:50%;background:${AC};flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:800;color:#fff">
            ${(c.author||"?")[0].toUpperCase()}
          </div>
          <div style="flex:1;min-width:0">
            <span style="font-size:10px;font-weight:600;color:rgba(255,255,255,0.5)">u/${c.author||"?"}</span>
            <span style="font-size:10px;color:rgba(255,255,255,0.25);margin:0 4px">·</span>
            <span style="font-size:10px;color:${AC}">${fmtK(c.score||0)} pts</span>
            <p style="margin:3px 0 0;font-size:11px;color:rgba(255,255,255,0.45);line-height:1.5">${(c.body||"").replace(/</g,"&lt;").slice(0,200)}</p>
          </div>
        </div>`).join("")}
    </div>` : "";

  const card = document.createElement("div");
  card.style.cssText = [
    "background:#111318",
    "border:1px solid rgba(255,255,255,0.07)",
    "border-radius:16px",
    "overflow:hidden",
    "margin-bottom:0",
    "transition:border-color .18s, box-shadow .18s",
    "cursor:default",
  ].join(";");

  card.onmouseenter = () => {
    card.style.borderColor = "rgba(255,69,0,0.35)";
    card.style.boxShadow   = "0 6px 32px rgba(255,69,0,0.12)";
  };
  card.onmouseleave = () => {
    card.style.borderColor = "rgba(255,255,255,0.07)";
    card.style.boxShadow   = "none";
  };

  card.innerHTML = `
    <!-- Card body -->
    <div style="padding:16px 18px 12px">

      <!-- Row 1: subreddit + author + time  /  Reddit logo -->
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
        <div style="display:flex;align-items:center;gap:6px;font-size:11px;color:rgba(255,255,255,0.4)">
          <div style="width:20px;height:20px;border-radius:50%;background:${AC};display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <svg width="12" height="12" viewBox="0 0 20 20" fill="white">
              <circle cx="10" cy="10" r="10" fill="${AC}"/>
              <path d="M16.67 10a1.46 1.46 0 0 0-2.47-1 7.12 7.12 0 0 0-3.85-1.23l.65-3.07 2.13.45a1 1 0 1 0 1-.97 1 1 0 0 0-.96.68l-2.38-.5a.27.27 0 0 0-.32.2l-.73 3.44a7.14 7.14 0 0 0-3.89 1.23 1.46 1.46 0 1 0-1.61 2.39 2.87 2.87 0 0 0 0 .44c0 2.24 2.61 4.06 5.83 4.06s5.83-1.82 5.83-4.06a2.87 2.87 0 0 0 0-.44 1.46 1.46 0 0 0 .68-1.62zM7.27 11a1 1 0 1 1 1 1 1 1 0 0 1-1-1zm5.58 2.71a3.58 3.58 0 0 1-2.85.87 3.58 3.58 0 0 1-2.85-.87.19.19 0 0 1 .27-.27 3.24 3.24 0 0 0 2.58.71 3.24 3.24 0 0 0 2.58-.71.19.19 0 0 1 .27.27zm-.13-1.71a1 1 0 1 1 1-1 1 1 0 0 1-1 1z" fill="white"/>
            </svg>
          </div>
          <span style="font-weight:600;color:rgba(255,255,255,0.7)">${post.subreddit||"r/?"}</span>
          <span>·</span>
          <span>u/<b style="color:rgba(255,255,255,0.55)">${post.author||"?"}</b></span>
          <span>·</span>
          <span>${age} ago</span>
          ${post.link_flair ? `<span style="background:rgba(255,69,0,0.15);color:${AC};padding:1px 8px;border-radius:20px;font-size:9px;font-weight:700">${post.link_flair}</span>` : ""}
        </div>
        <!-- Reddit wordmark -->
        <svg width="60" height="20" viewBox="0 0 60 20" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="10" cy="10" r="10" fill="${AC}"/>
          <path d="M16.67 10a1.46 1.46 0 0 0-2.47-1 7.12 7.12 0 0 0-3.85-1.23l.65-3.07 2.13.45a1 1 0 1 0 1-.97 1 1 0 0 0-.96.68l-2.38-.5a.27.27 0 0 0-.32.2l-.73 3.44a7.14 7.14 0 0 0-3.89 1.23 1.46 1.46 0 1 0-1.61 2.39 2.87 2.87 0 0 0 0 .44c0 2.24 2.61 4.06 5.83 4.06s5.83-1.82 5.83-4.06a2.87 2.87 0 0 0 0-.44 1.46 1.46 0 0 0 .68-1.62zM7.27 11a1 1 0 1 1 1 1 1 1 0 0 1-1-1zm5.58 2.71a3.58 3.58 0 0 1-2.85.87 3.58 3.58 0 0 1-2.85-.87.19.19 0 0 1 .27-.27 3.24 3.24 0 0 0 2.58.71 3.24 3.24 0 0 0 2.58-.71.19.19 0 0 1 .27.27zm-.13-1.71a1 1 0 1 1 1-1 1 1 0 0 1-1 1z" fill="white"/>
          <text x="22" y="14" font-family="Verdana,sans-serif" font-weight="800" font-size="11" fill="rgba(255,255,255,0.85)">reddit</text>
        </svg>
      </div>

      <!-- Row 2: Title -->
      <a href="${post.url}" target="_blank" rel="noopener noreferrer"
        style="display:block;font-size:15px;font-weight:700;color:#fff;text-decoration:none;line-height:1.45;margin-bottom:8px;letter-spacing:-.01em"
        onmouseenter="this.style.color='${AC}'" onmouseleave="this.style.color='#fff'">
        ${post.title}
        ${!post.is_self && post.domain ? `<span style="font-size:10px;color:rgba(255,255,255,0.3);font-weight:400;margin-left:6px">(${post.domain})</span>` : ""}
      </a>

      <!-- Row 3: Body snippet -->
      ${post.selftext ? `<p style="font-size:12px;color:rgba(255,255,255,0.45);line-height:1.65;margin:0 0 10px">${post.selftext.slice(0,250).replace(/</g,"&lt;")}${post.selftext.length>250?"…":""}</p>` : ""}

      <!-- Top comments -->
      ${commentsHTML}
    </div>

    <!-- Action bar (Reddit-style) -->
    <div style="display:flex;align-items:center;gap:2px;padding:6px 10px 8px;border-top:1px solid rgba(255,255,255,0.05)">

      <!-- Vote group -->
      <div style="display:flex;align-items:center;background:rgba(255,255,255,0.05);border-radius:20px;padding:2px 4px;gap:2px;margin-right:4px">
        <!-- Upvote -->
        <button style="background:none;border:none;cursor:pointer;padding:4px 6px;border-radius:16px;display:flex;align-items:center;justify-content:center;transition:background .12s"
          onmouseenter="this.style.background='rgba(255,69,0,0.18)'" onmouseleave="this.style.background='none'">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="${AC}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="18 15 12 9 6 15"/>
          </svg>
        </button>
        <span style="font-size:12px;font-weight:700;color:rgba(255,255,255,0.75);min-width:24px;text-align:center">${fmtK(score)}</span>
        <!-- Downvote -->
        <button style="background:none;border:none;cursor:pointer;padding:4px 6px;border-radius:16px;display:flex;align-items:center;justify-content:center;transition:background .12s"
          onmouseenter="this.style.background='rgba(113,147,255,0.18)'" onmouseleave="this.style.background='none'">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.35)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>
      </div>

      <!-- Comments -->
      <a href="${post.url}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;display:flex;align-items:center;gap:5px;padding:5px 10px;border-radius:20px;font-size:11px;font-weight:600;color:rgba(255,255,255,0.4);transition:background .12s, color .12s"
        onmouseenter="this.style.background='rgba(255,255,255,0.07)';this.style.color='rgba(255,255,255,0.8)'" onmouseleave="this.style.background='transparent';this.style.color='rgba(255,255,255,0.4)'">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        ${fmtK(post.num_comments||0)}
      </a>

      <!-- Share -->
      <button style="display:flex;align-items:center;gap:5px;padding:5px 10px;border-radius:20px;font-size:11px;font-weight:600;color:rgba(255,255,255,0.4);background:none;border:none;cursor:pointer;transition:background .12s,color .12s"
        onmouseenter="this.style.background='rgba(255,255,255,0.07)';this.style.color='rgba(255,255,255,0.8)'" onmouseleave="this.style.background='transparent';this.style.color='rgba(255,255,255,0.4)'">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
          <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
        </svg>
        Share
      </button>

      <!-- Upvote ratio badge -->
      <span style="margin-left:auto;font-size:10px;color:rgba(255,255,255,0.25)">
        <svg style="vertical-align:-2px;margin-right:2px" width="10" height="10" viewBox="0 0 24 24" fill="${AC}"><polyline points="18 15 12 9 6 15" stroke="${AC}" stroke-width="2.5" stroke-linecap="round" fill="none"/></svg>
        ${ratio}%
      </span>
    </div>`;

  return card;
}

// ── Reddit sort state ─────────────────────────────────────────────
let redditSortMode = "relevant"; // "relevant" | "recent"
let redditLastQuery = "";

function computeRedditRelevance(post, queryWords) {
  const title = (post.title || "").toLowerCase();
  const body = (post.selftext || "").toLowerCase();
  const text = title + " " + body;
  let score = 0;
  queryWords.forEach((word, idx) => {
    const w = word.toLowerCase();
    if (!w || w.length < 2) return;
    // Title matches worth more
    const titleCount = (title.match(new RegExp("\\b" + w.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"), "g")) || []).length;
    const bodyCount  = (text.match(new RegExp("\\b" + w.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"), "g")) || []).length;
    // First query word (most important keyword) gets extra weight
    const weight = idx === 0 ? 4 : 2;
    score += titleCount * weight * 3 + bodyCount * weight;
  });
  // Exact full-phrase match bonus
  const phrase = queryWords.join(" ").toLowerCase();
  if (phrase.length > 3 && text.includes(phrase)) score += 20;
  return score;
}

function setRedditSort(mode) {
  redditSortMode = mode;
  const btnRel = document.getElementById("reddit-sort-relevant");
  const btnRec = document.getElementById("reddit-sort-recent");
  const AC = "#FF4500";
  if (btnRel && btnRec) {
    if (mode === "relevant") {
      btnRel.style.cssText = `background:rgba(255,69,0,0.18);color:${AC};border-color:${AC};padding:4px 12px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;border-radius:9999px;border-width:1px;border-style:solid;transition:all .15s`;
      btnRec.style.cssText = `background:transparent;color:rgba(255,69,0,0.45);border-color:rgba(255,69,0,0.25);padding:4px 12px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;border-radius:9999px;border-width:1px;border-style:solid;transition:all .15s`;
    } else {
      btnRec.style.cssText = `background:rgba(255,69,0,0.18);color:${AC};border-color:${AC};padding:4px 12px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;border-radius:9999px;border-width:1px;border-style:solid;transition:all .15s`;
      btnRel.style.cssText = `background:transparent;color:rgba(255,69,0,0.45);border-color:rgba(255,69,0,0.25);padding:4px 12px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;border-radius:9999px;border-width:1px;border-style:solid;transition:all .15s`;
    }
  }
  renderRedditPosts(redditLastQuery);
}

function renderRedditPosts(query) {
  const postsGrid = document.getElementById("reddit-posts-grid");
  if (!postsGrid || !redditPosts.length) return;

  const queryWords = query.trim().split(/\s+/).filter(w => w.length >= 2);

  let sorted = [...redditPosts];
  if (redditSortMode === "relevant") {
    // Compute relevance for each post
    sorted = sorted.map(p => ({ ...p, _relevance: computeRedditRelevance(p, queryWords) }));
    // Separate: posts with ANY match vs no match
    const matched   = sorted.filter(p => p._relevance > 0).sort((a, b) => b._relevance - a._relevance);
    const unmatched = sorted.filter(p => p._relevance === 0).sort((a, b) => b.score - a.score);
    sorted = [...matched, ...unmatched];
  } else {
    // Recent: sort by created_utc descending
    sorted = sorted.sort((a, b) => (b.created_utc || 0) - (a.created_utc || 0));
  }

  postsGrid.innerHTML = "";
  sorted.forEach(p => postsGrid.appendChild(buildRedditCard(p)));
}

document.getElementById("reddit-search-btn")?.addEventListener("click", async () => {
  const query        = (document.getElementById("reddit-query")?.value||"").trim();
  const progressEl   = document.getElementById("reddit-progress");
  const analyzeBtn   = document.getElementById("reddit-analyze-btn");
  const container    = document.getElementById("reddit-results-container");
  const postsGrid    = document.getElementById("reddit-posts-grid");
  const summaryPanel = document.getElementById("reddit-summary-panel");
  const countEl      = document.getElementById("reddit-count");
  if (!query) return alert("Please enter a search query.");

  redditLastQuery = query;
  // Reset sort to relevant on new search
  redditSortMode = "relevant";
  setRedditSort("relevant");

  progressEl.style.width = "20%";
  summaryPanel.classList.add("hidden");
  analyzeBtn.style.display = "none";
  container.classList.remove("hidden");
  postsGrid.innerHTML = intelSpinner("#FF4500");
  sysLog("OSINT", "Searching Reddit for: " + query, "info");

  try {
    progressEl.style.width = "55%";
    const res  = await fetch("/api/reddit/search",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query})});
    progressEl.style.width = "90%";
    const data = await res.json();
    if (!res.ok) throw new Error(data.error||"Search failed");
    redditPosts = data.posts||[];
    progressEl.style.width = "100%";
    countEl.textContent = redditPosts.length + " posts (last 3 years)";
    sysLog("OSINT","Found "+redditPosts.length+" Reddit posts (filtered to last 3 years)","success");
    postsGrid.innerHTML = "";
    if (!redditPosts.length) {
      postsGrid.innerHTML = `<div style="padding:40px;text-align:center;color:#818384">No Reddit posts found within the last 3 years. Try a different query.</div>`;
    } else {
      renderRedditPosts(query);
      analyzeBtn.style.display = "";
    }
    setTimeout(() => { progressEl.style.width = "0%"; }, 900);
  } catch(err) {
    sysLog("OSINT","Reddit error: "+err.message,"error");
    postsGrid.innerHTML = `<div style="padding:30px;text-align:center;color:#ef4444">${err.message}</div>`;
    progressEl.style.width = "0%";
  }
});


document.getElementById("reddit-analyze-btn")?.addEventListener("click", async () => {
  if (!redditPosts.length) return;
  const panel  = document.getElementById("reddit-summary-panel");
  const text   = document.getElementById("reddit-summary-text");
  const spin   = document.getElementById("reddit-summary-spinner");
  const query  = (document.getElementById("reddit-query")?.value||"").trim();
  panel.classList.remove("hidden"); text.textContent=""; spin.classList.remove("hidden");
  sysLog("OSINT","ChatGPT analyzing "+redditPosts.length+" posts...","warn");
  try {
    const res  = await fetch("/api/reddit/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query,posts:redditPosts.slice(0,10).map(p=>({url:p.url,title:p.title}))})});
    const data = await res.json();
    spin.classList.add("hidden");
    if (!res.ok) throw new Error(data.error||"Analysis failed");
    text.textContent = stripMd(data.summary);
    sysLog("OSINT","ChatGPT summary done","success");
  } catch(err) {
    spin.classList.add("hidden"); text.textContent="Error: "+err.message;
    sysLog("OSINT","AI error: "+err.message,"error");
  }
});

document.getElementById("reddit-query")?.addEventListener("keypress",e=>{if(e.key==="Enter")document.getElementById("reddit-search-btn")?.click();});

