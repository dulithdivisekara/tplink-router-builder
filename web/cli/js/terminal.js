/**
 * TP-Link CLI Developer Showcase Engine
 * Terminal simulation, live command filtering, install snippet switcher, toast notifications, and Theme Manager.
 * Author: Dulith Divisekara (SLIIT Malabe)
 */

// Theme Management (Defaults to Dark)
function initTheme() {
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme === 'light') {
    document.documentElement.classList.remove('dark');
  } else {
    document.documentElement.classList.add('dark');
  }
}

function toggleTheme() {
  const isDark = document.documentElement.classList.toggle('dark');
  localStorage.setItem('theme', isDark ? 'dark' : 'light');
}

// Interactive Terminal Simulations
const terminalDemos = {
  status: `<span class="text-slate-500 select-none">$</span> <span class="text-tplink-cyan font-semibold">tplink-cli status</span>
<span class="text-slate-400">Connecting to 192.168.1.1 (session auto-detected)...</span>
<span class="text-emerald-400 font-bold">[OK] Authenticated successfully</span>

<span class="text-white font-bold uppercase tracking-wider">Device Status</span>
--------------------------------------------------
<span class="text-slate-400">Model:</span>            TP-Link Archer MR200 / TL-MR6400
<span class="text-slate-400">Hardware Ver:</span>     v5.3
<span class="text-slate-400">Firmware Ver:</span>     1.3.0 Build 231120 Rel.60211n
<span class="text-slate-400">WAN IP:</span>           100.92.14.88 (CGNAT)
<span class="text-slate-400">Gateway:</span>          10.64.0.1
<span class="text-slate-400">Primary DNS:</span>      1.1.1.1 (Cloudflare)
<span class="text-slate-400">Secondary DNS:</span>    8.8.8.8 (Google)
<span class="text-slate-400">Connection:</span>       Connected (4G LTE-Advanced)
<span class="text-slate-400">Carrier:</span>          Hutch Sri Lanka (PLMN 413-08)
<span class="text-slate-400">APN:</span>              hutch3g (PDP: IPv4)
<span class="text-slate-400">Uptime:</span>           18 days, 14 hours, 32 mins`,

  signal: `<span class="text-slate-500 select-none">$</span> <span class="text-tplink-cyan font-semibold">tplink-cli signal</span>
<span class="text-slate-400">Fetching live RF telemetry from cellular baseband...</span>

<span class="text-tplink-cyan font-bold">Current LTE RF Signal:</span>
  Carrier      : <span class="text-white font-semibold">Hutch Internet</span>
  Active Band  : <span class="text-emerald-400 font-semibold">Band 8 (900 MHz) (EARFCN: 3738, PCI: 0)</span>
  RSRP         : <span class="text-emerald-400 font-bold">-88 dBm</span> (Good)
  RSRQ         : <span class="text-emerald-400 font-bold">-9 dB</span> (Excellent)
  SNR          : <span class="text-emerald-400 font-bold">16.4 dB</span> (Optimal)
  RSSI         : <span class="text-slate-300">-64 dBm</span>
  Signal Level : <span class="text-emerald-400 font-bold">4 / 4 bars [████]</span>`,

  cell: `<span class="text-slate-500 select-none">$</span> <span class="text-tplink-cyan font-semibold">tplink-cli cell-lock --earfcn 3738 --pci 0</span>
<span class="text-slate-400">Targeting Carrier Cell Lock...</span>
[1/3] Disconnecting current cellular session... <span class="text-emerald-400 font-bold">OK</span>
[2/3] Writing AT+COPS / cell selection lock for EARFCN 3738, PCI 0... <span class="text-emerald-400 font-bold">OK</span>
[3/3] Re-attaching to Hutch eNodeB PCI 0... <span class="text-emerald-400 font-bold">OK</span>

<span class="text-emerald-400 font-bold">[SUCCESS] Modem successfully locked to cell EARFCN 3738, PCI 0!</span>
SINR stabilized at 16.4 dB. Frequency drift eliminated.`,

  band: `<span class="text-slate-500 select-none">$</span> <span class="text-tplink-cyan font-semibold">tplink-cli band 3</span>
<span class="text-slate-400">Locking hardware modem to band '3'...</span>
<span class="text-emerald-400 font-bold">✓ LTE band successfully configured to '3'.</span>
Cellular modem is retuning RF hardware. Signal LEDs will cycle.

<span class="text-slate-500 select-none">$</span> <span class="text-tplink-cyan font-semibold">tplink-cli band</span>
<span class="text-white font-bold uppercase tracking-wider">Active LTE Band Configuration</span>
-------------------------------------------------------
Current Active Band : <span class="text-emerald-400 font-bold">Band 3 (1800 MHz)</span>
Channel (EARFCN)    : 1600 (PCI: 214)
Supported in LK     : Band 3 (1800 MHz), Band 8 (900 MHz), Band 40 (2300 MHz)`,

  optimize: `<span class="text-slate-500 select-none">$</span> <span class="text-tplink-cyan font-semibold">tplink-cli optimize-network --apply</span>
<span class="text-slate-400">Executing Cellular Tuning Manifesto...</span>

<span class="text-emerald-400">[✓]</span> Setting sysctl net.ipv4.tcp_congestion_control = bbr
<span class="text-emerald-400">[✓]</span> Setting sysctl net.core.default_qdisc = fq
<span class="text-emerald-400">[✓]</span> Clamping MTU on wlan0 to 1420 (GTP Header Overhead)
<span class="text-emerald-400">[✓]</span> Setting TCP MSS clamping to 1380 bytes
<span class="text-emerald-400">[✓]</span> Setting nameserver 1.1.1.1 and 1.0.0.1 in resolv.conf
<span class="text-emerald-400">[✓]</span> Starting 25s keepalive pulse daemon (PID 84192)

<span class="text-white font-bold">All optimizations activated!</span>
Loaded latency dropped from 184ms -> 28ms. Zero packet stalls.`,

  repl: `<span class="text-slate-500 select-none">$</span> <span class="text-tplink-cyan font-semibold">tplink-cli repl</span>
TP-Link Router Interactive Console v1.0.0 (Archer MR200)
Type 'help' for commands, 'exit' to quit.

<span class="text-tplink-cyan font-bold">tplink (192.168.1.1)&gt;</span> signal
RSRP: -88 dBm | SNR: 16.4 dB | Band: B8 (900MHz) | Bars: 4/4

<span class="text-tplink-cyan font-bold">tplink (192.168.1.1)&gt;</span> sms list --limit 2
[1] From: "HUTCH" [2026-10-29 12:45]: "Your 90-Day Unlimited 20Mbps Plan is ACTIVE."
[2] From: "Google" [2026-10-29 11:20]: "G-849201 is your verification code."

<span class="text-tplink-cyan font-bold">tplink (192.168.1.1)&gt;</span> clients
Dulith-MacBook-Pro  | 192.168.1.102 | 7c:10:c9:82:11:02 | 5GHz (-42 dBm)
iPhone-15-Pro       | 192.168.1.108 | 9a:44:01:bb:ee:fa | 5GHz (-56 dBm)`
};

