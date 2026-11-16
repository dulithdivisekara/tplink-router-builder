/**
 * TP-Link MCP Showcase Application Engine
 * Script-driven UI for real-time tool filtering, schema inspection, theme switching, and agent config export.
 * Author: Dulith Divisekara (SLIIT Malabe)
 */

let allTools = [];
let currentCategory = 'all';

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

// Toast notification
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

// Load tools data dynamically
async function initApp() {
  try {
    const res = await fetch('data/tools.json');
    if (res.ok) {
      allTools = await res.json();
    }
  } catch (err) {
    console.warn('Local data fetch failed, using pre-rendered fallback:', err);
  }
}

// Category filter
function setCategory(cat) {
  currentCategory = cat;
  document.querySelectorAll('.cat-pill').forEach(btn => {
    if (btn.dataset.cat === cat) {
      btn.className = 'cat-pill shrink-0 px-3 py-1.5 rounded-full text-xs font-mono font-medium bg-tplink-teal/20 text-tplink-teal dark:text-tplink-cyan border border-tplink-teal/40 transition-colors';
    } else {
      btn.className = 'cat-pill shrink-0 px-3 py-1.5 rounded-full text-xs font-mono font-medium bg-black/5 dark:bg-white/5 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white border border-black/5 dark:border-white/5 transition-colors';
    }
  });
  filterTools();
}

// Filter tools based on query & category
function filterTools() {
  const query = (document.getElementById('tool-search')?.value || '').toLowerCase().trim();
  const cards = document.querySelectorAll('.tool-card');

  cards.forEach(card => {
    const name = (card.dataset.name || '').toLowerCase();
    const cat = card.dataset.cat || '';
    const text = card.textContent.toLowerCase();

    const matchesQuery = !query || name.includes(query) || text.includes(query);
    const matchesCat = currentCategory === 'all' || cat === currentCategory;

    card.style.display = (matchesQuery && matchesCat) ? 'block' : 'none';
  });
}

// Tool Schema Modal
function openToolModal(toolName) {
  const tool = allTools.find(t => t.name === toolName);
  const modal = document.getElementById('tool-modal');
  if (!modal) return;

  const title = document.getElementById('modal-title');
  const badge = document.getElementById('modal-category');
  const desc = document.getElementById('modal-desc');
  const paramsList = document.getElementById('modal-params');
  const promptBox = document.getElementById('modal-prompt');

  if (tool) {
    title.textContent = tool.name;
    badge.textContent = tool.category;
    desc.textContent = tool.description;
    
    // Fallback prompt generation if example_prompt is absent
    const fallbackPrompt = tool.example_prompt || generatePromptForTool(tool);
    promptBox.textContent = `"${fallbackPrompt}"`;

    paramsList.innerHTML = '';
    if (!tool.parameters || tool.parameters.length === 0) {
      paramsList.innerHTML = '<div class="text-xs text-slate-500 dark:text-slate-400 italic py-2">Zero-parameter tool. No arguments required.</div>';
    } else {
      tool.parameters.forEach(p => {
        const pDiv = document.createElement('div');
        pDiv.className = 'p-3 rounded-lg bg-black/5 dark:bg-black/40 border border-black/5 dark:border-white/5 text-xs';
        pDiv.innerHTML = `
          <div class="flex items-center justify-between mb-1 gap-2">
            <div class="flex items-center gap-2">
              <span class="font-mono text-tplink-teal dark:text-tplink-cyan font-bold">${p.name}</span>
              <span class="px-1.5 py-0.5 rounded bg-black/10 dark:bg-white/10 text-[10px] font-mono text-slate-600 dark:text-slate-400">${p.type}</span>
            </div>
            <span class="text-[10px] font-mono font-medium ${p.required ? 'text-amber-500 dark:text-amber-400' : 'text-slate-500'}">${p.required ? 'Required' : 'Optional'}</span>
          </div>
          <p class="text-slate-600 dark:text-slate-300 text-[11px] leading-relaxed">${p.description || p.name}</p>
          ${p.default !== null && p.default !== undefined ? `<div class="text-[10px] font-mono text-slate-500 mt-1">Default: <code>${JSON.stringify(p.default)}</code></div>` : ''}
        `;
        paramsList.appendChild(pDiv);
      });
    }
  } else {
    // Fallback if not loaded
    title.textContent = toolName;
    badge.textContent = 'Router Tool';
    desc.textContent = 'Exposes direct JSON-RPC and AT command interaction with the TP-Link baseband.';
    promptBox.textContent = `"Run ${toolName} on the router and report telemetry."`;
    paramsList.innerHTML = '<div class="text-xs text-slate-500 italic py-2">Schema loaded from pre-rendered bundle.</div>';
  }

  modal.classList.remove('hidden');
  modal.classList.add('flex');
}

