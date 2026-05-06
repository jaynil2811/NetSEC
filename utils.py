# ============================================================
# SECTION: check_js_err.py
# ============================================================

from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        errors = []
        page.on("pageerror", lambda err: errors.append(f"Page Error: {err.message}"))
        page.on("console", lambda msg: errors.append(f"Console {msg.type}: {msg.text}") if msg.type in ['error', 'warning'] else None)
        
        print("Navigating to http://localhost:8000...")
        page.goto("http://localhost:8000")
        page.wait_for_timeout(2000)
        
        print("\n--- BROWSER ERRORS ---")
        for e in errors:
            print(e)
            
        browser.close()

if __name__ == "__main__":
    main()


# ============================================================
# SECTION: check_nav.py
# ============================================================

with open('templates/index.html','r',encoding='utf-8') as f:
    c = f.read()
import re
navs = re.findall(r'data-target="([^"]+)"', c)
print('Nav targets:', navs)
print('ideas in html:', 'ideas' in c.lower())
print('Feature Ideas in html:', 'Feature Ideas' in c)


# ============================================================
# SECTION: diag_js.py
# ============================================================

import re

with open('static/js/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

lines = js.split('\n')
total = len(lines)
print("Total lines:", total)

# Look for common JS issues:
# 1. Unmatched backtick template literals
# 2. Check for nav-link click handler
nav_idx = js.find('nav-link')
print("nav-link found at:", nav_idx)

click_idx = js.find("data-target")
print("data-target found at:", click_idx)

# Check for the showSection function  
show_idx = js.find('showSection')
print("showSection found at:", show_idx)

# Count backticks - should be even
btick = js.count('`')
print("Backtick count:", btick, "(" + ("EVEN - OK" if btick % 2 == 0 else "ODD - BROKEN!") + ")")

# Count template literal depth issues - look for ${ not closed
# Simple check: count ${ vs }
dollar_open = js.count('${')
print("${ count:", dollar_open)

# Look for any obvous broken areas around the new Reddit card code
new_card_start = js.find('function buildRedditCard')
if new_card_start != -1:
    print("buildRedditCard at line:", js[:new_card_start].count('\n') + 1)
    # Check 50 lines after it
    chunk = js[new_card_start:new_card_start+3000]
    btick_in_fn = chunk.count('`')
    print("Backticks in buildRedditCard:", btick_in_fn, "(" + ("EVEN" if btick_in_fn % 2 == 0 else "ODD!") + ")")

# Look for nav handler
nav_handler = js.find("querySelectorAll('.nav-link')")
if nav_handler == -1:
    nav_handler = js.find('nav-link')
print("nav handler at:", nav_handler)
print("context:", repr(js[max(0,nav_handler-50):nav_handler+200]))


# ============================================================
# SECTION: find_block.py
# ============================================================

import re, ast

def read(path):
    with open(path,'r',encoding='utf-8') as f: return f.read()
def write(path,c):
    with open(path,'w',encoding='utf-8') as f: f.write(c)

app_py = read('app.py')

# Find the whole block from SEARX_INSTANCES to end of _bing fallback
start = app_py.find('# ---- Google / Web Dork Search')
if start == -1:
    start = app_py.find('SEARX_INSTANCES')
    # Go back to # comment
    start = app_py.rfind('\n', 0, start) + 1

# Find end: after def fetch_web_page_text function
end = app_py.find('\ndef fetch_web_page_text(')
end = app_py.find('\n\n\n', end)   # triple newline after function

print("start=%d end=%d" % (start, end))
print("--- snippet at start: ---")
print(repr(app_py[start:start+120]))
print("--- snippet at end: ---")
print(repr(app_py[end:end+80]))


# ============================================================
# SECTION: find_brace.py
# ============================================================

with open('static/js/app.js', 'r', encoding='utf-8') as f: js = f.read()

stack = []
for i, c in enumerate(js):
    if c == '{':
        stack.append(i)
    elif c == '}':
        if not stack:
            print(f"Unmatched closing brace at offset {i}")
            line = js[:i].count('\n') + 1
            print(f"Line {line}:")
            print(js[max(0, i-100):i+100])
            break
        stack.pop()

print("Stack size at end:", len(stack))
if len(stack) > 0:
    for i in stack:
        print("Unmatched opening brace at line:", js[:i].count('\n')+1)



# ============================================================
# SECTION: find_bt.py
# ============================================================

with open('static/js/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Find buildRedditCard and locate the odd backtick
start = js.find('function buildRedditCard')
chunk = js[start:start+4000]

# Walk through and find unmatched backtick
depth = 0
in_string_sq = False
in_string_dq = False
in_template  = 0  # depth of template literals
i = 0
issues = []

while i < len(chunk):
    c = chunk[i]
    
    if c == '\\' and i+1 < len(chunk):
        i += 2  # skip escaped char
        continue
    
    if c == '`':
        if in_template > 0:
            in_template -= 1
        else:
            in_template += 1
        line_num = chunk[:i].count('\n') + 1
        issues.append("Line %d col %d: backtick toggle, depth now %d" % (line_num, i, in_template))
    
    i += 1

print("Template literal depth at end of fn:", in_template)
print("\nBacktick events:")
for ev in issues:
    print(" ", ev)
    
# Count total backticks in the function chunk
total_bt = chunk.count('`')
print("\nTotal backticks:", total_bt)


# ============================================================
# SECTION: fix_google_fn.py
# ============================================================

import ast

def read(path):
    with open(path,'r',encoding='utf-8') as f: return f.read()
def write(path,c):
    with open(path,'w',encoding='utf-8') as f: f.write(c)

app_py = read('app.py')

NEW_GOOGLE_BLOCK = r'''# ---- Google / Web Dork Search via DuckDuckGo HTML (free, no API key) ---

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

'''

# Replace from SEARX_INSTANCES to just before @app.route reddit/search
start = app_py.find('SEARX_INSTANCES')
# go back to find the # comment line
comment_start = app_py.rfind('\n', 0, start)
start = comment_start + 1

end = app_py.find('\n\n\n@app.route("/api/reddit/search"')
if end == -1:
    end = app_py.find('\n@app.route("/api/reddit/search"')
    end = max(0, end)
else:
    end += 2  # keep the two newlines before

print("Replacing chars %d to %d" % (start, end))
app_py = app_py[:start] + NEW_GOOGLE_BLOCK + '\n\n' + app_py[end:].lstrip('\n')

try:
    ast.parse(app_py)
    print("Syntax OK")
    write('app.py', app_py)
    print("app.py written (%d lines)" % app_py.count('\n'))
except SyntaxError as e:
    print("SYNTAX ERROR line %d: %s" % (e.lineno, e.msg))


# ============================================================
# SECTION: fix_html.py
# ============================================================

with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add nav button after subdomain nav item
OLD_NAV = '''          <button class="nav-link w-full flex items-center gap-3 text-fuchsia-400" data-target="sandbox">
            <i class="fas fa-user-secret text-fuchsia-400"></i>
            Disposable Browser
          </button>'''

NEW_NAV = '''          <button class="nav-link w-full flex items-center gap-3 text-amber-400" data-target="ideas">
            <i class="fas fa-lightbulb text-amber-400"></i>
            Feature Ideas
          </button>
          <button class="nav-link w-full flex items-center gap-3 text-fuchsia-400" data-target="sandbox">
            <i class="fas fa-user-secret text-fuchsia-400"></i>
            Disposable Browser
          </button>'''

if OLD_NAV in html:
    html = html.replace(OLD_NAV, NEW_NAV)
    print("Nav button added")
else:
    print("ERROR: nav button marker not found")

# 2. Add the Ideas section before sandbox section
OLD_SECTION = '''        <section id="sandbox" class="section-block hidden flex flex-col h-[85vh]">'''

IDEAS_SECTION = '''        <!-- Ideas / Feature Lab Section -->
        <section id="ideas" class="section-block hidden">
          <h2 class="text-2xl font-semibold text-amber-300 glow flex items-center gap-3">
            <i class="fas fa-lightbulb text-amber-400"></i>
            Feature Ideas Lab
          </h2>
          <div class="text-xs text-amber-300/60 mt-1 mb-6">
            Vote or suggest new tools &amp; modules — the top ideas get built next.
          </div>

          <!-- Idea Suggestion Form -->
          <div class="neon-panel p-6 mt-2 border-amber-500/20" style="border-color:rgba(251,191,36,0.2)">
            <div class="text-sm font-bold text-amber-300 uppercase tracking-widest mb-4">
              <i class="fas fa-plus-circle mr-2"></i>Submit a New Idea
            </div>
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div class="lg:col-span-2">
                <label class="label">Idea Title</label>
                <input id="idea-title" class="input-neon border-amber-500/30 focus:border-amber-400" placeholder="e.g. CVE live feed scanner, Dark web monitor..." />
              </div>
              <div>
                <label class="label">Category</label>
                <select id="idea-category" class="input-neon border-amber-500/30 focus:border-amber-400">
                  <option value="scanner">Scanner / Recon</option>
                  <option value="osint">OSINT / Intelligence</option>
                  <option value="sandbox">Sandbox / Browser</option>
                  <option value="report">Reporting</option>
                  <option value="ui">UI / Design</option>
                  <option value="ai">AI / Automation</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div class="lg:col-span-3">
                <label class="label">Description</label>
                <textarea id="idea-desc" class="input-neon border-amber-500/30 focus:border-amber-400 w-full h-20 resize-none" placeholder="Describe what you want built and why it would be useful..."></textarea>
              </div>
              <div class="flex items-end">
                <button id="idea-submit-btn" class="btn-neon text-amber-400 border-amber-400 hover:bg-amber-500/10 hover:shadow-[0_0_15px_rgba(251,191,36,0.4)] w-full">
                  <i class="fas fa-paper-plane mr-2"></i>Submit Idea
                </button>
              </div>
            </div>
          </div>

          <!-- Curated Ideas Board -->
          <div class="mt-8">
            <div class="text-sm font-bold text-amber-300 uppercase tracking-widest mb-4">
              <i class="fas fa-rocket mr-2"></i>Ideas Board
            </div>
            <div id="ideas-board" class="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <!-- Pre-loaded ideas -->
            </div>
          </div>
        </section>

        <section id="sandbox" class="section-block hidden flex flex-col h-[85vh]">'''

if OLD_SECTION in html:
    html = html.replace(OLD_SECTION, IDEAS_SECTION)
    print("Ideas section added")
else:
    print("ERROR: sandbox section marker not found")

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("HTML updated successfully")


# ============================================================
# SECTION: fix_ideas_js.py
# ============================================================

with open('static/js/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

IDEAS_JS = '''
// ── Feature Ideas Lab ─────────────────────────────────────────
const PRESET_IDEAS = [
  { id:1, title:"CVE Live Feed Scanner",      cat:"scanner", desc:"Pull real-time CVE data from NVD/MITRE and match against discovered services/ports. Show severity ratings.", votes:12, status:"planned" },
  { id:2, title:"Dark Web Monitor",           cat:"osint",   desc:"Monitor paste sites (Pastebin, ghostbin) and dark web indicators for leaked credentials or mentions of the target domain.", votes:9,  status:"idea" },
  { id:3, title:"WiFi Network Scanner",       cat:"scanner", desc:"Passive WiFi network recon — list nearby SSIDs, BSSIDs, signal strength and encryption types.", votes:7, status:"idea" },
  { id:4, title:"AI Threat Summarizer",       cat:"ai",      desc:"Use an LLM to auto-summarize OSINT and Nmap findings into a plain-English executive summary in the PDF report.", votes:15, status:"in-progress" },
  { id:5, title:"Screenshot Capture Engine",  cat:"sandbox", desc:"Automatically capture screenshots of target web pages and embed them in the PDF report.", votes:11, status:"planned" },
  { id:6, title:"Email Header Analyzer",      cat:"osint",   desc:"Paste email headers and get full analysis: SPF/DKIM checks, relay hops, geolocation of sending server.", votes:6, status:"idea" },
];

let userIdeas = JSON.parse(localStorage.getItem("netSecIdeas") || "[]");
let ideaVotes = JSON.parse(localStorage.getItem("netSecVotes") || "{}");

function renderIdeasBoard() {
  const board = document.getElementById("ideas-board");
  if (!board) return;
  const all = [...PRESET_IDEAS, ...userIdeas].sort((a,b) => (b.votes||0) - (a.votes||0));
  const catColors = {
    scanner:"#22d3ee", osint:"#f97316", sandbox:"#a855f7",
    report:"#4ade80", ui:"#fb923c", ai:"#f472b6", other:"#94a3b8",
    "in-progress":"#facc15", planned:"#60a5fa", idea:"#e2e8f0"
  };
  const statusLabel = { "in-progress":"🔄 In Progress", "planned":"📌 Planned", "idea":"💡 Idea" };
  board.innerHTML = all.map(idea => {
    const c  = catColors[idea.cat] || "#94a3b8";
    const sc = catColors[idea.status] || "#94a3b8";
    const voted = ideaVotes[idea.id];
    return `
      <div class="neon-panel p-5 flex flex-col gap-2 hover:border-amber-500/30 transition-all" style="border-color:${c}20;">
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="font-bold text-sm text-white">${idea.title}</div>
            <div class="text-[10px] uppercase tracking-widest mt-0.5" style="color:${c}">${idea.cat}</div>
          </div>
          <div class="text-[10px] px-2 py-0.5 rounded-full border shrink-0" style="color:${sc};border-color:${sc}40">
            ${statusLabel[idea.status] || idea.status}
          </div>
        </div>
        <div class="text-xs text-slate-400 leading-relaxed">${idea.desc}</div>
        <div class="flex items-center justify-between mt-2">
          <button onclick="voteIdea(${idea.id})" class="flex items-center gap-1.5 text-xs px-3 py-1 rounded border transition-all ${voted ? 'border-amber-400/50 text-amber-400' : 'border-slate-600 text-slate-400 hover:border-amber-400/50 hover:text-amber-400'}">
            <i class="fas fa-arrow-up"></i>
            <span id="votes-${idea.id}">${idea.votes || 0}</span>
            ${voted ? '<span class="text-[9px] opacity-60">VOTED</span>' : ''}
          </button>
          <span class="text-[10px] text-slate-600">#${idea.id}</span>
        </div>
      </div>`;
  }).join("");
}

function voteIdea(id) {
  if (ideaVotes[id]) return; // already voted
  ideaVotes[id] = true;
  localStorage.setItem("netSecVotes", JSON.stringify(ideaVotes));
  // Update vote count
  const preset = PRESET_IDEAS.find(i=>i.id===id);
  const user   = userIdeas.find(i=>i.id===id);
  if (preset) preset.votes = (preset.votes||0)+1;
  if (user)   user.votes   = (user.votes||0)+1;
  localStorage.setItem("netSecIdeas", JSON.stringify(userIdeas));
  renderIdeasBoard();
}

document.getElementById("idea-submit-btn")?.addEventListener("click", () => {
  const title = document.getElementById("idea-title").value.trim();
  const cat   = document.getElementById("idea-category").value;
  const desc  = document.getElementById("idea-desc").value.trim();
  if (!title) return alert("Please enter an idea title.");
  const idea = { id: Date.now(), title, cat, desc, votes:1, status:"idea" };
  userIdeas.push(idea);
  ideaVotes[idea.id] = true;
  localStorage.setItem("netSecIdeas", JSON.stringify(userIdeas));
  localStorage.setItem("netSecVotes", JSON.stringify(ideaVotes));
  document.getElementById("idea-title").value = "";
  document.getElementById("idea-desc").value  = "";
  sysLog("SYSTEM", `Idea submitted: ${title}`, "success");
  renderIdeasBoard();
});

renderIdeasBoard();
'''

# Append before the last line of the file
js = js.rstrip()
js += '\n' + IDEAS_JS + '\n'

with open('static/js/app.js', 'w', encoding='utf-8') as f:
    f.write(js)

print("Ideas JS appended successfully. Total lines:", js.count('\n'))


# ============================================================
# SECTION: fix_js.py
# ============================================================

import re

# Fix app.js: replace the full adv-intel card rendering section with branded tool cards
with open('static/js/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

OLD_SECTION = '''    state.advIntelResults[target] = data;
    resultsEl.innerHTML = "";
    sysLog("OSINT", `Deep Recon completed for ${target}`, "success");

    // Helper to create tool cards with better styling!
    const createCard = (title, content, icon = "fa-info-circle", color = "#22d3ee") => {
      const card = document.createElement("div");
      card.className = "relative overflow-hidden p-5 bg-black/40 border-t-2 rounded shadow-lg";
      card.style.borderTopColor = color;
      card.innerHTML = `
        <div class="flex items-center gap-2 mb-4 border-b border-white/5 pb-2">
          <i class="fas ${icon} text-lg" style="color: ${color}"></i>
          <span class="text-xs uppercase tracking-widest font-bold" style="color: ${color}">${title}</span>
        </div>
        <div class="text-xs font-mono text-slate-300 overflow-auto max-h-[300px] whitespace-pre-wrap">${content}</div>
      `;
      return card;
    };

    // Censys
    if (data.censys) {
      resultsEl.appendChild(createCard("Censys", JSON.stringify(data.censys, null, 2), "fa-search", "#00d2ff"));
    }

    // AlienVault OTX
    if (data.otx) {
      resultsEl.appendChild(createCard("AlienVault OTX", JSON.stringify(data.otx, null, 2), "fa-shield-virus", "#f97316"));
    }

    // IPinfo
    if (data.ipinfo) {
      const info = data.ipinfo;
      const text = `City: ${info.city}\\nRegion: ${info.region}\\nCountry: ${info.country}\\nOrg: ${info.org}\\nLoc: ${info.loc}\\nTimezone: ${info.timezone}`;
      resultsEl.appendChild(createCard("IPinfo.io", text, "fa-map-marker-alt", "#34d399"));
    }

    // Pulsedive
    if (data.pulsedive) {
      resultsEl.appendChild(createCard("Pulsedive", JSON.stringify(data.pulsedive, null, 2), "fa-water", "#818cf8"));
    }

    // Onyphe
    if (data.onyphe) {
      resultsEl.appendChild(createCard("Onyphe", JSON.stringify(data.onyphe, null, 2), "fa-eye", "#a78bfa"));
    }

    // BGPView
    if (data.bgpview && data.bgpview.data) {
      const bgp = data.bgpview.data;
      const text = `Prefixes: ${bgp.prefixes?.length || 0}\\nASNs: ${bgp.asns?.map(a => a.asn).join(", ")}`;
      resultsEl.appendChild(createCard("BGPView", text, "fa-route", "#fbbf24"));
    }

    // WHOIS (Local limits-free via Python)
    if (data.whois && data.whois.data) {
      resultsEl.appendChild(createCard("WHOIS Lookups", data.whois.data, "fa-id-card", "#f43f5e"));
    }

    // ThreatFox
    if (data.threatfox && data.threatfox.data) {
      resultsEl.appendChild(createCard("ThreatFox IOCs", JSON.stringify(data.threatfox.data, null, 2), "fa-biohazard", "#ef4444"));
    }

    // URLhaus
    if (data.urlhaus) {
      resultsEl.appendChild(createCard("URLhaus Malware", JSON.stringify(data.urlhaus, null, 2), "fa-link", "#db2777"));
    }

    // Robtex
    if (data.robtex) {
      resultsEl.appendChild(createCard("Robtex Network", JSON.stringify(data.robtex, null, 2), "fa-network-wired", "#14b8a6"));
    }

    if (resultsEl.children.length === 0) {
      resultsEl.innerHTML = `<div class="col-span-full text-center text-slate-500 py-10">No data found from integrated tools for this target.</div>`;'''

NEW_SECTION = '''    state.advIntelResults[target] = data;
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
      if (typeof obj === "string") return obj.replace(/\\n/g, "<br>");
      return JSON.stringify(obj, null, 2).replace(/\\n/g,"<br>").replace(/ /g,"&nbsp;");
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
      resultsEl.appendChild(createBrandedCard("whois", (data.whois.data||"").replace(/\\n/g,"<br>")));
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

    if (resultsEl.children.length === 0) {
      resultsEl.innerHTML = `<div class="col-span-full text-center text-slate-500 py-10">No data found from integrated tools for this target.</div>`;'''

if OLD_SECTION in js:
    js = js.replace(OLD_SECTION, NEW_SECTION)
    with open('static/js/app.js', 'w', encoding='utf-8') as f:
        f.write(js)
    print("SUCCESS: JS branded cards applied")
else:
    print("ERROR: OLD_SECTION not found in JS. Let me check...")
    idx = js.find('state.advIntelResults[target] = data;')
    print(f"Found advIntelResults at: {idx}")
    idx2 = js.find('Helper to create tool cards')
    print(f"Found 'Helper to create tool cards' at: {idx2}")


# ============================================================
# SECTION: fix_js_maps.py
# ============================================================

import sys

with open('static/js/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Remove the existing declarations
js = js.replace('let osintMap;\n', '')
js = js.replace('let liveAttackMap;\n', '')

# Prepend them to the top
new_header = "let liveAttackMap;\nlet osintMap;\n\n"
js = new_header + js

with open('static/js/app.js', 'w', encoding='utf-8') as f:
    f.write(js)

print("Fixed map variable declarations")


# ============================================================
# SECTION: fix_report.py
# ============================================================

NEW_REPORT_FN = '''
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
        el.append(Paragraph(f"Generated: {datetime.utcnow().strftime(\'%Y-%m-%d %H:%M:%S\')} UTC", meta_s))
        el.append(Spacer(1,24))

        summary    = payload.get("summary", {})
        hosts      = payload.get("hosts", [])
        osint_data = payload.get("osint", {})
        adv_intel  = payload.get("adv_intel", {})
        subdomains = payload.get("subdomains", {})

        risk_score = summary.get("risk", {}).get("score", "n/a")
        risk_level = str(summary.get("risk", {}).get("level", "n/a")).upper()
        risk_col   = colors.HexColor("#dc2626") if risk_level in ("CRITICAL","HIGH") \\
                     else colors.HexColor("#f59e0b") if risk_level == "MEDIUM" \\
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
                el.append(Paragraph(f"Host: {h.get(\'ip\')}  |  Status: {h.get(\'status\',\'?\')}  |  OS: {h.get(\'os_guess\') or \'Unknown\'}  |  Risk: {str(h.get(\'risk_level\',\'?\')).upper()}", h3_s))
                vulns=h.get("vulnerabilities") or []
                if vulns: el.append(Paragraph("Vulnerabilities: "+(", ".join(vulns)),norm_s))
                port_list=h.get("ports") or h.get("open_ports") or []
                if port_list:
                    nr=[["Port","Proto","State","Service","Product/Version","Scripts"]]
                    se=[]
                    for i,p in enumerate(port_list,1):
                        sc2="; ".join(f"{s[\'name\']}: {s[\'output\']}" for s in (p.get("scripts") or []) if s.get("output"))
                        nr.append([str(p.get("port","-")),p.get("protocol","-"),p.get("state","-"),p.get("service") or "-",
                                   Paragraph(f"{p.get(\'product\') or \'\'} {p.get(\'version\') or \'\'}".strip() or "-",mono_s),
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
                        ["Coords",f"{geo.get(\'lat\')}, {geo.get(\'lon\')}" if geo.get("lat") else "-"]]
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
                        wt=f"Handle: {name}  |  Org: {org2}  |  Type: {whois.get(\'type\','')}"
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

'''

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find boundaries
start_marker = '@app.route("/api/report", methods=["POST"])\n'
end_marker   = '\ndef get_subdomains('

start_idx = content.find(start_marker)
end_idx   = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print(f"ERROR: markers not found. start={start_idx}, end={end_idx}")
else:
    new_content = content[:start_idx] + NEW_REPORT_FN.lstrip('\n') + '\n\ndef get_subdomains(' + content[end_idx+len('\ndef get_subdomains('):]
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Done! Lines written:", new_content.count('\n'))


# ============================================================
# SECTION: patch_all.py
# ============================================================

import re, os, ast

def read(path):
    with open(path, 'r', encoding='utf-8') as f: return f.read()
def write(path, content):
    with open(path, 'w', encoding='utf-8') as f: f.write(content)
def ok(msg): print("[OK] " + msg)
def err(msg): print("[ERR] " + msg)

# =====================================================================
# 1. FIX app.js saveState/loadState (no stale scan data from localStorage)
# =====================================================================
JS_PATH = 'static/js/app.js'
js = read(JS_PATH)

OLD_SAVE = """function saveState() {
  localStorage.setItem("netsecState", JSON.stringify(state));
}

function loadState() {
  const savedState = localStorage.getItem("netsecState");
  if (savedState) {
    Object.assign(state, JSON.parse(savedState));
    renderHostTable();
    renderNmapTable();
    updateRisk();
  }
}"""

NEW_SAVE = """function saveState() {
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
}"""

if OLD_SAVE in js:
    js = js.replace(OLD_SAVE, NEW_SAVE)
    ok("saveState/loadState fixed")
else:
    err("saveState not found")

# Remove Ideas Lab JS block
ideas_start = js.find('\n// -- Feature Ideas Lab')
if ideas_start == -1:
    ideas_start = js.find('\n// Feature Ideas Lab')
if ideas_start == -1:
    ideas_start = js.find('const PRESET_IDEAS')
    if ideas_start != -1:
        # back up to find the comment line
        chunk = js[:ideas_start]
        nl = chunk.rfind('\n')
        ideas_start = nl

if ideas_start != -1:
    js = js[:ideas_start].rstrip() + '\n'
    ok("Ideas JS block removed")
else:
    ok("Ideas JS block not found (already removed)")

write(JS_PATH, js)
ok("app.js saved (%d lines)" % js.count('\n'))

# =====================================================================
# 2. HTML: remove Ideas tab, add Reddit nav + Reddit section
# =====================================================================
HTML_PATH = 'templates/index.html'
html = read(HTML_PATH)

# Remove ideas nav button
html = re.sub(
    r'\s*<button[^>]+data-target="ideas"[^>]*>.*?</button>',
    '', html, flags=re.DOTALL
)
ok("Ideas nav button removed")

# Add Reddit nav before sandbox
OLD_NAV = '          <button class="nav-link w-full flex items-center gap-3 text-fuchsia-400" data-target="sandbox">'
NEW_NAV = r"""          <button class="nav-link w-full flex items-center gap-3 text-orange-400" data-target="reddit">
            <i class="fab fa-reddit text-orange-400"></i>
            Reddit Intel
          </button>
          <button class="nav-link w-full flex items-center gap-3 text-fuchsia-400" data-target="sandbox">"""
if OLD_NAV in html:
    html = html.replace(OLD_NAV, NEW_NAV)
    ok("Reddit nav added")
else:
    err("Sandbox nav not found")

# Remove ideas section
ideas_sec = html.find('        <section id="ideas"')
if ideas_sec == -1:
    ideas_sec = html.find('<!-- Ideas / Feature Lab Section -->')
if ideas_sec != -1:
    close_tag = html.find('</section>', ideas_sec)
    if close_tag != -1:
        html = html[:ideas_sec].rstrip() + '\n' + html[close_tag + len('</section>'):].lstrip('\n')
        ok("Ideas HTML section removed")
else:
    ok("Ideas section already removed")

# Insert Reddit section before sandbox section
REDDIT_HTML = """
        <!-- Reddit Intelligence Section -->
        <section id="reddit" class="section-block hidden">
          <h2 class="text-2xl font-semibold flex items-center gap-3" style="color:#ff4500">
            <i class="fab fa-reddit" style="color:#ff4500"></i>
            Reddit Intelligence Search
          </h2>
          <p class="text-xs mt-1 mb-6" style="color:rgba(255,69,0,0.6)">
            Search Reddit posts by CVE, malware name, or any security topic. Click any result to open it. Use Analyze to get an AI summary.
          </p>

          <div class="neon-panel p-6" style="border-color:rgba(255,69,0,0.2)">
            <div class="grid grid-cols-1 lg:grid-cols-5 gap-4">
              <div class="lg:col-span-4">
                <label class="label">Search Query</label>
                <input id="reddit-query" class="input-neon" style="border-color:rgba(255,69,0,0.3)"
                  placeholder="e.g. CVE-2024-21413 or ransomware screenshot keylogger 2024..." />
              </div>
              <div class="flex items-end">
                <button id="reddit-search-btn" class="btn-neon w-full" style="color:#ff4500;border-color:#ff4500">
                  <i class="fab fa-reddit mr-2"></i>Search
                </button>
              </div>
            </div>
            <div class="mt-4">
              <div class="text-xs" style="color:#ff4500">Search Progress</div>
              <div class="w-full bg-black/60 mt-2 progress-track">
                <div id="reddit-progress" class="glow-bar progress-fill" style="width:0%;background:#ff4500;transition:width 0.6s ease"></div>
              </div>
            </div>
          </div>

          <div id="reddit-results-container" class="mt-6 hidden">
            <div class="flex items-center justify-between mb-4">
              <div class="text-sm font-bold uppercase tracking-widest" style="color:#ff4500">
                <i class="fab fa-reddit mr-2"></i>Top Reddit Posts
                <span id="reddit-count" class="ml-2 text-xs opacity-60"></span>
              </div>
              <button id="reddit-analyze-btn" class="btn-neon px-6" style="color:#ff4500;border-color:#ff4500;display:none">
                <i class="fas fa-brain mr-2"></i>Analyze &amp; Summarize with AI
              </button>
            </div>

            <div id="reddit-posts-grid" class="grid grid-cols-1 lg:grid-cols-2 gap-4"></div>

            <div id="reddit-summary-panel" class="hidden mt-6 neon-panel p-6" style="border-color:rgba(255,69,0,0.3)">
              <div class="flex items-center gap-3 mb-4">
                <div class="w-9 h-9 rounded-lg flex items-center justify-center" style="background:rgba(255,69,0,0.15)">
                  <i class="fas fa-brain text-lg" style="color:#ff4500"></i>
                </div>
                <div>
                  <div class="font-bold text-sm" style="color:#ff4500">AI Intelligence Summary</div>
                  <div class="text-[10px] text-slate-500 uppercase tracking-widest">Auto-generated from top Reddit posts</div>
                </div>
                <div id="reddit-summary-spinner" class="ml-auto hidden">
                  <div class="w-5 h-5 border-2 rounded-full animate-spin" style="border-color:rgba(255,69,0,0.2);border-top-color:#ff4500"></div>
                </div>
              </div>
              <div id="reddit-summary-text" class="text-xs leading-relaxed text-slate-300 whitespace-pre-wrap font-mono"></div>
            </div>
          </div>
        </section>

"""

sandbox_marker = '        <section id="sandbox" class="section-block hidden flex flex-col h-[85vh]">'
if sandbox_marker in html:
    html = html.replace(sandbox_marker, REDDIT_HTML + sandbox_marker)
    ok("Reddit HTML section inserted before sandbox")
else:
    err("Sandbox section not found for Reddit insertion")

write(HTML_PATH, html)
ok("index.html saved")

# =====================================================================
# 3. app.py: add Reddit search + AI analyze endpoints
# =====================================================================
APP_PATH = 'app.py'
app_py = read(APP_PATH)

# Only add if not already present
if '/api/reddit/search' not in app_py:
    REDDIT_BACKEND = '''

# ---- Reddit Intelligence ------------------------------------------

REDDIT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}


def reddit_search(query, limit=10):
    """Search Reddit using public JSON API - no auth required."""
    results = []
    try:
        params = {
            "q": query, "sort": "relevance",
            "limit": min(limit, 25), "t": "year", "type": "link",
        }
        r = requests.get(
            "https://www.reddit.com/search.json",
            params=params, headers=REDDIT_HEADERS, timeout=12,
        )
        if r.status_code != 200:
            return results, "Reddit returned HTTP %d" % r.status_code
        for child in r.json().get("data", {}).get("children", []):
            p = child.get("data", {})
            results.append({
                "id":           p.get("id", ""),
                "title":        p.get("title", ""),
                "subreddit":    p.get("subreddit_name_prefixed", ""),
                "url":          "https://www.reddit.com" + p.get("permalink", ""),
                "score":        p.get("score", 0),
                "upvote_ratio": p.get("upvote_ratio", 0),
                "num_comments": p.get("num_comments", 0),
                "created_utc":  p.get("created_utc", 0),
                "selftext":     (p.get("selftext", "") or "")[:800],
                "domain":       p.get("domain", ""),
                "is_self":      p.get("is_self", False),
            })
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
                    text += "\\n\\n" + body[:500]
        return text.strip()
    except Exception:
        return ""


def extractive_summarize(query, texts):
    """Local frequency-based extractive summarization - no API needed."""
    combined = "Query: %s\\n\\n" % query
    for i, t in enumerate(texts, 1):
        if t:
            combined += "--- Post %d ---\\n%s\\n\\n" % (i, t[:600])
    combined = combined[:5000]

    sentences = re.split(r"(?<=[.!?])\\s+", combined)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 30][:100]

    stopwords = {
        "the","a","an","in","on","at","is","it","of","to","and","or","for",
        "with","this","that","was","are","be","by","from","as","have","has",
        "not","but","been","will","can","its","i","we","they","you","he","she",
        "post","reddit","comment","https","www","com","http",
    }
    import collections, heapq
    words = re.findall(r"\\b[a-z]{3,}\\b", combined.lower())
    freq = collections.Counter(w for w in words if w not in stopwords)
    if not freq:
        return "Insufficient content to generate a summary."

    scores = {}
    for sent in sentences:
        ws = re.findall(r"\\b[a-z]{3,}\\b", sent.lower())
        scores[sent] = sum(freq.get(w, 0) for w in ws if w not in stopwords) / max(len(ws), 1)

    top_sentences = heapq.nlargest(min(7, len(sentences)), scores, key=scores.get)
    ordered = [s for s in sentences if s in top_sentences]
    return " ".join(ordered[:7]) or "Could not generate a summary."


def ai_summarize(query, posts_content):
    """Try HuggingFace free inference first, fall back to local extractive."""
    combined = "Query: %s\\n\\n" % query
    for i, t in enumerate(posts_content, 1):
        if t:
            combined += "--- Post %d ---\\n%s\\n\\n" % (i, t[:500])
    combined = combined[:3500]

    try:
        hf = requests.post(
            "https://api-inference.huggingface.co/models/sshleifer/distilbart-cnn-12-6",
            json={"inputs": combined, "parameters": {"max_length": 400, "min_length": 80}},
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
        enriched.append("TITLE: %s\\n%s" % (post.get("title", ""), txt))

    summary = ai_summarize(query, enriched)
    return jsonify({"summary": summary, "posts_analyzed": len(enriched)})

# ------------------------------------------------------------------
'''
    app_py = app_py.replace(
        '\nif __name__ == "__main__":',
        REDDIT_BACKEND + '\nif __name__ == "__main__":'
    )
    ok("Reddit backend added to app.py")
else:
    ok("Reddit backend already present")

write(APP_PATH, app_py)
ok("app.py saved")

# =====================================================================
# 4. Append Reddit frontend JS
# =====================================================================
js = read(JS_PATH)

if 'reddit-search-btn' not in js:
    REDDIT_JS = """
// ---- Reddit Intelligence Tab ------------------------------------

let redditPosts = [];

document.getElementById("reddit-search-btn")?.addEventListener("click", async () => {
  const query       = document.getElementById("reddit-query").value.trim();
  const progressEl  = document.getElementById("reddit-progress");
  const analyzeBtn  = document.getElementById("reddit-analyze-btn");
  const container   = document.getElementById("reddit-results-container");
  const postsGrid   = document.getElementById("reddit-posts-grid");
  const summaryPanel= document.getElementById("reddit-summary-panel");
  const countEl     = document.getElementById("reddit-count");

  if (!query) return alert("Please enter a search query.");

  progressEl.style.width = "20%";
  summaryPanel.classList.add("hidden");
  analyzeBtn.style.display = "none";
  container.classList.remove("hidden");
  postsGrid.innerHTML = `<div class="col-span-2 flex flex-col items-center py-12 gap-4">
    <div class="w-12 h-12 border-4 rounded-full animate-spin" style="border-color:rgba(255,69,0,0.2);border-top-color:#ff4500"></div>
    <div class="text-sm uppercase tracking-widest" style="color:#ff4500">Searching Reddit...</div>
  </div>`;

  sysLog("OSINT", `Searching Reddit for: ${query}`, "info");

  try {
    progressEl.style.width = "50%";
    const res  = await fetch("/api/reddit/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    progressEl.style.width = "80%";
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Search failed");

    redditPosts = data.posts || [];
    progressEl.style.width = "100%";
    countEl.textContent = `(${redditPosts.length} posts found)`;
    sysLog("OSINT", `Found ${redditPosts.length} Reddit posts for: ${query}`, "success");

    postsGrid.innerHTML = "";
    if (!redditPosts.length) {
      postsGrid.innerHTML = `<div class="col-span-2 text-center text-slate-500 py-10">No Reddit posts found.</div>`;
    } else {
      redditPosts.forEach((post, idx) => {
        const age   = post.created_utc
          ? new Date(post.created_utc * 1000).toLocaleDateString("en-US",{year:"numeric",month:"short",day:"numeric"})
          : "";
        const ratio = Math.round((post.upvote_ratio || 0) * 100);
        const card  = document.createElement("a");
        card.href   = post.url;
        card.target = "_blank";
        card.rel    = "noopener noreferrer";
        card.className = "block rounded-xl p-5 group transition-all duration-200 hover:-translate-y-0.5";
        card.style.cssText = "background:#180800;border:1px solid rgba(255,69,0,0.18);box-shadow:0 2px 16px rgba(255,69,0,0.07);text-decoration:none;";
        card.innerHTML = `
          <div class="flex items-start gap-3">
            <div class="text-2xl font-black shrink-0 leading-none mt-1" style="color:rgba(255,69,0,0.3)">${String(idx+1).padStart(2,"0")}</div>
            <div class="min-w-0 flex-1">
              <div class="text-sm font-bold leading-snug text-white group-hover:text-orange-300 transition-colors line-clamp-3">${post.title}</div>
              <div class="flex flex-wrap items-center gap-3 mt-2 text-[11px]" style="color:#ff4500aa">
                <span><i class="fab fa-reddit mr-1"></i>${post.subreddit}</span>
                <span><i class="fas fa-arrow-up mr-1"></i>${(post.score||0).toLocaleString()}</span>
                <span><i class="fas fa-percent mr-1"></i>${ratio}%</span>
                <span><i class="fas fa-comment-alt mr-1"></i>${post.num_comments||0} comments</span>
                ${age ? `<span><i class="fas fa-calendar-alt mr-1"></i>${age}</span>` : ""}
              </div>
              ${post.selftext ? `<p class="mt-2 text-xs text-slate-400 leading-relaxed line-clamp-2">${post.selftext.slice(0,200)}...</p>` : ""}
            </div>
            <i class="fas fa-external-link-alt shrink-0 text-xs mt-1 opacity-20 group-hover:opacity-60 transition-opacity" style="color:#ff4500"></i>
          </div>`;
        postsGrid.appendChild(card);
      });
      analyzeBtn.style.display = "";
    }

    setTimeout(() => { progressEl.style.width = "0%"; }, 1200);
  } catch (err) {
    sysLog("OSINT", `Reddit error: ${err.message}`, "error");
    postsGrid.innerHTML = `<div class="col-span-2 text-red-400 text-center py-10">${err.message}</div>`;
    progressEl.style.width = "0%";
  }
});

document.getElementById("reddit-analyze-btn")?.addEventListener("click", async () => {
  if (!redditPosts.length) return;
  const summaryPanel = document.getElementById("reddit-summary-panel");
  const summaryText  = document.getElementById("reddit-summary-text");
  const spinner      = document.getElementById("reddit-summary-spinner");
  const query        = document.getElementById("reddit-query").value.trim();

  summaryPanel.classList.remove("hidden");
  summaryText.textContent = "Analyzing posts...";
  spinner.classList.remove("hidden");
  sysLog("OSINT", `AI analyzing ${redditPosts.length} Reddit posts...`, "warn");

  try {
    const res = await fetch("/api/reddit/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        posts: redditPosts.slice(0, 10).map(p => ({ url: p.url, title: p.title })),
      }),
    });
    const data = await res.json();
    spinner.classList.add("hidden");
    if (!res.ok) throw new Error(data.error || "Analysis failed");
    summaryText.textContent = data.summary;
    sysLog("OSINT", `AI summary complete - analyzed ${data.posts_analyzed} posts.`, "success");
  } catch (err) {
    spinner.classList.add("hidden");
    summaryText.textContent = `Error: ${err.message}`;
    sysLog("OSINT", `AI error: ${err.message}`, "error");
  }
});

document.getElementById("reddit-query")?.addEventListener("keypress", (e) => {
  if (e.key === "Enter") document.getElementById("reddit-search-btn")?.click();
});
"""
    js = js.rstrip() + '\n' + REDDIT_JS + '\n'
    write(JS_PATH, js)
    ok("Reddit frontend JS added")
else:
    ok("Reddit JS already present")

# =====================================================================
# 5. Syntax check
# =====================================================================
try:
    ast.parse(read(APP_PATH))
    ok("app.py syntax OK")
except SyntaxError as e:
    err("app.py syntax error at line %d: %s" % (e.lineno, e.msg))

print("\n=== All patches complete ===")


# ============================================================
# SECTION: patch_fix2.py
# ============================================================

import re, ast

def read(path):
    with open(path,'r',encoding='utf-8') as f: return f.read()
def write(path,c):
    with open(path,'w',encoding='utf-8') as f: f.write(c)
def ok(m):  print("[OK]  "+m)
def err(m): print("[ERR] "+m)

# =====================================================================
# 1. app.py — replace google_dork_search with reliable DDG HTML scraping
# =====================================================================
app_py = read('app.py')

OLD_GOOGLE_FN = '''# ---- Google / Web Dork Search using SearXNG (free, no API key) ──────

SEARX_INSTANCES = [
    "https://searx.be",
    "https://searxng.site",
    "https://search.sapti.me",
    "https://searx.tiekoetter.com",
]

def google_dork_search(query, limit=10):
    """Search Google/Bing/DDG results via SearXNG free public instances."""
    results = []
    last_error = "All instances unavailable"

    for instance in SEARX_INSTANCES:
        try:
            params = {
                "q": query, "format": "json",
                "engines": "google,bing,duckduckgo",
                "pageno": 1, "language": "en",
            }
            r = requests.get(
                instance + "/search",
                params=params,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=12,
            )
            if r.status_code == 200:
                data = r.json()
                for item in data.get("results", [])[:limit]:
                    results.append({
                        "title":   item.get("title", ""),
                        "url":     item.get("url", ""),
                        "snippet": item.get("content", ""),
                        "engines": ", ".join(item.get("engines", [])),
                        "score":   round(item.get("score", 0), 2),
                        "published_date": item.get("publishedDate", ""),
                        "thumbnail": item.get("img_src", ""),
                    })
                if results:
                    return results, None
        except Exception as ex:
            last_error = str(ex)
            continue

    return results, last_error'''

NEW_GOOGLE_FN = '''# ---- Google / Web Dork Search via DuckDuckGo HTML (free, no API key) ───

import urllib.parse as _urlparse

_DDG_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
           "AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/124.0.0.0 Safari/537.36")
_DDG_HEADERS = {
    "User-Agent": _DDG_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}


def _decode_ddg_url(raw_url):
    """Decode DuckDuckGo redirect URLs to real destination URLs."""
    if not raw_url:
        return ""
    if raw_url.startswith("//duckduckgo.com"):
        raw_url = "https:" + raw_url
    if "duckduckgo.com/l/?" in raw_url or "duckduckgo.com/y.js" in raw_url:
        try:
            qs = _urlparse.parse_qs(_urlparse.urlparse(raw_url).query)
            return _urlparse.unquote(qs.get("uddg", [raw_url])[0])
        except Exception:
            pass
    return raw_url


def _strip_html(text):
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def google_dork_search(query, limit=10):
    """
    Search via DuckDuckGo HTML endpoint — 100% free, no API key, no rate limit.
    Falls back to Bing HTML scraping if DDG is unavailable.
    """
    results = _ddg_html_search(query, limit)
    if results:
        return results, None

    results = _bing_html_search(query, limit)
    if results:
        return results, None

    return [], "Search unavailable — check network connectivity"


def _ddg_html_search(query, limit=10):
    """DuckDuckGo HTML scraping — most reliable free search, no API needed."""
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

        # Extract result titles + URLs
        title_matches = re.findall(
            r\'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>\',
            html, re.DOTALL
        )
        # Extract snippets
        snippet_matches = re.findall(
            r\'class="result__snippet"[^>]*>(.*?)</a>\',
            html, re.DOTALL
        )
        # Extract displayed URLs
        url_matches = re.findall(
            r\'class="result__url"[^>]*>\\s*(.*?)\\s*</\',
            html, re.DOTALL
        )

        results = []
        for i, (raw_url, raw_title) in enumerate(title_matches[:limit]):
            real_url  = _decode_ddg_url(raw_url.strip())
            title     = _strip_html(raw_title)
            snippet   = _strip_html(snippet_matches[i]) if i < len(snippet_matches) else ""
            display   = _strip_html(url_matches[i])     if i < len(url_matches)    else ""

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
        print("DDG HTML search error: " + str(ex))
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

        # Parse Bing result items
        blocks = re.findall(r\'<li class="b_algo"[^>]*>(.*?)</li>\', html, re.DOTALL)
        results = []
        for block in blocks[:limit]:
            title_m   = re.search(r\'<h2[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>\', block, re.DOTALL)
            snippet_m = re.search(r\'<p[^>]*>(.*?)</p>\', block, re.DOTALL)
            if not title_m:
                continue
            results.append({
                "title":          _strip_html(title_m.group(2)),
                "url":            title_m.group(1),
                "snippet":        _strip_html(snippet_m.group(1)) if snippet_m else "",
                "engines":        "Bing",
                "score":          round(1.0 - len(results) * 0.05, 2),
                "published_date": "",
                "thumbnail":      "",
            })
        return results
    except Exception as ex:
        print("Bing search error: " + str(ex))
        return []'''

if OLD_GOOGLE_FN in app_py:
    app_py = app_py.replace(OLD_GOOGLE_FN, NEW_GOOGLE_FN)
    ok("google_dork_search replaced with DDG HTML scraping")
else:
    err("OLD_GOOGLE_FN not found — checking partial match...")
    idx = app_py.find('SEARX_INSTANCES')
    ok("  SEARX_INSTANCES at idx=%d" % idx)

write('app.py', app_py)
try:
    ast.parse(app_py)
    ok("app.py syntax OK")
except SyntaxError as e:
    err("Syntax error line %d: %s" % (e.lineno, e.msg))

# =====================================================================
# 2. app.js — modern Reddit card matching the reference image
#    (card with Reddit logo top-right, vote/comment icons at bottom)
# =====================================================================
js = read('static/js/app.js')

# Remove old buildRedditCard and Reddit search listener
OLD_BUILD = 'function buildRedditCard(post) {'
start_build = js.find(OLD_BUILD)
end_listener = js.find("document.getElementById(\"reddit-query\")?.addEventListener(\"keypress\"")
end_listener = js.find(");", end_listener) + 2  # find closing

if start_build != -1 and end_listener != -1:
    before = js[:start_build].rstrip()
    after  = js[end_listener:].lstrip('\n')
    js = before + '\n' + after
    ok("Old Reddit card + listeners removed")
else:
    err("Markers not found: build=%d listener=%d" % (start_build, end_listener))

NEW_REDDIT_JS = """
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

// ── Reddit search + analyze listeners ────────────────────────────────

document.getElementById("reddit-search-btn")?.addEventListener("click", async () => {
  const query        = (document.getElementById("reddit-query")?.value||"").trim();
  const progressEl   = document.getElementById("reddit-progress");
  const analyzeBtn   = document.getElementById("reddit-analyze-btn");
  const container    = document.getElementById("reddit-results-container");
  const postsGrid    = document.getElementById("reddit-posts-grid");
  const summaryPanel = document.getElementById("reddit-summary-panel");
  const countEl      = document.getElementById("reddit-count");
  if (!query) return alert("Please enter a search query.");

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
    countEl.textContent = redditPosts.length + " posts";
    sysLog("OSINT","Found "+redditPosts.length+" Reddit posts","success");
    postsGrid.innerHTML = "";
    if (!redditPosts.length) {
      postsGrid.innerHTML = `<div style="padding:40px;text-align:center;color:#818384">No Reddit posts found. Try a different query.</div>`;
    } else {
      redditPosts.forEach(p => postsGrid.appendChild(buildRedditCard(p)));
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
"""

js = js.rstrip() + '\n' + NEW_REDDIT_JS + '\n'
write('static/js/app.js', js)
ok("Modern Reddit card JS written (%d lines)" % js.count('\n'))

print("\n=== Patch complete ===")


# ============================================================
# SECTION: patch_reddit.py
# ============================================================

import re, ast

def read(path):
    with open(path,'r',encoding='utf-8') as f: return f.read()
def write(path,c):
    with open(path,'w',encoding='utf-8') as f: f.write(c)
def ok(m): print("[OK] "+m)
def er(m): print("[ERR] "+m)

# =====================================================================
# 1. app.py  - add top-2 comments to each search result,
#              replace ai_summarize to use Pollinations.ai (free ChatGPT)
# =====================================================================
app_py = read('app.py')

# ---- replace the three functions: reddit_search, ai_summarize, extractive_summarize ----
OLD_REDDIT_SEARCH = '''def reddit_search(query, limit=10):
    """Search Reddit using public JSON API - no auth required."""
    results = []
    try:
        params = {
            "q": query, "sort": "relevance",
            "limit": min(limit, 25), "t": "year", "type": "link",
        }
        r = requests.get(
            "https://www.reddit.com/search.json",
            params=params, headers=REDDIT_HEADERS, timeout=12,
        )
        if r.status_code != 200:
            return results, "Reddit returned HTTP %d" % r.status_code
        for child in r.json().get("data", {}).get("children", []):
            p = child.get("data", {})
            results.append({
                "id":           p.get("id", ""),
                "title":        p.get("title", ""),
                "subreddit":    p.get("subreddit_name_prefixed", ""),
                "url":          "https://www.reddit.com" + p.get("permalink", ""),
                "score":        p.get("score", 0),
                "upvote_ratio": p.get("upvote_ratio", 0),
                "num_comments": p.get("num_comments", 0),
                "created_utc":  p.get("created_utc", 0),
                "selftext":     (p.get("selftext", "") or "")[:800],
                "domain":       p.get("domain", ""),
                "is_self":      p.get("is_self", False),
            })
    except Exception as ex:
        return results, str(ex)
    return results, None'''

NEW_REDDIT_SEARCH = '''def fetch_top_comments(permalink, limit=2):
    """Fetch top N comments for a given Reddit permalink."""
    try:
        json_url = "https://www.reddit.com" + permalink + ".json?limit=5&sort=top"
        r = requests.get(json_url, headers=REDDIT_HEADERS, timeout=8)
        if r.status_code != 200:
            return []
        data = r.json()
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
        return comments
    except Exception:
        return []


def reddit_search(query, limit=10):
    """Search Reddit using public JSON API - no auth required. Includes top 2 comments per post."""
    results = []
    try:
        params = {
            "q": query, "sort": "relevance",
            "limit": min(limit, 25), "t": "year", "type": "link",
        }
        r = requests.get(
            "https://www.reddit.com/search.json",
            params=params, headers=REDDIT_HEADERS, timeout=12,
        )
        if r.status_code != 200:
            return results, "Reddit returned HTTP %d" % r.status_code

        raw_posts = []
        for child in r.json().get("data", {}).get("children", []):
            p = child.get("data", {})
            raw_posts.append({
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
                "comments":     [],
            })

        # Fetch top 2 comments for each post in parallel
        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = {ex.submit(fetch_top_comments, p["permalink"], 2): i
                       for i, p in enumerate(raw_posts)}
            for ft, idx in futures.items():
                raw_posts[idx]["comments"] = ft.result()

        results = raw_posts
    except Exception as ex:
        return results, str(ex)
    return results, None'''

if OLD_REDDIT_SEARCH in app_py:
    app_py = app_py.replace(OLD_REDDIT_SEARCH, NEW_REDDIT_SEARCH)
    ok("reddit_search updated with comments fetching")
else:
    er("OLD_REDDIT_SEARCH not found")

# ---- Replace ai_summarize to use Pollinations.ai ----
OLD_AI = '''def ai_summarize(query, posts_content):
    """Try HuggingFace free inference first, fall back to local extractive."""
    combined = "Query: %s\\n\\n" % query
    for i, t in enumerate(posts_content, 1):
        if t:
            combined += "--- Post %d ---\\n%s\\n\\n" % (i, t[:500])
    combined = combined[:3500]

    try:
        hf = requests.post(
            "https://api-inference.huggingface.co/models/sshleifer/distilbart-cnn-12-6",
            json={"inputs": combined, "parameters": {"max_length": 400, "min_length": 80}},
            headers={"Content-Type": "application/json"},
            timeout=25,
        )
        if hf.status_code == 200:
            out = hf.json()
            if isinstance(out, list) and out and out[0].get("summary_text"):
                return out[0]["summary_text"]
    except Exception:
        pass

    return extractive_summarize(query, posts_content)'''

NEW_AI = '''def ai_summarize(query, posts_content):
    """Summarize using Pollinations.ai (free ChatGPT, no login needed).
    Falls back to local extractive summarization if unavailable."""
    combined_parts = []
    for i, t in enumerate(posts_content, 1):
        if t:
            combined_parts.append("--- Post %d ---\\n%s" % (i, t[:500]))
    combined = "\\n\\n".join(combined_parts)[:4000]

    prompt = (
        "You are a cybersecurity analyst AI. "
        "A user searched Reddit for: \\'%s\\'\\n\\n"
        "Here are excerpts from the top Reddit posts on this topic:\\n\\n"
        "%s\\n\\n"
        "Please provide a comprehensive analysis that:\\n"
        "1. Summarizes the key findings from these community posts\\n"
        "2. Highlights any warnings, threat indicators, or security risks mentioned\\n"
        "3. Notes the community consensus or notable disagreements\\n"
        "4. Provides practical takeaways for a security professional\\n"
        "Be concise, factual, and security-focused."
    ) % (query, combined)

    # Try Pollinations.ai (free ChatGPT/OpenAI, no key needed)
    try:
        r = requests.post(
            "https://text.pollinations.ai/",
            json={
                "messages": [{"role": "user", "content": prompt}],
                "model": "openai",
                "seed": 42,
            },
            headers={"Content-Type": "application/json"},
            timeout=45,
        )
        if r.status_code == 200 and r.text.strip():
            return r.text.strip()
    except Exception:
        pass

    # Fallback to HuggingFace
    try:
        hf_prompt = "Summarize these Reddit posts about %s:\\n%s" % (query, combined[:2500])
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

    return extractive_summarize(query, posts_content)'''

if OLD_AI in app_py:
    app_py = app_py.replace(OLD_AI, NEW_AI)
    ok("ai_summarize updated to use Pollinations.ai (free ChatGPT)")
else:
    er("OLD_AI not found")

write('app.py', app_py)
try:
    ast.parse(app_py)
    ok("app.py syntax OK")
except SyntaxError as e:
    er("Syntax error at line %d: %s" % (e.lineno, e.msg))

# =====================================================================
# 2. HTML  - update Reddit section (Summarize button placement + ChatGPT logo)
# =====================================================================
html = read('templates/index.html')

OLD_REDDIT_HTML = '''        <!-- Reddit Intelligence Section -->
        <section id="reddit" class="section-block hidden">
          <h2 class="text-2xl font-semibold flex items-center gap-3" style="color:#ff4500">
            <i class="fab fa-reddit" style="color:#ff4500"></i>
            Reddit Intelligence Search
          </h2>
          <p class="text-xs mt-1 mb-6" style="color:rgba(255,69,0,0.6)">
            Search Reddit posts by CVE, malware name, or any security topic. Click any result to open it. Use Analyze to get an AI summary.
          </p>

          <div class="neon-panel p-6" style="border-color:rgba(255,69,0,0.2)">
            <div class="grid grid-cols-1 lg:grid-cols-5 gap-4">
              <div class="lg:col-span-4">
                <label class="label">Search Query</label>
                <input id="reddit-query" class="input-neon" style="border-color:rgba(255,69,0,0.3)"
                  placeholder="e.g. CVE-2024-21413 or ransomware screenshot keylogger 2024..." />
              </div>
              <div class="flex items-end">
                <button id="reddit-search-btn" class="btn-neon w-full" style="color:#ff4500;border-color:#ff4500">
                  <i class="fab fa-reddit mr-2"></i>Search
                </button>
              </div>
            </div>
            <div class="mt-4">
              <div class="text-xs" style="color:#ff4500">Search Progress</div>
              <div class="w-full bg-black/60 mt-2 progress-track">
                <div id="reddit-progress" class="glow-bar progress-fill" style="width:0%;background:#ff4500;transition:width 0.6s ease"></div>
              </div>
            </div>
          </div>

          <div id="reddit-results-container" class="mt-6 hidden">
            <div class="flex items-center justify-between mb-4">
              <div class="text-sm font-bold uppercase tracking-widest" style="color:#ff4500">
                <i class="fab fa-reddit mr-2"></i>Top Reddit Posts
                <span id="reddit-count" class="ml-2 text-xs opacity-60"></span>
              </div>
              <button id="reddit-analyze-btn" class="btn-neon px-6" style="color:#ff4500;border-color:#ff4500;display:none">
                <i class="fas fa-brain mr-2"></i>Analyze &amp; Summarize with AI
              </button>
            </div>

            <div id="reddit-posts-grid" class="grid grid-cols-1 lg:grid-cols-2 gap-4"></div>

            <div id="reddit-summary-panel" class="hidden mt-6 neon-panel p-6" style="border-color:rgba(255,69,0,0.3)">
              <div class="flex items-center gap-3 mb-4">
                <div class="w-9 h-9 rounded-lg flex items-center justify-center" style="background:rgba(255,69,0,0.15)">
                  <i class="fas fa-brain text-lg" style="color:#ff4500"></i>
                </div>
                <div>
                  <div class="font-bold text-sm" style="color:#ff4500">AI Intelligence Summary</div>
                  <div class="text-[10px] text-slate-500 uppercase tracking-widest">Auto-generated from top Reddit posts</div>
                </div>
                <div id="reddit-summary-spinner" class="ml-auto hidden">
                  <div class="w-5 h-5 border-2 rounded-full animate-spin" style="border-color:rgba(255,69,0,0.2);border-top-color:#ff4500"></div>
                </div>
              </div>
              <div id="reddit-summary-text" class="text-xs leading-relaxed text-slate-300 whitespace-pre-wrap font-mono"></div>
            </div>
          </div>
        </section>'''

NEW_REDDIT_HTML = '''        <!-- Reddit Intelligence Section -->
        <section id="reddit" class="section-block hidden">
          <!-- Header -->
          <div class="flex items-center gap-3 mb-2">
            <svg width="32" height="32" viewBox="0 0 20 20" fill="#FF4500" xmlns="http://www.w3.org/2000/svg">
              <circle cx="10" cy="10" r="10" fill="#FF4500"/>
              <path d="M16.67 10a1.46 1.46 0 0 0-2.47-1 7.12 7.12 0 0 0-3.85-1.23l.65-3.07 2.13.45a1 1 0 1 0 1-.97 1 1 0 0 0-.96.68l-2.38-.5a.27.27 0 0 0-.32.2l-.73 3.44a7.14 7.14 0 0 0-3.89 1.23 1.46 1.46 0 1 0-1.61 2.39 2.87 2.87 0 0 0 0 .44c0 2.24 2.61 4.06 5.83 4.06s5.83-1.82 5.83-4.06a2.87 2.87 0 0 0 0-.44 1.46 1.46 0 0 0 .68-1.62zM7.27 11a1 1 0 1 1 1 1 1 1 0 0 1-1-1zm5.58 2.71a3.58 3.58 0 0 1-2.85.87 3.58 3.58 0 0 1-2.85-.87.19.19 0 0 1 .27-.27 3.24 3.24 0 0 0 2.58.71 3.24 3.24 0 0 0 2.58-.71.19.19 0 0 1 .27.27zm-.13-1.71a1 1 0 1 1 1-1 1 1 0 0 1-1 1z" fill="white"/>
            </svg>
            <h2 class="text-2xl font-bold" style="color:#FF4500">Reddit Intelligence</h2>
          </div>
          <p class="text-xs mb-6" style="color:rgba(255,69,0,0.55)">
            Search Reddit by CVE, malware, or security topic. Top posts with community comments. AI-powered analysis via ChatGPT.
          </p>

          <!-- Search Bar -->
          <div class="rounded-xl p-5 mb-6" style="background:#1A1A1B;border:1px solid #343536">
            <div class="flex gap-3">
              <div class="flex-1 relative">
                <i class="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-sm" style="color:#818384"></i>
                <input id="reddit-query" class="w-full rounded-full px-4 pl-9 py-2.5 text-sm outline-none"
                  style="background:#272729;border:1px solid #343536;color:#D7DADC;caret-color:#FF4500;"
                  placeholder="Search Reddit: CVE-2024-21413, ransomware, keylogger..." />
              </div>
              <button id="reddit-search-btn" class="flex items-center gap-2 px-5 py-2 rounded-full font-bold text-sm transition-all hover:opacity-90"
                style="background:#FF4500;color:white;border:none;white-space:nowrap">
                <svg width="16" height="16" viewBox="0 0 20 20" fill="white"><circle cx="10" cy="10" r="10" fill="rgba(255,255,255,0.25)"/><path d="M16.67 10a1.46 1.46 0 0 0-2.47-1 7.12 7.12 0 0 0-3.85-1.23l.65-3.07 2.13.45a1 1 0 1 0 1-.97 1 1 0 0 0-.96.68l-2.38-.5a.27.27 0 0 0-.32.2l-.73 3.44a7.14 7.14 0 0 0-3.89 1.23 1.46 1.46 0 1 0-1.61 2.39 2.87 2.87 0 0 0 0 .44c0 2.24 2.61 4.06 5.83 4.06s5.83-1.82 5.83-4.06a2.87 2.87 0 0 0 0-.44 1.46 1.46 0 0 0 .68-1.62zM7.27 11a1 1 0 1 1 1 1 1 1 0 0 1-1-1zm5.58 2.71a3.58 3.58 0 0 1-2.85.87 3.58 3.58 0 0 1-2.85-.87.19.19 0 0 1 .27-.27 3.24 3.24 0 0 0 2.58.71 3.24 3.24 0 0 0 2.58-.71.19.19 0 0 1 .27.27zm-.13-1.71a1 1 0 1 1 1-1 1 1 0 0 1-1 1z" fill="white"/></svg>
                Search Reddit
              </button>
            </div>
            <div class="mt-3">
              <div id="reddit-progress" style="height:3px;width:0%;background:linear-gradient(90deg,#FF4500,#FF6534);border-radius:2px;transition:width 0.5s ease"></div>
            </div>
          </div>

          <!-- Results -->
          <div id="reddit-results-container" class="hidden">
            <!-- Results header -->
            <div class="flex items-center justify-between mb-4">
              <div class="text-sm font-medium" style="color:#818384">
                Top Reddit Posts <span id="reddit-count" class="ml-1" style="color:#FF4500"></span>
              </div>
            </div>

            <!-- Posts list (single column, Reddit-style) -->
            <div id="reddit-posts-grid" class="flex flex-col gap-2"></div>

            <!-- AI Summarize button - ABOVE summary panel -->
            <div class="mt-6 mb-2 flex justify-center">
              <button id="reddit-analyze-btn" class="flex items-center gap-2.5 px-6 py-3 rounded-full font-semibold text-sm transition-all hover:opacity-90 hover:scale-105" style="background:#10A37F;color:white;display:none;border:none">
                <!-- ChatGPT logo SVG -->
                <svg width="18" height="18" viewBox="0 0 41 41" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M37.532 16.87a9.963 9.963 0 0 0-.856-8.184 10.078 10.078 0 0 0-10.855-4.835 9.964 9.964 0 0 0-6.65-2.164 10.079 10.079 0 0 0-9.612 6.977 9.967 9.967 0 0 0-6.664 4.834 10.08 10.08 0 0 0 1.24 11.817 9.965 9.965 0 0 0 .856 8.185 10.079 10.079 0 0 0 10.855 4.835 9.965 9.965 0 0 0 6.65 2.164 10.079 10.079 0 0 0 9.614-6.98 9.967 9.967 0 0 0 6.663-4.834 10.079 10.079 0 0 0-1.241-11.817zm-17.223 24.11a7.474 7.474 0 0 1-4.801-1.735c.061-.033.168-.091.237-.134l7.964-4.6a1.294 1.294 0 0 0 .655-1.134V19.054l3.366 1.944a.12.12 0 0 1 .066.092v9.299a7.505 7.505 0 0 1-7.487 7.591zM4.186 34.063a7.471 7.471 0 0 1-.894-5.023c.06.036.162.099.237.141l7.964 4.6a1.297 1.297 0 0 0 1.308 0l9.724-5.614v3.888a.12.12 0 0 1-.048.103L14.4 36.86a7.505 7.505 0 0 1-10.214-2.797zM2.408 13.866a7.471 7.471 0 0 1 3.904-3.288A.12.12 0 0 1 6.3 10.7v9.201a1.294 1.294 0 0 0 .654 1.132l9.723 5.614-3.366 1.944a.12.12 0 0 1-.114.012L4.597 23.86a7.505 7.505 0 0 1-2.189-9.994zm27.555 6.437l-9.724-5.615 3.367-1.943a.121.121 0 0 1 .114-.012l8.6 4.944a7.498 7.498 0 0 1-1.158 13.528v-9.201a1.293 1.293 0 0 0-.199-.701zm3.35-5.043c-.059-.037-.162-.099-.236-.141l-7.965-4.6a1.298 1.298 0 0 0-1.308 0l-9.723 5.614v-3.888a.12.12 0 0 1 .048-.103l8.080-4.165a7.505 7.505 0 0 1 11.104 7.283zm-21.063 6.929l-3.367-1.944a.12.12 0 0 1-.065-.092v-9.299a7.505 7.505 0 0 1 12.293-5.756 6.94 6.94 0 0 0-.236.134l-7.965 4.6a1.294 1.294 0 0 0-.654 1.132l-.006 11.225zm1.829-3.943l4.33-2.501 4.332 2.5v4.999l-4.331 2.5-4.331-2.5V18.246z" fill="currentColor"/>
                </svg>
                Summarize with ChatGPT
              </button>
            </div>

            <!-- AI Summary Panel -->
            <div id="reddit-summary-panel" class="hidden rounded-xl p-6" style="background:#1A1A1B;border:1px solid #343536">
              <div class="flex items-center gap-3 mb-4">
                <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background:#10A37F22">
                  <svg width="18" height="18" viewBox="0 0 41 41" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M37.532 16.87a9.963 9.963 0 0 0-.856-8.184 10.078 10.078 0 0 0-10.855-4.835 9.964 9.964 0 0 0-6.65-2.164 10.079 10.079 0 0 0-9.612 6.977 9.967 9.967 0 0 0-6.664 4.834 10.08 10.08 0 0 0 1.24 11.817 9.965 9.965 0 0 0 .856 8.185 10.079 10.079 0 0 0 10.855 4.835 9.965 9.965 0 0 0 6.65 2.164 10.079 10.079 0 0 0 9.614-6.98 9.967 9.967 0 0 0 6.663-4.834 10.079 10.079 0 0 0-1.241-11.817zm-17.223 24.11a7.474 7.474 0 0 1-4.801-1.735c.061-.033.168-.091.237-.134l7.964-4.6a1.294 1.294 0 0 0 .655-1.134V19.054l3.366 1.944a.12.12 0 0 1 .066.092v9.299a7.505 7.505 0 0 1-7.487 7.591zM4.186 34.063a7.471 7.471 0 0 1-.894-5.023c.06.036.162.099.237.141l7.964 4.6a1.297 1.297 0 0 0 1.308 0l9.724-5.614v3.888a.12.12 0 0 1-.048.103L14.4 36.86a7.505 7.505 0 0 1-10.214-2.797zM2.408 13.866a7.471 7.471 0 0 1 3.904-3.288A.12.12 0 0 1 6.3 10.7v9.201a1.294 1.294 0 0 0 .654 1.132l9.723 5.614-3.366 1.944a.12.12 0 0 1-.114.012L4.597 23.86a7.505 7.505 0 0 1-2.189-9.994zm27.555 6.437l-9.724-5.615 3.367-1.943a.121.121 0 0 1 .114-.012l8.6 4.944a7.498 7.498 0 0 1-1.158 13.528v-9.201a1.293 1.293 0 0 0-.199-.701zm3.35-5.043c-.059-.037-.162-.099-.236-.141l-7.965-4.6a1.298 1.298 0 0 0-1.308 0l-9.723 5.614v-3.888a.12.12 0 0 1 .048-.103l8.080-4.165a7.505 7.505 0 0 1 11.104 7.283zm-21.063 6.929l-3.367-1.944a.12.12 0 0 1-.065-.092v-9.299a7.505 7.505 0 0 1 12.293-5.756 6.94 6.94 0 0 0-.236.134l-7.965 4.6a1.294 1.294 0 0 0-.654 1.132l-.006 11.225zm1.829-3.943l4.33-2.501 4.332 2.5v4.999l-4.331 2.5-4.331-2.5V18.246z" fill="#10A37F"/>
                  </svg>
                </div>
                <div>
                  <div class="font-semibold text-sm" style="color:#10A37F">ChatGPT Analysis</div>
                  <div class="text-[10px] uppercase tracking-widest" style="color:#818384">Summarized from top Reddit posts</div>
                </div>
                <div id="reddit-summary-spinner" class="ml-auto hidden">
                  <div class="w-5 h-5 border-2 rounded-full animate-spin" style="border-color:#10A37F30;border-top-color:#10A37F"></div>
                </div>
              </div>
              <div id="reddit-summary-text" class="text-sm leading-relaxed whitespace-pre-wrap" style="color:#D7DADC"></div>
            </div>
          </div>
        </section>'''

if OLD_REDDIT_HTML in html:
    html = html.replace(OLD_REDDIT_HTML, NEW_REDDIT_HTML)
    ok("Reddit HTML redesigned")
else:
    er("OLD_REDDIT_HTML not found exactly")
    # Try partial match
    idx = html.find('<!-- Reddit Intelligence Section -->')
    ok("  Section found at idx=%d" % idx)

write('templates/index.html', html)
ok("index.html saved")

# =====================================================================
# 3. app.js - replace Reddit frontend with authentic Reddit-style cards
# =====================================================================
js = read('static/js/app.js')

OLD_REDDIT_JS_START = '// ---- Reddit Intelligence Tab ------------------------------------'
OLD_REDDIT_JS_END = """document.getElementById("reddit-query")?.addEventListener("keypress", (e) => {
  if (e.key === "Enter") document.getElementById("reddit-search-btn")?.click();
});"""

start_idx = js.find(OLD_REDDIT_JS_START)
end_idx   = js.find(OLD_REDDIT_JS_END)
if start_idx != -1 and end_idx != -1:
    end_idx += len(OLD_REDDIT_JS_END)
    js = js[:start_idx].rstrip() + '\n' + js[end_idx:].lstrip('\n')
    ok("Old Reddit JS removed")
else:
    er("Reddit JS boundaries not found (start=%d end=%d)" % (start_idx, end_idx))

NEW_REDDIT_JS = """
// ---- Reddit Intelligence Tab ----------------------------------------

let redditPosts = [];

function timeAgo(utc) {
  if (!utc) return "";
  const diff = Math.floor((Date.now() / 1000) - utc);
  if (diff < 60)       return diff + "s ago";
  if (diff < 3600)     return Math.floor(diff/60) + "m ago";
  if (diff < 86400)    return Math.floor(diff/3600) + "h ago";
  if (diff < 2592000)  return Math.floor(diff/86400) + "d ago";
  return Math.floor(diff/2592000) + "mo ago";
}

function fmtScore(n) {
  if (!n) return "0";
  if (n >= 1000) return (n/1000).toFixed(1) + "k";
  return String(n);
}

function buildRedditCard(post) {
  const ratio    = Math.round((post.upvote_ratio || 0) * 100);
  const age      = timeAgo(post.created_utc);
  const comments = post.comments || [];
  const isLink   = !post.is_self && post.external_url && !post.external_url.includes("reddit.com");

  // Comments HTML
  let commentsHTML = "";
  if (comments.length) {
    commentsHTML = `
      <div class="mt-3 pt-3" style="border-top:1px solid #343536">
        <div class="text-[10px] uppercase tracking-widest mb-2" style="color:#818384">
          <i class="fas fa-comment-alt mr-1"></i>Top Comments
        </div>
        ${comments.map(c => `
          <div class="flex gap-2 mb-2">
            <div class="w-5 h-5 rounded-full shrink-0 flex items-center justify-center text-[9px] font-bold mt-0.5" style="background:#FF4500;color:white">
              ${(c.author||"?")[0].toUpperCase()}
            </div>
            <div class="min-w-0">
              <div class="text-[10px] mb-0.5" style="color:#818384">
                <span style="color:#D7DADC;font-weight:600">u/${c.author||"[deleted]"}</span>
                &nbsp;·&nbsp;<i class="fas fa-arrow-up" style="color:#FF4500"></i> ${fmtScore(c.score)}
              </div>
              <div class="text-xs leading-relaxed" style="color:#9EA3A8">${c.body||""}</div>
            </div>
          </div>`).join("")}
      </div>`;
  }

  const card = document.createElement("div");
  card.style.cssText = "background:#1A1A1B;border:1px solid #343536;border-radius:4px;margin-bottom:8px;transition:border-color 0.15s;";
  card.onmouseenter = () => card.style.borderColor = "#818384";
  card.onmouseleave = () => card.style.borderColor = "#343536";

  card.innerHTML = `
    <div class="flex" style="padding:8px 8px 0 4px">
      <!-- Vote column -->
      <div class="flex flex-col items-center shrink-0 pt-1" style="width:40px;gap:2px">
        <button class="text-lg leading-none hover:text-orange-500 transition-colors" style="color:#818384;background:none;border:none;cursor:pointer">▲</button>
        <span class="text-xs font-bold" style="color:#D7DADC">${fmtScore(post.score)}</span>
        <button class="text-lg leading-none hover:text-blue-500 transition-colors" style="color:#818384;background:none;border:none;cursor:pointer">▼</button>
      </div>

      <!-- Content -->
      <div class="flex-1 min-w-0 pl-2">
        <!-- Meta line -->
        <div class="text-[11px] mb-1.5 flex flex-wrap items-center gap-1" style="color:#818384">
          <span class="font-semibold hover:underline cursor-pointer" style="color:#D7DADC">${post.subreddit}</span>
          <span>·</span>
          <span>Posted by <span style="color:#D7DADC">u/${post.author||"[deleted]"}</span></span>
          <span>·</span>
          <span>${age}</span>
          ${post.link_flair ? `<span class="px-1.5 py-0.5 rounded-full text-[10px]" style="background:rgba(255,69,0,0.15);color:#FF4500">${post.link_flair}</span>` : ""}
        </div>

        <!-- Title -->
        <a href="${post.url}" target="_blank" rel="noopener noreferrer"
          class="block text-sm font-medium leading-snug mb-2 hover:text-blue-400 transition-colors"
          style="color:#D7DADC;text-decoration:none">
          ${post.title}
          ${isLink ? `<span class="text-[10px] ml-1" style="color:#818384">(${post.domain})</span>` : ""}
        </a>

        <!-- Body preview -->
        ${post.selftext ? `<p class="text-xs leading-relaxed mb-2" style="color:#9EA3A8">${post.selftext.slice(0,220).replace(/</g,"&lt;")}${post.selftext.length>220?"...":""}</p>` : ""}

        <!-- Comments section -->
        ${commentsHTML}

        <!-- Action bar -->
        <div class="flex items-center gap-1 mt-3 pb-2 text-[11px] font-medium" style="color:#818384">
          <a href="${post.url}" target="_blank" rel="noopener noreferrer"
            class="flex items-center gap-1.5 px-2 py-1.5 rounded hover:bg-white/5 transition-colors cursor-pointer"
            style="color:#818384;text-decoration:none">
            <i class="fas fa-comment-alt"></i>
            ${(post.num_comments||0).toLocaleString()} Comments
          </a>
          <span class="flex items-center gap-1.5 px-2 py-1.5 rounded hover:bg-white/5 transition-colors cursor-pointer">
            <i class="fas fa-share"></i> Share
          </span>
          <span class="flex items-center gap-1.5 px-2 py-1.5 rounded hover:bg-white/5 transition-colors cursor-pointer">
            <i class="fas fa-bookmark"></i> Save
          </span>
          <span class="ml-auto text-[10px]" style="color:#818384">
            <i class="fas fa-arrow-up" style="color:#FF4500"></i> ${ratio}% upvoted
          </span>
        </div>
      </div>
    </div>`;

  return card;
}

document.getElementById("reddit-search-btn")?.addEventListener("click", async () => {
  const query        = document.getElementById("reddit-query").value.trim();
  const progressEl   = document.getElementById("reddit-progress");
  const analyzeBtn   = document.getElementById("reddit-analyze-btn");
  const container    = document.getElementById("reddit-results-container");
  const postsGrid    = document.getElementById("reddit-posts-grid");
  const summaryPanel = document.getElementById("reddit-summary-panel");
  const countEl      = document.getElementById("reddit-count");

  if (!query) return alert("Please enter a search query.");

  progressEl.style.width = "15%";
  summaryPanel.classList.add("hidden");
  analyzeBtn.style.display = "none";
  container.classList.remove("hidden");
  postsGrid.innerHTML = `
    <div style="padding:40px;text-align:center">
      <div style="width:40px;height:40px;border:3px solid rgba(255,69,0,0.2);border-top-color:#FF4500;border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto 12px"></div>
      <div style="color:#FF4500;font-size:12px;text-transform:uppercase;letter-spacing:0.1em">Searching Reddit...</div>
    </div>`;

  sysLog("OSINT", "Searching Reddit for: " + query, "info");

  try {
    progressEl.style.width = "45%";
    const res  = await fetch("/api/reddit/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    progressEl.style.width = "85%";
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Search failed");

    redditPosts = data.posts || [];
    progressEl.style.width = "100%";
    countEl.textContent = redditPosts.length + " posts";
    sysLog("OSINT", "Found " + redditPosts.length + " Reddit posts for: " + query, "success");

    postsGrid.innerHTML = "";
    if (!redditPosts.length) {
      postsGrid.innerHTML = `<div style="padding:40px;text-align:center;color:#818384">No Reddit posts found for this query.</div>`;
    } else {
      redditPosts.forEach(post => postsGrid.appendChild(buildRedditCard(post)));
      analyzeBtn.style.display = "";
    }
    setTimeout(() => { progressEl.style.width = "0%"; }, 1000);
  } catch (err) {
    sysLog("OSINT", "Reddit error: " + err.message, "error");
    postsGrid.innerHTML = `<div style="padding:30px;text-align:center;color:#ef4444">${err.message}</div>`;
    progressEl.style.width = "0%";
  }
});

document.getElementById("reddit-analyze-btn")?.addEventListener("click", async () => {
  if (!redditPosts.length) return;
  const summaryPanel = document.getElementById("reddit-summary-panel");
  const summaryText  = document.getElementById("reddit-summary-text");
  const spinner      = document.getElementById("reddit-summary-spinner");
  const query        = document.getElementById("reddit-query").value.trim();

  summaryPanel.classList.remove("hidden");
  summaryText.textContent = "";
  spinner.classList.remove("hidden");
  sysLog("OSINT", "ChatGPT analyzing " + redditPosts.length + " Reddit posts...", "warn");

  try {
    const res = await fetch("/api/reddit/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        posts: redditPosts.slice(0, 10).map(p => ({ url: p.url, title: p.title })),
      }),
    });
    const data = await res.json();
    spinner.classList.add("hidden");
    if (!res.ok) throw new Error(data.error || "Analysis failed");
    summaryText.textContent = data.summary;
    sysLog("OSINT", "ChatGPT summary complete for: " + query, "success");
  } catch (err) {
    spinner.classList.add("hidden");
    summaryText.textContent = "Error: " + err.message;
    sysLog("OSINT", "AI error: " + err.message, "error");
  }
});

document.getElementById("reddit-query")?.addEventListener("keypress", (e) => {
  if (e.key === "Enter") document.getElementById("reddit-search-btn")?.click();
});
"""

js = js.rstrip() + '\n' + NEW_REDDIT_JS + '\n'
write('static/js/app.js', js)
ok("Reddit frontend JS replaced with authentic Reddit cards")
ok("app.js saved (" + str(js.count('\n')) + " lines)")

print("\n=== Reddit redesign complete ===")


# ============================================================
# SECTION: patch_reddit_accuracy.py
# ============================================================

import re, ast

def read(path):
    with open(path,'r',encoding='utf-8') as f: return f.read()
def write(path,c):
    with open(path,'w',encoding='utf-8') as f: f.write(c)
def ok(m): print("[OK] "+m)

app_py = read('app.py')

# 1. Update fetch_top_comments to fetch_full_reddit_post (which returns {post_data, comments})
OLD_FETCH_COMMENTS = '''def fetch_top_comments(permalink, limit=2):
    """Fetch top N comments for a given Reddit permalink."""
    try:
        json_url = "https://www.reddit.com" + permalink + ".json?limit=5&sort=top"
        r = requests.get(json_url, headers=REDDIT_HEADERS, timeout=8)
        if r.status_code != 200:
            return []
        data = r.json()
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
        return comments
    except Exception:
        return []'''

NEW_FETCH_POST = '''def fetch_full_reddit_post(permalink, limit=2):
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
        return None'''

app_py = app_py.replace(OLD_FETCH_COMMENTS, NEW_FETCH_POST)
ok("fetch_full_reddit_post injected")


OLD_REDDIT_SEARCH = '''def reddit_search(query, limit=10):
    """Search Reddit using public JSON API - no auth required. Includes top 2 comments per post."""
    results = []
    try:
        params = {
            "q": query, "sort": "relevance",
            "limit": min(limit, 25), "t": "year", "type": "link",
        }
        r = requests.get(
            "https://www.reddit.com/search.json",
            params=params, headers=REDDIT_HEADERS, timeout=12,
        )
        if r.status_code != 200:
            return results, "Reddit returned HTTP %d" % r.status_code

        raw_posts = []
        for child in r.json().get("data", {}).get("children", []):
            p = child.get("data", {})
            raw_posts.append({
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
                "comments":     [],
            })

        # Fetch top 2 comments for each post in parallel
        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = {ex.submit(fetch_top_comments, p["permalink"], 2): i
                       for i, p in enumerate(raw_posts)}
            for ft, idx in futures.items():
                raw_posts[idx]["comments"] = ft.result()

        results = raw_posts
    except Exception as ex:
        return results, str(ex)
    return results, None'''

NEW_REDDIT_SEARCH = '''def reddit_search(query, limit=10):
    """
    Search Reddit using DuckDuckGo HTML for highly accurate relevance matching,
    then fetch rich native post JSON including top comments.
    """
    results = []
    try:
        # Step 1: Search via DuckDuckGo for site:reddit.com
        dork_query = f"site:reddit.com {query}"
        ddg_results = _ddg_html_search(dork_query, limit=15)
        
        # Extract unique permalinks
        permalinks = []
        seen = set()
        for res in ddg_results:
            m = re.search(r'reddit\.com(/r/[^/]+/comments/[^/]+/[^/?&#]+)', res["url"])
            if m:
                p = m.group(1)
                if p not in seen:
                    seen.add(p)
                    permalinks.append(p)
                    
            if len(permalinks) >= limit:
                break
                
        if not permalinks:
            return [], "No relevant Reddit discussions found via search."

        # Step 2: Fetch rich data for all found permalinks in parallel
        raw_posts = []
        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = [ex.submit(fetch_full_reddit_post, p, 2) for p in permalinks]
            for ft in futures:
                post_data = ft.result()
                if post_data:
                    raw_posts.append(post_data)

        # Sort results by score (descending) combined with how high they ranked in DDG
        # For simplicity, maintaining the DDG relevance order is usually best
        results = raw_posts
        
    except Exception as ex:
        return results, str(ex)
    return results, None'''

app_py = app_py.replace(OLD_REDDIT_SEARCH, NEW_REDDIT_SEARCH)
ok("reddit_search updated with DuckDuckGo accuracy logic")

write('app.py', app_py)
ast.parse(app_py)
ok("syntax OK, saved")


# ============================================================
# SECTION: patch_reddit_native.py
# ============================================================

import ast

def read(path):
    with open(path,'r',encoding='utf-8') as f: return f.read()
def write(path,c):
    with open(path,'w',encoding='utf-8') as f: f.write(c)

app_py = read('app.py')

NEW_REDDIT_SEARCH = '''def reddit_search(query, limit=10):
    """
    Search Reddit using native JSON for the exact behavior of the mobile app,
    mixing 'hot' (top active) and 'new' (latest) posts.
    """
    results = []
    try:
        hot_plinks = []
        new_plinks = []
        
        # 1. Fetch HOT (Top active)
        try:
            r = requests.get(
                "https://www.reddit.com/search.json",
                params={"q": query, "sort": "hot", "t": "all", "limit": 15, "type": "link"},
                headers=REDDIT_HEADERS, timeout=8
            )
            if r.status_code == 200:
                hot_plinks = [c["data"]["permalink"] for c in r.json().get("data", {}).get("children", [])]
        except: pass

        # 2. Fetch NEW (Latest)
        try:
            r = requests.get(
                "https://www.reddit.com/search.json",
                params={"q": query, "sort": "new", "t": "all", "limit": 15, "type": "link"},
                headers=REDDIT_HEADERS, timeout=8
            )
            if r.status_code == 200:
                new_plinks = [c["data"]["permalink"] for c in r.json().get("data", {}).get("children", [])]
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
            if len(permalinks) >= limit:
                break
                
        if not permalinks:
            return [], "No Reddit posts found."

        # 4. Fetch rich data + comments for the selected permalinks
        raw_posts = []
        with ThreadPoolExecutor(max_workers=min(limit, 10)) as ex:
            # We want to preserve the interleaved order
            futures = {ex.submit(fetch_full_reddit_post, p, 2): i for i, p in enumerate(permalinks)}
            sorted_posts = [None] * len(permalinks)
            for ft in futures:
                idx = futures[ft]
                try:
                    res = ft.result()
                    if res: sorted_posts[idx] = res
                except: pass
                
            raw_posts = [p for p in sorted_posts if p]

        results = raw_posts
    except Exception as ex:
        return results, str(ex)
    return results, None'''

start = app_py.find('def reddit_search')
end = app_py.find('\n\n\n', start)
if end == -1: end = app_py.find('\n@app.route', start)

app_py = app_py[:start] + NEW_REDDIT_SEARCH + app_py[end:]

try:
    ast.parse(app_py)
    write('app.py', app_py)
    print("Patch applied successfully, syntax OK.")
except SyntaxError as e:
    print("Syntax error:", e)


# ============================================================
# SECTION: patch_redesign.py
# ============================================================

import re, ast

def read(path):
    with open(path,'r',encoding='utf-8') as f: return f.read()
def write(path,c):
    with open(path,'w',encoding='utf-8') as f: f.write(c)
def ok(m):  print("[OK]  "+m)
def err(m): print("[ERR] "+m)

# =====================================================================
# 1. app.py - add Google Dork search (via SearXNG free API) + fix ai prompt
# =====================================================================
app_py = read('app.py')

# Replace extractive_summarize + ai_summarize with improved versions that
# return plain-text (no markdown) so the frontend can render it cleanly
OLD_AI = '''def ai_summarize(query, posts_content):
    """Summarize using Pollinations.ai (free ChatGPT, no login needed).
    Falls back to local extractive summarization if unavailable."""
    combined_parts = []
    for i, t in enumerate(posts_content, 1):
        if t:
            combined_parts.append("--- Post %d ---\\n%s" % (i, t[:500]))
    combined = "\\n\\n".join(combined_parts)[:4000]

    prompt = (
        "You are a cybersecurity analyst AI. "
        "A user searched Reddit for: \\'%s\\'\\n\\n"
        "Here are excerpts from the top Reddit posts on this topic:\\n\\n"
        "%s\\n\\n"
        "Please provide a comprehensive analysis that:\\n"
        "1. Summarizes the key findings from these community posts\\n"
        "2. Highlights any warnings, threat indicators, or security risks mentioned\\n"
        "3. Notes the community consensus or notable disagreements\\n"
        "4. Provides practical takeaways for a security professional\\n"
        "Be concise, factual, and security-focused."
    ) % (query, combined)

    # Try Pollinations.ai (free ChatGPT/OpenAI, no key needed)
    try:
        r = requests.post(
            "https://text.pollinations.ai/",
            json={
                "messages": [{"role": "user", "content": prompt}],
                "model": "openai",
                "seed": 42,
            },
            headers={"Content-Type": "application/json"},
            timeout=45,
        )
        if r.status_code == 200 and r.text.strip():
            return r.text.strip()
    except Exception:
        pass

    # Fallback to HuggingFace
    try:
        hf_prompt = "Summarize these Reddit posts about %s:\\n%s" % (query, combined[:2500])
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

    return extractive_summarize(query, posts_content)'''

NEW_AI = '''def ai_summarize(query, posts_content, source="Reddit"):
    """
    Summarize using Pollinations.ai (free ChatGPT, no login).
    Returns PLAIN TEXT - no markdown, no asterisks, no tables.
    Falls back to local extractive summarization.
    """
    combined_parts = []
    for i, t in enumerate(posts_content, 1):
        if t:
            combined_parts.append("Post %d: %s" % (i, t[:450]))
    combined = "\\n\\n".join(combined_parts)[:4000]

    prompt = (
        "You are a cybersecurity analyst. A user searched %s for: \\"%s\\"\\n\\n"
        "Here are excerpts from the top posts:\\n\\n%s\\n\\n"
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
            text = re.sub(r"\\*\\*|__|\\_|\\|\\*", "", text)
            text = re.sub(r"^#{1,6}\\s+", "", text, flags=re.MULTILINE)
            text = re.sub(r"^\\|.*\\|.*$", "", text, flags=re.MULTILINE)
            text = re.sub(r"^[-]+$", "", text, flags=re.MULTILINE)
            text = re.sub(r"\\n{3,}", "\\n\\n", text).strip()
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

SEARX_INSTANCES = [
    "https://searx.be",
    "https://searxng.site",
    "https://search.sapti.me",
    "https://searx.tiekoetter.com",
]

def google_dork_search(query, limit=10):
    """Search Google/Bing/DDG results via SearXNG free public instances."""
    results = []
    last_error = "All instances unavailable"

    for instance in SEARX_INSTANCES:
        try:
            params = {
                "q": query, "format": "json",
                "engines": "google,bing,duckduckgo",
                "pageno": 1, "language": "en",
            }
            r = requests.get(
                instance + "/search",
                params=params,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=12,
            )
            if r.status_code == 200:
                data = r.json()
                for item in data.get("results", [])[:limit]:
                    results.append({
                        "title":   item.get("title", ""),
                        "url":     item.get("url", ""),
                        "snippet": item.get("content", ""),
                        "engines": ", ".join(item.get("engines", [])),
                        "score":   round(item.get("score", 0), 2),
                        "published_date": item.get("publishedDate", ""),
                        "thumbnail": item.get("img_src", ""),
                    })
                if results:
                    return results, None
        except Exception as ex:
            last_error = str(ex)
            continue

    return results, last_error


def fetch_web_page_text(url):
    """Fetch simplified text content from a web URL for summarization."""
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        text = re.sub(r"<[^>]+>", " ", r.text)
        text = re.sub(r"\\s{2,}", " ", text).strip()
        return text[:800]
    except Exception:
        return ""'''

if OLD_AI in app_py:
    app_py = app_py.replace(OLD_AI, NEW_AI)
    ok("ai_summarize upgraded (plain text, Google search added)")
else:
    err("OLD_AI not found")

# Add Google search routes before `if __name__`
GOOGLE_ROUTES = '''

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
        enriched.append("TITLE: %s\\nSNIPPET: %s\\n%s" % (res.get("title",""), res.get("snippet",""), txt))

    summary = ai_summarize(query, enriched, source="Google")
    return jsonify({"summary": summary, "results_analyzed": len(enriched)})

'''

if '/api/reddit/analyze' in app_py and '/api/google/search' not in app_py:
    app_py = app_py.replace(
        '\nif __name__ == "__main__":',
        GOOGLE_ROUTES + '\nif __name__ == "__main__":'
    )
    ok("Google Dork backend routes added")
else:
    ok("Google routes already present or reddit route not found")

# Also fix the reddit analyze route to pass source="Reddit"
app_py = app_py.replace(
    '    summary = ai_summarize(query, enriched)\n    return jsonify({"summary": summary, "posts_analyzed": len(enriched)})',
    '    summary = ai_summarize(query, enriched, source="Reddit")\n    return jsonify({"summary": summary, "posts_analyzed": len(enriched)})'
)

write('app.py', app_py)
try:
    ast.parse(app_py)
    ok("app.py syntax OK")
except SyntaxError as e:
    err("Syntax error line %d: %s" % (e.lineno, e.msg))

# =====================================================================
# 2. HTML - Add marked.js CDN, Google nav button, Google tab section
# =====================================================================
html = read('templates/index.html')

# Add marked.js before </head>
if 'marked' not in html:
    html = html.replace(
        '</head>',
        '  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>\n</head>'
    )
    ok("marked.js CDN added")

# Add Google nav button after Reddit nav button
OLD_GOOGLE_NAV = '          <button class="nav-link w-full flex items-center gap-3 text-fuchsia-400" data-target="sandbox">'
NEW_GOOGLE_NAV = '''          <button class="nav-link w-full flex items-center gap-3" style="color:#4285F4" data-target="google">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            Google Dork
          </button>
          <button class="nav-link w-full flex items-center gap-3 text-fuchsia-400" data-target="sandbox">'''

if OLD_GOOGLE_NAV in html:
    html = html.replace(OLD_GOOGLE_NAV, NEW_GOOGLE_NAV)
    ok("Google nav button added")
else:
    err("Sandbox nav marker not found")

# ── Reddit section redesign (cyberpunk dark theme matching app style) ──
OLD_REDDIT_SECTION = html[html.find('        <!-- Reddit Intelligence Section -->'):html.find('        <section id="sandbox"')]

REDDIT_CYBERPUNK = '''        <!-- Reddit Intelligence Section -->
        <section id="reddit" class="section-block hidden">
          <div class="flex items-center gap-3 mb-2">
            <div class="w-9 h-9 rounded-lg flex items-center justify-center" style="background:rgba(255,69,0,0.15);box-shadow:0 0 16px rgba(255,69,0,0.3)">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="#FF4500"><circle cx="10" cy="10" r="10" fill="#FF4500"/><path d="M16.67 10a1.46 1.46 0 0 0-2.47-1 7.12 7.12 0 0 0-3.85-1.23l.65-3.07 2.13.45a1 1 0 1 0 1-.97 1 1 0 0 0-.96.68l-2.38-.5a.27.27 0 0 0-.32.2l-.73 3.44a7.14 7.14 0 0 0-3.89 1.23 1.46 1.46 0 1 0-1.61 2.39 2.87 2.87 0 0 0 0 .44c0 2.24 2.61 4.06 5.83 4.06s5.83-1.82 5.83-4.06a2.87 2.87 0 0 0 0-.44 1.46 1.46 0 0 0 .68-1.62zM7.27 11a1 1 0 1 1 1 1 1 1 0 0 1-1-1zm5.58 2.71a3.58 3.58 0 0 1-2.85.87 3.58 3.58 0 0 1-2.85-.87.19.19 0 0 1 .27-.27 3.24 3.24 0 0 0 2.58.71 3.24 3.24 0 0 0 2.58-.71.19.19 0 0 1 .27.27zm-.13-1.71a1 1 0 1 1 1-1 1 1 0 0 1-1 1z" fill="white"/></svg>
            </div>
            <div>
              <h2 class="text-xl font-bold tracking-wide" style="color:#FF4500">Reddit Intelligence</h2>
              <div class="text-[10px] uppercase tracking-widest" style="color:rgba(255,69,0,0.5)">Community threat intelligence search</div>
            </div>
          </div>

          <div class="neon-panel p-5 mt-4 mb-6" style="border-color:rgba(255,69,0,0.25);box-shadow:0 0 20px rgba(255,69,0,0.08)">
            <div class="grid grid-cols-1 lg:grid-cols-5 gap-4">
              <div class="lg:col-span-4">
                <label class="label">Search Query</label>
                <input id="reddit-query" class="input-neon" style="border-color:rgba(255,69,0,0.3);caret-color:#FF4500"
                  placeholder="CVE-2024-21413   ransomware screenshot 2024   keylogger malware..." />
              </div>
              <div class="flex items-end">
                <button id="reddit-search-btn" class="btn-neon w-full hover:shadow-[0_0_18px_rgba(255,69,0,0.4)]" style="color:#FF4500;border-color:#FF4500">
                  <svg class="inline mr-2" width="14" height="14" viewBox="0 0 20 20" fill="#FF4500"><circle cx="10" cy="10" r="10"/><path d="M16.67 10a1.46 1.46 0 0 0-2.47-1 7.12 7.12 0 0 0-3.85-1.23l.65-3.07 2.13.45a1 1 0 1 0 1-.97 1 1 0 0 0-.96.68l-2.38-.5a.27.27 0 0 0-.32.2l-.73 3.44a7.14 7.14 0 0 0-3.89 1.23 1.46 1.46 0 1 0-1.61 2.39 2.87 2.87 0 0 0 0 .44c0 2.24 2.61 4.06 5.83 4.06s5.83-1.82 5.83-4.06a2.87 2.87 0 0 0 0-.44 1.46 1.46 0 0 0 .68-1.62zM7.27 11a1 1 0 1 1 1 1 1 1 0 0 1-1-1zm5.58 2.71a3.58 3.58 0 0 1-2.85.87 3.58 3.58 0 0 1-2.85-.87.19.19 0 0 1 .27-.27 3.24 3.24 0 0 0 2.58.71 3.24 3.24 0 0 0 2.58-.71.19.19 0 0 1 .27.27zm-.13-1.71a1 1 0 1 1 1-1 1 1 0 0 1-1 1z" fill="white"/></svg>
                  Search Reddit
                </button>
              </div>
            </div>
            <div class="mt-3">
              <div id="reddit-progress" style="height:2px;width:0%;background:linear-gradient(90deg,#FF4500,#ff6b35);border-radius:2px;transition:width 0.4s ease;box-shadow:0 0 8px #FF4500"></div>
            </div>
          </div>

          <div id="reddit-results-container" class="hidden">
            <div class="flex items-center justify-between mb-4">
              <div class="text-xs uppercase tracking-widest font-bold" style="color:#FF4500">
                <i class="fab fa-reddit mr-1"></i> Top Posts
                <span id="reddit-count" class="ml-2 opacity-60 normal-case tracking-normal font-normal"></span>
              </div>
            </div>

            <div id="reddit-posts-grid" class="flex flex-col gap-3"></div>

            <div class="mt-6 flex justify-center">
              <button id="reddit-analyze-btn" class="flex items-center gap-2.5 px-7 py-3 rounded-full font-bold text-sm transition-all hover:scale-105" style="background:#10A37F;color:white;border:none;display:none;box-shadow:0 0 20px rgba(16,163,127,0.3)">
                <svg width="18" height="18" viewBox="0 0 41 41" fill="none"><path d="M37.532 16.87a9.963 9.963 0 0 0-.856-8.184 10.078 10.078 0 0 0-10.855-4.835 9.964 9.964 0 0 0-6.65-2.164 10.079 10.079 0 0 0-9.612 6.977 9.967 9.967 0 0 0-6.664 4.834 10.08 10.08 0 0 0 1.24 11.817 9.965 9.965 0 0 0 .856 8.185 10.079 10.079 0 0 0 10.855 4.835 9.965 9.965 0 0 0 6.65 2.164 10.079 10.079 0 0 0 9.614-6.98 9.967 9.967 0 0 0 6.663-4.834 10.079 10.079 0 0 0-1.241-11.817zm-17.223 24.11a7.474 7.474 0 0 1-4.801-1.735c.061-.033.168-.091.237-.134l7.964-4.6a1.294 1.294 0 0 0 .655-1.134V19.054l3.366 1.944a.12.12 0 0 1 .066.092v9.299a7.505 7.505 0 0 1-7.487 7.591zM4.186 34.063a7.471 7.471 0 0 1-.894-5.023c.06.036.162.099.237.141l7.964 4.6a1.297 1.297 0 0 0 1.308 0l9.724-5.614v3.888a.12.12 0 0 1-.048.103L14.4 36.86a7.505 7.505 0 0 1-10.214-2.797zM2.408 13.866a7.471 7.471 0 0 1 3.904-3.288c0 .033-.001.065 0 .122v9.201a1.294 1.294 0 0 0 .654 1.132l9.723 5.614-3.366 1.944a.12.12 0 0 1-.114.012L4.597 23.86a7.505 7.505 0 0 1-2.189-9.994zm27.555 6.437l-9.724-5.615 3.367-1.943a.121.121 0 0 1 .114-.012l8.6 4.944a7.498 7.498 0 0 1-1.158 13.528v-9.201a1.293 1.293 0 0 0-.2-.701zm3.35-5.043c-.059-.037-.162-.099-.236-.141l-7.965-4.6a1.298 1.298 0 0 0-1.308 0l-9.723 5.614v-3.888a.12.12 0 0 1 .048-.103l8.08-4.165a7.505 7.505 0 0 1 11.104 7.283zm-21.063 6.929l-3.367-1.944a.12.12 0 0 1-.065-.092v-9.299a7.505 7.505 0 0 1 12.293-5.756 6.94 6.94 0 0 0-.236.134l-7.965 4.6a1.294 1.294 0 0 0-.654 1.132l-.006 11.225zm1.829-3.943l4.33-2.501 4.332 2.5v4.999l-4.331 2.5-4.331-2.5V18.246z" fill="currentColor"/></svg>
                Summarize with ChatGPT
              </button>
            </div>

            <div id="reddit-summary-panel" class="hidden neon-panel p-6 mt-4" style="border-color:rgba(16,163,127,0.3);box-shadow:0 0 20px rgba(16,163,127,0.08)">
              <div class="flex items-center gap-3 mb-4">
                <div class="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style="background:rgba(16,163,127,0.15)">
                  <svg width="16" height="16" viewBox="0 0 41 41" fill="none"><path d="M37.532 16.87a9.963 9.963 0 0 0-.856-8.184 10.078 10.078 0 0 0-10.855-4.835 9.964 9.964 0 0 0-6.65-2.164 10.079 10.079 0 0 0-9.612 6.977 9.967 9.967 0 0 0-6.664 4.834 10.08 10.08 0 0 0 1.24 11.817 9.965 9.965 0 0 0 .856 8.185 10.079 10.079 0 0 0 10.855 4.835 9.965 9.965 0 0 0 6.65 2.164 10.079 10.079 0 0 0 9.614-6.98 9.967 9.967 0 0 0 6.663-4.834 10.079 10.079 0 0 0-1.241-11.817zm-17.223 24.11a7.474 7.474 0 0 1-4.801-1.735c.061-.033.168-.091.237-.134l7.964-4.6a1.294 1.294 0 0 0 .655-1.134V19.054l3.366 1.944a.12.12 0 0 1 .066.092v9.299a7.505 7.505 0 0 1-7.487 7.591zM4.186 34.063a7.471 7.471 0 0 1-.894-5.023c.06.036.162.099.237.141l7.964 4.6a1.297 1.297 0 0 0 1.308 0l9.724-5.614v3.888a.12.12 0 0 1-.048.103L14.4 36.86a7.505 7.505 0 0 1-10.214-2.797zM2.408 13.866a7.471 7.471 0 0 1 3.904-3.288c0 .033-.001.065 0 .122v9.201a1.294 1.294 0 0 0 .654 1.132l9.723 5.614-3.366 1.944a.12.12 0 0 1-.114.012L4.597 23.86a7.505 7.505 0 0 1-2.189-9.994zm27.555 6.437l-9.724-5.615 3.367-1.943a.121.121 0 0 1 .114-.012l8.6 4.944a7.498 7.498 0 0 1-1.158 13.528v-9.201a1.293 1.293 0 0 0-.2-.701zm3.35-5.043c-.059-.037-.162-.099-.236-.141l-7.965-4.6a1.298 1.298 0 0 0-1.308 0l-9.723 5.614v-3.888a.12.12 0 0 1 .048-.103l8.08-4.165a7.505 7.505 0 0 1 11.104 7.283zm-21.063 6.929l-3.367-1.944a.12.12 0 0 1-.065-.092v-9.299a7.505 7.505 0 0 1 12.293-5.756 6.94 6.94 0 0 0-.236.134l-7.965 4.6a1.294 1.294 0 0 0-.654 1.132l-.006 11.225zm1.829-3.943l4.33-2.501 4.332 2.5v4.999l-4.331 2.5-4.331-2.5V18.246z" fill="#10A37F"/></svg>
                </div>
                <div>
                  <div class="font-bold text-sm" style="color:#10A37F">ChatGPT Analysis</div>
                  <div class="text-[10px] uppercase tracking-widest" style="color:#818384">AI Intelligence Summary — Reddit</div>
                </div>
                <div id="reddit-summary-spinner" class="ml-auto hidden">
                  <div class="w-5 h-5 border-2 rounded-full animate-spin" style="border-color:rgba(16,163,127,0.2);border-top-color:#10A37F"></div>
                </div>
              </div>
              <div id="reddit-summary-text" class="text-sm leading-relaxed" style="color:#cbd5e1;white-space:pre-wrap;font-family:inherit"></div>
            </div>
          </div>
        </section>

        <!-- Google Dork Intelligence Section -->
        <section id="google" class="section-block hidden">
          <div class="flex items-center gap-3 mb-2">
            <div class="w-9 h-9 rounded-lg flex items-center justify-center" style="background:rgba(66,133,244,0.1);box-shadow:0 0 16px rgba(66,133,244,0.2)">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
            </div>
            <div>
              <h2 class="text-xl font-bold tracking-wide" style="color:#4285F4">Google Dork Intelligence</h2>
              <div class="text-[10px] uppercase tracking-widest" style="color:rgba(66,133,244,0.5)">Advanced web search with dorking operators</div>
            </div>
          </div>

          <div class="neon-panel p-5 mt-4 mb-6" style="border-color:rgba(66,133,244,0.2);box-shadow:0 0 20px rgba(66,133,244,0.06)">
            <div class="grid grid-cols-1 lg:grid-cols-5 gap-4">
              <div class="lg:col-span-4">
                <label class="label">Search / Dork Query</label>
                <input id="google-query" class="input-neon" style="border-color:rgba(66,133,244,0.3);caret-color:#4285F4"
                  placeholder='site:pastebin.com "CVE-2024"   inurl:admin "login"   filetype:pdf malware analysis 2024...' />
              </div>
              <div class="flex items-end">
                <button id="google-search-btn" class="btn-neon w-full hover:shadow-[0_0_18px_rgba(66,133,244,0.4)]" style="color:#4285F4;border-color:#4285F4">
                  <svg class="inline mr-2" width="13" height="13" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
                  Google Dork
                </button>
              </div>
            </div>
            <!-- Dork shortcuts -->
            <div class="mt-3 flex flex-wrap gap-2">
              <span class="text-[10px] uppercase tracking-widest mr-1" style="color:rgba(66,133,244,0.5)">Quick Dorks:</span>
              <button onclick="document.getElementById('google-query').value='site:pastebin.com '+document.getElementById('google-query').value" class="text-[10px] px-2 py-0.5 rounded border" style="color:#4285F4;border-color:rgba(66,133,244,0.3)">site:pastebin</button>
              <button onclick="document.getElementById('google-query').value='filetype:pdf '+document.getElementById('google-query').value" class="text-[10px] px-2 py-0.5 rounded border" style="color:#34A853;border-color:rgba(52,168,83,0.3)">filetype:pdf</button>
              <button onclick="document.getElementById('google-query').value='inurl:admin '+document.getElementById('google-query').value" class="text-[10px] px-2 py-0.5 rounded border" style="color:#FBBC05;border-color:rgba(251,188,5,0.3)">inurl:admin</button>
              <button onclick="document.getElementById('google-query').value='intitle:index.of '+document.getElementById('google-query').value" class="text-[10px] px-2 py-0.5 rounded border" style="color:#EA4335;border-color:rgba(234,67,53,0.3)">intitle:index.of</button>
              <button onclick="document.getElementById('google-query').value='intext:password '+document.getElementById('google-query').value" class="text-[10px] px-2 py-0.5 rounded border" style="color:#a78bfa;border-color:rgba(167,139,250,0.3)">intext:password</button>
            </div>
            <div class="mt-3">
              <div id="google-progress" style="height:2px;width:0%;background:linear-gradient(90deg,#4285F4,#34A853,#FBBC05,#EA4335);border-radius:2px;transition:width 0.4s ease;box-shadow:0 0 8px #4285F4"></div>
            </div>
          </div>

          <div id="google-results-container" class="hidden">
            <div class="flex items-center justify-between mb-4">
              <div class="text-xs uppercase tracking-widest font-bold" style="color:#4285F4">
                <i class="fas fa-globe mr-1"></i> Web Results
                <span id="google-count" class="ml-2 opacity-60 normal-case tracking-normal font-normal"></span>
              </div>
            </div>

            <div id="google-results-grid" class="flex flex-col gap-3"></div>

            <div class="mt-6 flex justify-center">
              <button id="google-analyze-btn" class="flex items-center gap-2.5 px-7 py-3 rounded-full font-bold text-sm transition-all hover:scale-105" style="background:#10A37F;color:white;border:none;display:none;box-shadow:0 0 20px rgba(16,163,127,0.3)">
                <svg width="18" height="18" viewBox="0 0 41 41" fill="none"><path d="M37.532 16.87a9.963 9.963 0 0 0-.856-8.184 10.078 10.078 0 0 0-10.855-4.835 9.964 9.964 0 0 0-6.65-2.164 10.079 10.079 0 0 0-9.612 6.977 9.967 9.967 0 0 0-6.664 4.834 10.08 10.08 0 0 0 1.24 11.817 9.965 9.965 0 0 0 .856 8.185 10.079 10.079 0 0 0 10.855 4.835 9.965 9.965 0 0 0 6.65 2.164 10.079 10.079 0 0 0 9.614-6.98 9.967 9.967 0 0 0 6.663-4.834 10.079 10.079 0 0 0-1.241-11.817zm-17.223 24.11a7.474 7.474 0 0 1-4.801-1.735c.061-.033.168-.091.237-.134l7.964-4.6a1.294 1.294 0 0 0 .655-1.134V19.054l3.366 1.944a.12.12 0 0 1 .066.092v9.299a7.505 7.505 0 0 1-7.487 7.591zM4.186 34.063a7.471 7.471 0 0 1-.894-5.023c.06.036.162.099.237.141l7.964 4.6a1.297 1.297 0 0 0 1.308 0l9.724-5.614v3.888a.12.12 0 0 1-.048.103L14.4 36.86a7.505 7.505 0 0 1-10.214-2.797zM2.408 13.866a7.471 7.471 0 0 1 3.904-3.288c0 .033-.001.065 0 .122v9.201a1.294 1.294 0 0 0 .654 1.132l9.723 5.614-3.366 1.944a.12.12 0 0 1-.114.012L4.597 23.86a7.505 7.505 0 0 1-2.189-9.994zm27.555 6.437l-9.724-5.615 3.367-1.943a.121.121 0 0 1 .114-.012l8.6 4.944a7.498 7.498 0 0 1-1.158 13.528v-9.201a1.293 1.293 0 0 0-.2-.701zm3.35-5.043c-.059-.037-.162-.099-.236-.141l-7.965-4.6a1.298 1.298 0 0 0-1.308 0l-9.723 5.614v-3.888a.12.12 0 0 1 .048-.103l8.08-4.165a7.505 7.505 0 0 1 11.104 7.283zm-21.063 6.929l-3.367-1.944a.12.12 0 0 1-.065-.092v-9.299a7.505 7.505 0 0 1 12.293-5.756 6.94 6.94 0 0 0-.236.134l-7.965 4.6a1.294 1.294 0 0 0-.654 1.132l-.006 11.225zm1.829-3.943l4.33-2.501 4.332 2.5v4.999l-4.331 2.5-4.331-2.5V18.246z" fill="currentColor"/></svg>
                Summarize with ChatGPT
              </button>
            </div>

            <div id="google-summary-panel" class="hidden neon-panel p-6 mt-4" style="border-color:rgba(16,163,127,0.3);box-shadow:0 0 20px rgba(16,163,127,0.08)">
              <div class="flex items-center gap-3 mb-4">
                <div class="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style="background:rgba(16,163,127,0.15)">
                  <svg width="16" height="16" viewBox="0 0 41 41" fill="none"><path d="M37.532 16.87a9.963 9.963 0 0 0-.856-8.184 10.078 10.078 0 0 0-10.855-4.835 9.964 9.964 0 0 0-6.65-2.164 10.079 10.079 0 0 0-9.612 6.977 9.967 9.967 0 0 0-6.664 4.834 10.08 10.08 0 0 0 1.24 11.817 9.965 9.965 0 0 0 .856 8.185 10.079 10.079 0 0 0 10.855 4.835 9.965 9.965 0 0 0 6.65 2.164 10.079 10.079 0 0 0 9.614-6.98 9.967 9.967 0 0 0 6.663-4.834 10.079 10.079 0 0 0-1.241-11.817zm-17.223 24.11a7.474 7.474 0 0 1-4.801-1.735c.061-.033.168-.091.237-.134l7.964-4.6a1.294 1.294 0 0 0 .655-1.134V19.054l3.366 1.944a.12.12 0 0 1 .066.092v9.299a7.505 7.505 0 0 1-7.487 7.591zM4.186 34.063a7.471 7.471 0 0 1-.894-5.023c.06.036.162.099.237.141l7.964 4.6a1.297 1.297 0 0 0 1.308 0l9.724-5.614v3.888a.12.12 0 0 1-.048.103L14.4 36.86a7.505 7.505 0 0 1-10.214-2.797zM2.408 13.866a7.471 7.471 0 0 1 3.904-3.288c0 .033-.001.065 0 .122v9.201a1.294 1.294 0 0 0 .654 1.132l9.723 5.614-3.366 1.944a.12.12 0 0 1-.114.012L4.597 23.86a7.505 7.505 0 0 1-2.189-9.994zm27.555 6.437l-9.724-5.615 3.367-1.943a.121.121 0 0 1 .114-.012l8.6 4.944a7.498 7.498 0 0 1-1.158 13.528v-9.201a1.293 1.293 0 0 0-.2-.701zm3.35-5.043c-.059-.037-.162-.099-.236-.141l-7.965-4.6a1.298 1.298 0 0 0-1.308 0l-9.723 5.614v-3.888a.12.12 0 0 1 .048-.103l8.08-4.165a7.505 7.505 0 0 1 11.104 7.283zm-21.063 6.929l-3.367-1.944a.12.12 0 0 1-.065-.092v-9.299a7.505 7.505 0 0 1 12.293-5.756 6.94 6.94 0 0 0-.236.134l-7.965 4.6a1.294 1.294 0 0 0-.654 1.132l-.006 11.225zm1.829-3.943l4.33-2.501 4.332 2.5v4.999l-4.331 2.5-4.331-2.5V18.246z" fill="#10A37F"/></svg>
                </div>
                <div>
                  <div class="font-bold text-sm" style="color:#10A37F">ChatGPT Analysis</div>
                  <div class="text-[10px] uppercase tracking-widest" style="color:#818384">AI Intelligence Summary — Google</div>
                </div>
                <div id="google-summary-spinner" class="ml-auto hidden">
                  <div class="w-5 h-5 border-2 rounded-full animate-spin" style="border-color:rgba(16,163,127,0.2);border-top-color:#10A37F"></div>
                </div>
              </div>
              <div id="google-summary-text" class="text-sm leading-relaxed" style="color:#cbd5e1;white-space:pre-wrap;font-family:inherit"></div>
            </div>
          </div>
        </section>

'''

if OLD_REDDIT_SECTION:
    html = html.replace(OLD_REDDIT_SECTION, REDDIT_CYBERPUNK)
    ok("Reddit cyberpunk + Google sections replaced")
else:
    err("Reddit section not found for replacement")

write('templates/index.html', html)
ok("index.html saved")

# =====================================================================
# 3. app.js - replace Reddit JS and add Google Dork JS
# =====================================================================
js = read('static/js/app.js')

# Remove old Reddit JS
start = js.find('// ---- Reddit Intelligence Tab')
if start != -1:
    js = js[:start].rstrip() + '\n'
    ok("Old Reddit JS removed")
else:
    err("Old Reddit JS not found")

FULL_NEW_JS = """
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
    .replace(/\\*\\*|__/g,"").replace(/\\*|_/g,"").replace(/^#{1,6}\\s/gm,"")
    .replace(/^[|].*$/gm,"").replace(/^[-=]{3,}$/gm,"")
    .replace(/\\n{3,}/g,"\\n\\n").trim();
}
function intelSpinner(color) {
  return `<div style="padding:48px;text-align:center">
    <div style="width:44px;height:44px;border:3px solid ${color}22;border-top-color:${color};border-radius:50%;animation:spin 0.7s linear infinite;margin:0 auto 14px"></div>
    <div style="color:${color};font-size:11px;text-transform:uppercase;letter-spacing:0.12em;opacity:0.8">Searching...</div>
  </div>`;
}

// ---- Reddit Intelligence Tab ----------------------------------------

let redditPosts = [];

function buildRedditCard(post) {
  const ratio    = Math.round((post.upvote_ratio||0)*100);
  const age      = timeAgo(post.created_utc);
  const comments = post.comments||[];
  const color    = "#FF4500";

  let commentsHTML = "";
  if (comments.length) {
    commentsHTML = `
      <div class="mt-3 pt-3" style="border-top:1px solid rgba(255,69,0,0.15)">
        <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.08em;color:rgba(255,69,0,0.5);margin-bottom:8px">
          <i class="fas fa-comment-alt" style="margin-right:4px"></i>Top Comments
        </div>
        ${comments.map(c => `
          <div style="display:flex;gap:8px;margin-bottom:10px;align-items:flex-start">
            <div style="width:22px;height:22px;border-radius:50%;background:#FF4500;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:800;color:white;flex-shrink:0;margin-top:1px">
              ${(c.author||"?")[0].toUpperCase()}
            </div>
            <div style="flex:1;min-width:0">
              <div style="font-size:10px;color:rgba(255,255,255,0.45);margin-bottom:3px">
                <span style="color:rgba(255,255,255,0.75);font-weight:600">u/${c.author||"?"}</span>
                &nbsp;·&nbsp;
                <i class="fas fa-arrow-up" style="color:#FF4500;font-size:9px"></i>
                <span style="color:#FF4500"> ${fmt(c.score)}</span>
              </div>
              <div style="font-size:11px;color:#8899a6;line-height:1.55">${(c.body||"").replace(/</g,"&lt;")}</div>
            </div>
          </div>`).join("")}
      </div>`;
  }

  const card = document.createElement("div");
  card.className = "relative overflow-hidden";
  card.style.cssText = `
    background:#0d1117;border:1px solid rgba(255,69,0,0.18);border-radius:12px;
    box-shadow:0 2px 20px rgba(255,69,0,0.08),inset 0 1px 0 rgba(255,69,0,0.06);
    transition:border-color 0.2s,box-shadow 0.2s;margin-bottom:0;
  `;
  card.onmouseenter = () => {
    card.style.borderColor = "rgba(255,69,0,0.45)";
    card.style.boxShadow = "0 4px 28px rgba(255,69,0,0.16),inset 0 1px 0 rgba(255,69,0,0.1)";
  };
  card.onmouseleave = () => {
    card.style.borderColor = "rgba(255,69,0,0.18)";
    card.style.boxShadow = "0 2px 20px rgba(255,69,0,0.08)";
  };

  card.innerHTML = `
    <!-- top accent line -->
    <div style="height:2px;background:linear-gradient(90deg,#FF4500,transparent);border-radius:12px 12px 0 0"></div>
    <div style="display:flex;gap:0;padding:14px 16px 12px">

      <!-- Vote column -->
      <div style="display:flex;flex-direction:column;align-items:center;gap:4px;min-width:44px;padding-top:2px">
        <button style="background:none;border:none;cursor:pointer;padding:4px 8px;border-radius:4px;transition:background 0.15s"
          onmouseenter="this.style.background='rgba(255,69,0,0.12)'" onmouseleave="this.style.background='none'">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 3L14 10H2L8 3Z" fill="#FF4500"/>
          </svg>
        </button>
        <span style="font-size:12px;font-weight:700;color:#D7DADC;line-height:1">${fmt(post.score)}</span>
        <button style="background:none;border:none;cursor:pointer;padding:4px 8px;border-radius:4px;transition:background 0.15s"
          onmouseenter="this.style.background='rgba(113,147,255,0.12)'" onmouseleave="this.style.background='none'">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 13L2 6H14L8 13Z" fill="#7193FF" opacity="0.6"/>
          </svg>
        </button>
      </div>

      <!-- Content -->
      <div style="flex:1;min-width:0;padding-left:12px">
        <!-- Meta -->
        <div style="font-size:11px;color:#818384;margin-bottom:6px;display:flex;flex-wrap:wrap;align-items:center;gap:4px">
          <span style="color:#D7DADC;font-weight:600;cursor:pointer" onmouseenter="this.style.color='#FF4500'" onmouseleave="this.style.color='#D7DADC'">${post.subreddit}</span>
          <span>·</span>
          <span>u/<span style="color:rgba(255,255,255,0.6)">${post.author||"[deleted]"}</span></span>
          <span>·</span>
          <span>${age} ago</span>
          ${post.link_flair ? `<span style="background:rgba(255,69,0,0.12);color:#FF4500;padding:1px 7px;border-radius:12px;font-size:9px;font-weight:600">${post.link_flair}</span>` : ""}
        </div>

        <!-- Title -->
        <a href="${post.url}" target="_blank" rel="noopener noreferrer"
          style="display:block;font-size:14px;font-weight:600;color:#D7DADC;text-decoration:none;line-height:1.45;margin-bottom:8px;transition:color 0.15s"
          onmouseenter="this.style.color='#FF6B35'" onmouseleave="this.style.color='#D7DADC'">
          ${post.title}
          ${post.domain && !post.is_self ? `<span style="font-size:10px;color:#818384;font-weight:400;margin-left:6px">(${post.domain})</span>` : ""}
        </a>

        <!-- Body preview -->
        ${post.selftext ? `<p style="font-size:12px;color:#8899a6;line-height:1.6;margin-bottom:10px">${post.selftext.slice(0,240).replace(/</g,"&lt;")}${post.selftext.length>240?"…":""}</p>` : ""}

        <!-- Comments -->
        ${commentsHTML}

        <!-- Action bar -->
        <div style="display:flex;align-items:center;gap:4px;margin-top:10px;flex-wrap:wrap">
          <a href="${post.url}" target="_blank" rel="noopener noreferrer" style="display:flex;align-items:center;gap:6px;padding:5px 9px;border-radius:4px;font-size:11px;font-weight:600;color:#818384;text-decoration:none;transition:background 0.15s;cursor:pointer"
            onmouseenter="this.style.background='rgba(255,69,0,0.1)';this.style.color='#FF4500'" onmouseleave="this.style.background='transparent';this.style.color='#818384'">
            <i class="fas fa-comment-alt" style="font-size:12px"></i> ${fmt(post.num_comments||0)} Comments
          </a>
          <span style="display:flex;align-items:center;gap:6px;padding:5px 9px;border-radius:4px;font-size:11px;font-weight:600;color:#818384;cursor:pointer;transition:background 0.15s"
            onmouseenter="this.style.background='rgba(255,69,0,0.1)';this.style.color='#FF4500'" onmouseleave="this.style.background='transparent';this.style.color='#818384'">
            <i class="fas fa-share" style="font-size:11px"></i> Share
          </span>
          <span style="display:flex;align-items:center;gap:6px;padding:5px 9px;border-radius:4px;font-size:11px;font-weight:600;color:#818384;cursor:pointer;transition:background 0.15s"
            onmouseenter="this.style.background='rgba(255,69,0,0.1)';this.style.color='#FF4500'" onmouseleave="this.style.background='transparent';this.style.color='#818384'">
            <i class="fas fa-bookmark" style="font-size:11px"></i> Save
          </span>
          <span style="margin-left:auto;font-size:10px;color:#818384">
            <i class="fas fa-arrow-up" style="color:#FF4500;margin-right:2px"></i>${ratio}% upvoted
          </span>
        </div>
      </div>
    </div>`;
  return card;
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
    countEl.textContent = redditPosts.length + " posts found";
    sysLog("OSINT","Found "+redditPosts.length+" Reddit posts for: "+query,"success");
    postsGrid.innerHTML = "";
    if (!redditPosts.length) {
      postsGrid.innerHTML = `<div style="padding:40px;text-align:center;color:#818384">No Reddit posts found. Try a different query.</div>`;
    } else {
      redditPosts.forEach(p => postsGrid.appendChild(buildRedditCard(p)));
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
    sysLog("OSINT","ChatGPT summary done for: "+query,"success");
  } catch(err) {
    spin.classList.add("hidden"); text.textContent="Error: "+err.message;
    sysLog("OSINT","AI error: "+err.message,"error");
  }
});

document.getElementById("reddit-query")?.addEventListener("keypress",e=>{if(e.key==="Enter")document.getElementById("reddit-search-btn")?.click();});

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
"""

js = js.rstrip() + '\n' + FULL_NEW_JS + '\n'
write('static/js/app.js', js)
ok("Full Reddit + Google Dork JS written (%d lines)" % js.count('\n'))

# =====================================================================
# Final syntax check
# =====================================================================
try:
    ast.parse(read('app.py'))
    ok("app.py syntax OK")
except SyntaxError as e:
    err("Line %d: %s" % (e.lineno, e.msg))

print("\n=== All changes applied ===")


# ============================================================
# SECTION: test_api_search.py
# ============================================================

import requests

try:
    print('Testing /api/reddit/search...')
    r = requests.post('http://localhost:8000/api/reddit/search', json={'query': 'ransomware keylogger'}, timeout=15)
    print('Status:', r.status_code)
    data = r.json()
    posts = data.get('posts', [])
    print(f'Found {len(posts)} posts.')
    for i, p in enumerate(posts[:3]):
        print(f"{i+1}. {p.get('title')} (score: {p.get('score')})")
        print(f"   Comments: {len(p.get('comments', []))}")
        print(f"   URL: {p.get('url')}")
except Exception as e:
    print('Error:', e)


# ============================================================
# SECTION: test_ddg.py
# ============================================================

import requests, re, urllib.parse

r = requests.post(
    'https://html.duckduckgo.com/html/',
    data={'q': 'VAPT Nessus report', 'b': '', 'kl': 'us-en'},
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'},
    timeout=12
)
print("Status:", r.status_code, "  Size:", len(r.text))

html = r.text

# Find result title links
titles = re.findall(r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL)
print("\n--- TITLES FOUND:", len(titles))
for url, title in titles[:3]:
    clean_title = re.sub(r'<[^>]+>', '', title).strip()
    print("  TITLE:", clean_title[:80])
    print("  URL  :", url[:100])

# Find snippets
snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
print("\n--- SNIPPETS FOUND:", len(snippets))
for s in snippets[:2]:
    clean = re.sub(r'<[^>]+>', '', s).strip()
    print("  SNIPPET:", clean[:120])

# Decode DDG redirect URL
sample_url = titles[0][0] if titles else ""
print("\nRaw URL sample:", sample_url[:200])
if '//duckduckgo.com/l/?' in sample_url or sample_url.startswith('//'):
    full = "https:" + sample_url if sample_url.startswith('//') else sample_url
    try:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(full).query)
        real = qs.get('uddg', ['?'])[0]
        print("Decoded URL:", real)
    except Exception as e:
        print("Decode error:", e)


# ============================================================
# SECTION: test_ddg2.py
# ============================================================

import requests, re
import urllib.parse as _urlparse

_DDG_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"
_DDG_HEADERS = {"User-Agent": _DDG_UA, "Accept": "text/html,application/xhtml+xml"}

def _strip_html(t): return re.sub(r"<[^>]+>","",t or "").strip()
def _decode_ddg_url(u):
    if not u: return ""
    if u.startswith("//duckduckgo.com"): u="https:"+u
    if "duckduckgo.com/l/?" in u:
        qs=_urlparse.parse_qs(_urlparse.urlparse(u).query)
        return _urlparse.unquote(qs.get("uddg",[u])[0])
    return u

r = requests.post("https://html.duckduckgo.com/html/", data={"q":"VAPT report Nessus","b":"","kl":"us-en"}, headers=_DDG_HEADERS, timeout=15)
html = r.content.decode("utf-8", errors="replace")
titles = re.findall(r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL)
snips  = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
print("HTTP %d | Results: %d" % (r.status_code, len(titles)))
for i in range(min(5,len(titles))):
    u, t = titles[i]
    print("%d. %s" % (i+1, _strip_html(t)[:70]))
    real = _decode_ddg_url(u.strip())
    print("   URL: " + real[:80])
    if i < len(snips):
        s = _strip_html(snips[i])
        try:
            print("   SNP: " + s[:80])
        except:
            print("   SNP: [encoding error]")
print("DONE - Google DDG search working!")


# ============================================================
# SECTION: test_reddit_sort.py
# ============================================================

import requests

query = 'CVE-2024 malware'
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

print("=== Reddit Native Search Testing ===")

configs = [
    ("relevance", "all"),
    ("relevance", "month"),
    ("hot", "all"),
    ("new", "all"),
    ("top", "month")
]

for sort, t in configs:
    print(f"\n--- Sort: {sort}, Time: {t} ---")
    try:
        r = requests.get('https://www.reddit.com/search.json', params={'q': query, 'sort': sort, 't': t, 'limit': 3, 'type': 'link'}, headers=headers, timeout=10)
        data = r.json()
        for child in data.get('data', {}).get('children', []):
            p = child['data']
            title = p.get('title', '')
            if len(title) > 60: title = title[:57] + '...'
            print(f"[{p.get('score')}] {title} ({p.get('subreddit_name_prefixed')} - {p.get('created_utc')})")
    except Exception as e:
        print('Error:', e)