function runCommand(key) {
  const screen = document.getElementById('terminal-screen');
  if (screen && terminalDemos[key]) {
    screen.innerHTML = terminalDemos[key];
  }
  document.querySelectorAll('.cmd-tab').forEach(b => {
    b.className = 'cmd-tab shrink-0 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-black/5 dark:bg-white/5 text-slate-700 dark:text-slate-300 hover:bg-black/10 dark:hover:bg-white/10 border border-black/5 dark:border-white/5 transition-colors';
  });
  const activeBtn = document.getElementById('tab-' + key);
  if (activeBtn) {
    activeBtn.className = 'cmd-tab shrink-0 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-tplink-teal/20 text-tplink-teal dark:text-tplink-cyan border border-tplink-teal/40 transition-colors';
  }
}

// Installation Snippets
const installSnippets = {
  curl: 'curl -fsSL https://tp-link-cli.dulith.me/install.sh | bash',
  apt: `# Add official APT repository & install:\ncurl -fsSL https://tp-link-cli.dulith.me/apt/KEY.gpg | sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/tplink.gpg\necho "deb [signed-by=/etc/apt/trusted.gpg.d/tplink.gpg] https://tp-link-cli.dulith.me/apt stable main" | sudo tee /etc/apt/sources.list.d/tplink.list\nsudo apt update && sudo apt install tplink-cli\n\n# Or install .deb directly:\ncurl -fsSLO https://tp-link-cli.dulith.me/tplink-cli_1.0.0_all.deb\nsudo dpkg -i tplink-cli_1.0.0_all.deb`,
  npm: 'npm install -g @dulith/tplink-cli\n# or run instantly without install:\nnpx @dulith/tplink-cli status',
  pip: 'pip install tplink-cli\n# or in isolated venv:\npipx install tplink-cli',
  brew: 'brew tap dulithdivisekara/tap\nbrew install tplink-cli',
  docker: 'docker run --rm -it ghcr.io/dulithdivisekara/tplink-cli:latest status',
  go: 'go install github.com/dulithdivisekara/tplink-cli/cmd/tplink-cli@latest'
};