function generatePromptForTool(t) {
  const name = t.name;
  if (name.includes('signal')) return 'Check my TP-Link router cellular RF signal and report RSRP, RSRQ, and SINR.';
  if (name.includes('status')) return 'Get the complete router status, uptime, WAN IP, and active carrier.';
  if (name.includes('cell_lock')) return 'Lock the LTE modem to EARFCN 3738 and PCI 0 to stabilize connection.';
  if (name.includes('band')) return 'Switch the router modem to LTE Band 3 (1800 MHz) for higher download speed.';
  if (name.includes('sms')) return 'Check unread SMS messages for any carrier OTP or verification tokens.';
  if (name.includes('clients')) return 'List all connected devices and their Wi-Fi signal strengths.';
  if (name.includes('calibrate')) return 'Run an autonomous RF calibration sweep to find the best LTE band.';
  if (name.includes('reboot')) return 'Reboot the router and verify reconnection.';
  return `Use ${name} on the router and return structured JSON results.`;
}

function closeToolModal() {
  const modal = document.getElementById('tool-modal');
  if (modal) {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }
}

// Client configuration tabs
const clientConfigs = {
  claude: `{
  "mcpServers": {
    "tplink-router": {
      "command": "npx",
      "args": ["-y", "@dulith/tplink-mcp"],
      "env": {
        "TPLINK_ROUTER_IP": "192.168.1.1",
        "TPLINK_PASSWORD": "your_router_password"
      }
    }
  }
}`,

  antigravity: `{
  "mcpServers": {
    "tplink-mcp": {
      "command": "python3",
      "args": ["-m", "tplink_mcp.server"],
      "env": {
        "TPLINK_ROUTER_IP": "192.168.1.1",
        "TPLINK_PASSWORD": "your_router_password"
      }
    }
  }
}`,

  cursor: `{
  "mcpServers": {
    "tplink": {
      "command": "npx",
      "args": ["-y", "@dulith/tplink-mcp"],
      "env": {
        "TPLINK_ROUTER_IP": "192.168.1.1",
        "TPLINK_PASSWORD": "your_router_password"
      }
    }
  }
}`,

  docker: `docker run -d --name tplink-mcp \\
  -e TPLINK_ROUTER_IP=192.168.1.1 \\
  -e TPLINK_PASSWORD=your_router_password \\
  ghcr.io/dulithdivisekara/tplink-mcp:latest`
};

function setConfigTab(client) {
  const el = document.getElementById('config-snippet');
  if (el && clientConfigs[client]) {
    el.textContent = clientConfigs[client];
  }
  document.querySelectorAll('.cfg-tab').forEach(b => {
    b.className = 'cfg-tab shrink-0 px-3 py-1.5 rounded-lg text-xs font-mono font-medium text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white transition-colors';
  });
  const active = document.getElementById('tab-' + client);
  if (active) {
    active.className = 'cfg-tab shrink-0 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-tplink-teal/20 text-tplink-teal dark:text-tplink-cyan border border-tplink-teal/40 transition-colors';
  }
}

function copyHeroCmd() {
  const text = document.getElementById('hero-cmd').textContent;
  navigator.clipboard.writeText(text);
  const btn = document.getElementById('hero-copy-btn');
  btn.innerHTML = `<svg class="w-4 h-4 text-emerald-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg><span class="text-emerald-500">Copied!</span>`;
  showToast('Copied npx start command to clipboard');
  setTimeout(() => {
    btn.innerHTML = `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg><span>Copy</span>`;
  }, 2000);
}

function copyConfigSnippet() {
  const text = document.getElementById('config-snippet').textContent;
  navigator.clipboard.writeText(text);
  const btn = document.getElementById('config-copy-btn');
  if (btn) {
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
  }
  showToast('Copied client config to clipboard');
}

// Close modal on escape key or backdrop click
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeToolModal();
});

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initApp();
  const modal = document.getElementById('tool-modal');
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeToolModal();
    });
  }
});