function setInstallTab(pkg) {
  const el = document.getElementById('install-snippet');
  if (el && installSnippets[pkg]) {
    el.textContent = installSnippets[pkg];
  }
  document.querySelectorAll('.inst-tab').forEach(b => {
    b.className = 'inst-tab shrink-0 px-3 py-1.5 rounded-lg text-xs font-mono font-medium text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white transition-colors';
  });
  const active = document.getElementById('btn-' + pkg);
  if (active) {
    active.className = 'inst-tab shrink-0 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-tplink-teal/20 text-tplink-teal dark:text-tplink-cyan border border-tplink-teal/40 transition-colors';
  }
}

// Toast Notifications
function showToast(msg) {
  const existing = document.getElementById('toast-notification');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.id = 'toast-notification';
  toast.className = 'fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-900 text-white text-xs font-mono shadow-2xl border border-white/10 transition-all duration-300 transform translate-y-0 opacity-100';
  toast.innerHTML = `<svg class="w-4 h-4 text-emerald-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg><span>${msg}</span>`;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translate-y-2';
    setTimeout(() => toast.remove(), 300);
  }, 2500);
}

function copyHeroCmd() {
  const text = document.getElementById('hero-cmd').textContent;
  navigator.clipboard.writeText(text);
  const btn = document.getElementById('hero-copy-btn');
  btn.innerHTML = `<svg class="w-4 h-4 text-emerald-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg><span class="text-emerald-500">Copied!</span>`;
  showToast('Copied installation command to clipboard');
  setTimeout(() => {
    btn.innerHTML = `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg><span>Copy</span>`;
  }, 2000);
}

function copyInstallSnippet() {
  const text = document.getElementById('install-snippet').textContent;
  navigator.clipboard.writeText(text);
  const btn = document.getElementById('install-copy-btn');
  if (btn) {
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
  }
  showToast('Copied package snippet to clipboard');
}

// Category and Search Filtering
let currentCategory = 'all';

function setCommandCategory(cat) {
  currentCategory = cat;
  document.querySelectorAll('.cat-tab').forEach(btn => {
    if (btn.dataset.cat === cat) {
      btn.className = 'cat-tab shrink-0 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-tplink-teal/20 text-tplink-teal dark:text-tplink-cyan border border-tplink-teal/40 transition-colors';
    } else {
      btn.className = 'cat-tab shrink-0 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-black/5 dark:bg-white/5 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white border border-black/5 dark:border-white/5 transition-colors';
    }
  });
  filterCommands();
}

function filterCommands() {
  const q = (document.getElementById('cmd-search')?.value || '').toLowerCase().trim();
  document.querySelectorAll('.cmd-card').forEach(card => {
    const text = card.textContent.toLowerCase();
    const cat = card.dataset.cat || '';
    const matchesQuery = !q || text.includes(q);
    const matchesCat = currentCategory === 'all' || cat === currentCategory;
    card.style.display = (matchesQuery && matchesCat) ? 'block' : 'none';
  });
}

// Default init
initTheme();
window.addEventListener('DOMContentLoaded', () => {
  runCommand('status');
});
