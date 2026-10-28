"""Real-Time Live Web Dashboard Server for TP-Link Router Cellular Calibration.

Serves an Apple/Tailwind glassmorphic real-time dashboard on http://localhost:8765
with live Server-Sent Events (SSE), RF gauges, latency/jitter oscilloscope,
and autonomous control endpoints.

Author: Dulith Divisekara (SLIIT Malabe)
"""

import json
import logging
import os
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_STATE_FILE = Path("/tmp/tplink_calibration_state.json")
GLOBAL_CALIBRATOR = None


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TP-Link Autonomous RF Calibration Lab | Dulith Divisekara</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            obsidian: '#070b12',
            surface: {
              DEFAULT: '#0d1522',
              card: '#111b2b',
              muted: '#172338',
              border: 'rgba(56, 189, 248, 0.14)'
            },
            signal: {
              cyan: '#00e5ff',
              emerald: '#10b981',
              amber: '#f59e0b',
              rose: '#f43f5e',
              sky: '#38bdf8'
            }
          },
          fontFamily: {
            sans: ['"Plus Jakarta Sans"', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace']
          }
        }
      }
    }
  </script>
  <style>
    body {
      font-family: 'Plus Jakarta Sans', ui-sans-serif, system-ui, -apple-system, sans-serif;
      background-color: #070b12;
      color: #f1f5f9;
      background-image: 
        radial-gradient(circle at 50% 0%, rgba(14, 165, 233, 0.08) 0%, transparent 60%),
        radial-gradient(circle at 100% 100%, rgba(16, 185, 129, 0.04) 0%, transparent 50%);
    }
    .tabular-nums {
      font-variant-numeric: tabular-nums;
    }
    .panel {
      background: #0d1522;
      border: 1px solid rgba(56, 189, 248, 0.12);
      box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.5), inset 0 1px 0 0 rgba(255, 255, 255, 0.05);
    }
    .panel-accent {
      background: linear-gradient(135deg, rgba(14, 165, 233, 0.08) 0%, #0d1522 100%);
      border: 1px solid rgba(56, 189, 248, 0.22);
    }
    .pulse-ring {
      animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: .35; transform: scale(1.15); }
    }
    /* Custom subtle scrollbar */
    ::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }
    ::-webkit-scrollbar-track {
      background: rgba(0, 0, 0, 0.2);
    }
    ::-webkit-scrollbar-thumb {
      background: rgba(56, 189, 248, 0.2);
      border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: rgba(56, 189, 248, 0.4);
    }
  </style>
</head>
<body class="min-h-screen flex flex-col selection:bg-cyan-500 selection:text-black">

  <!-- Top Navigation & Instrument Header -->
  <header class="panel sticky top-0 z-50 px-6 py-3.5 border-b border-surface-border/60 backdrop-blur-md bg-opacity-90 flex items-center justify-between">
    <div class="flex items-center space-x-3.5">
      <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-600 via-sky-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 font-bold text-black text-sm tracking-tighter">
        <svg class="w-5 h-5 text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.14 0M1.393 9.393c5.857-5.857 15.355-5.857 21.213 0" />
        </svg>
      </div>
      <div>
        <div class="flex items-center space-x-2">
          <h1 class="text-sm font-semibold tracking-tight text-white">TP-Link Autonomous RF Calibration Lab</h1>
          <span class="px-2 py-0.5 text-[10px] font-mono font-medium rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/25">AGY Autonomous Engine</span>
        </div>
        <p class="text-[11px] text-slate-400">Malabe, Sri Lanka (SLIIT Zone) • Hutch 20Mbps LTE • Archer MR200</p>
      </div>
    </div>

    <!-- Live Controls & Status Badges -->
    <div class="flex items-center space-x-2.5">
      <div id="status-pill" class="flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/25">
        <span class="w-2 h-2 rounded-full bg-emerald-400 pulse-ring"></span>
        <span id="status-text">CONNECTING</span>
      </div>

      <button onclick="revertAuto()" title="Rollback carrier lock to dynamic multi-band roaming" class="px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/25 transition-all flex items-center space-x-1.5 active:scale-95">
        <span>⟳ Emergency Auto</span>
      </button>

      <button id="btn-calibrate" onclick="startCalibration()" class="px-4 py-1.5 rounded-lg text-xs font-semibold bg-gradient-to-r from-cyan-500 to-sky-500 hover:from-cyan-400 hover:to-sky-400 text-black shadow-md shadow-cyan-500/20 transition-all active:scale-95 flex items-center space-x-1.5">
        <span>▶ Start Calibration</span>
      </button>
    </div>
  </header>

  <!-- Main Telemetry Workspace -->
  <main class="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">

    <!-- Primary Telemetry Cluster: Instrument Deck -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      
      <!-- Carrier Band Card -->
      <div class="panel rounded-xl p-4 relative overflow-hidden flex flex-col justify-between">
        <div class="flex items-center justify-between text-xs text-slate-400">
          <span>Active Carrier</span>
          <span class="text-[10px] font-mono text-cyan-400">LTE RF</span>
        </div>
        <div class="my-2">
          <div class="flex items-baseline space-x-2">
            <span id="active-band" class="text-3xl font-extrabold text-white font-mono tracking-tight">--</span>
            <span id="active-freq" class="text-xs text-cyan-300 font-mono">Scanning...</span>
          </div>
          <div id="active-rain-tag" class="mt-1 text-[11px] text-slate-400">Analyzing RF link</div>
        </div>
        <div class="w-full bg-slate-800/80 rounded-full h-1 mt-1 overflow-hidden">
          <div class="bg-cyan-400 h-1 rounded-full w-full"></div>
        </div>
      </div>

      <!-- Latency & WAN Target -->
      <div class="panel rounded-xl p-4 relative overflow-hidden flex flex-col justify-between">
        <div class="flex items-center justify-between text-xs text-slate-400">
          <span>WAN Latency</span>
          <span class="text-[10px] font-mono text-slate-500">1.1.1.1</span>
        </div>
        <div class="my-2">
          <div class="flex items-baseline space-x-1.5">
            <span id="metric-latency" class="text-3xl font-extrabold text-white font-mono tabular-nums">0.0</span>
            <span class="text-xs text-slate-400 font-mono">ms</span>
          </div>
          <div id="metric-jitter" class="mt-1 text-[11px] text-amber-400 font-mono tabular-nums">Jitter: 0.0 ms</div>
        </div>
        <div class="w-full bg-slate-800/80 rounded-full h-1 mt-1 overflow-hidden">
          <div class="bg-sky-400 h-1 rounded-full w-2/3"></div>
        </div>
      </div>

      <!-- Packet Loss & Rain Attenuation Alert -->
      <div class="panel rounded-xl p-4 relative overflow-hidden flex flex-col justify-between">
        <div class="flex items-center justify-between text-xs text-slate-400">
          <span>Packet Loss</span>
          <span class="text-[10px] font-mono text-slate-500">ICMP 20pkts</span>
        </div>
        <div class="my-2">
          <div class="flex items-baseline space-x-1">
            <span id="metric-loss" class="text-3xl font-extrabold text-emerald-400 font-mono tabular-nums">0.0%</span>
          </div>
          <div id="metric-weather-alert" class="mt-1 text-[11px] text-slate-400">Rain Attenuation: Normal</div>
        </div>
        <div class="w-full bg-slate-800/80 rounded-full h-1 mt-1 overflow-hidden">
          <div class="bg-emerald-400 h-1 rounded-full w-full"></div>
        </div>
      </div>

      <!-- Watchdog Fail-Safe Status -->
      <div class="panel rounded-xl p-4 relative overflow-hidden flex flex-col justify-between">
        <div class="flex items-center justify-between text-xs text-slate-400">
          <span>Watchdog Guard</span>
          <span class="text-[10px] font-mono text-indigo-400">45s Guard</span>
        </div>
        <div class="my-2">
          <div class="flex items-baseline space-x-1.5">
            <span id="watchdog-val" class="text-3xl font-extrabold text-indigo-300 font-mono">ARMED</span>
          </div>
          <div class="mt-1 text-[11px] text-slate-400">Auto-reverts to AUTO on WAN drop</div>
        </div>
        <div class="w-full bg-slate-800/80 rounded-full h-1 mt-1 overflow-hidden">
          <div class="bg-indigo-400 h-1 rounded-full w-full"></div>
        </div>
      </div>

    </div>

    <!-- RF Signal Power Gauges & Real-Time Pulse Oscilloscope -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

      <!-- Signal Instrumentation Panel -->
      <div class="panel rounded-xl p-5 flex flex-col justify-between space-y-4">
        <div>
          <div class="flex items-center justify-between">
            <h2 class="text-xs font-semibold text-slate-200">Radio Frequency Signal Metrics</h2>
            <span class="text-[10px] font-mono text-slate-500">Archer MR200</span>
          </div>
          <p class="text-[11px] text-slate-400 mt-0.5">Cellular signal power, link quality, and signal-to-noise ratio</p>
        </div>

        <div class="grid grid-cols-3 gap-2.5 text-center">
          <!-- RSRP Gauge -->
          <div class="p-3 rounded-lg bg-surface-muted/60 border border-white/5">
            <div class="text-[10px] text-slate-400 font-mono">RSRP</div>
            <div id="gauge-rsrp" class="text-lg font-bold font-mono text-cyan-300 mt-1 tabular-nums">-85 dBm</div>
            <div class="text-[9px] text-slate-500 mt-0.5">Target: &gt;-90</div>
          </div>
          <!-- RSRQ Gauge -->
          <div class="p-3 rounded-lg bg-surface-muted/60 border border-white/5">
            <div class="text-[10px] text-slate-400 font-mono">RSRQ</div>
            <div id="gauge-rsrq" class="text-lg font-bold font-mono text-sky-300 mt-1 tabular-nums">-10 dB</div>
            <div class="text-[9px] text-slate-500 mt-0.5">Target: &gt;-12</div>
          </div>
          <!-- SINR Gauge -->
          <div class="p-3 rounded-lg bg-surface-muted/60 border border-white/5">
            <div class="text-[10px] text-slate-400 font-mono">SINR</div>
            <div id="gauge-sinr" class="text-lg font-bold font-mono text-emerald-400 mt-1 tabular-nums">18 dB</div>
            <div class="text-[9px] text-slate-500 mt-0.5">Target: &gt;13</div>
          </div>
        </div>

        <div class="text-[11px] text-slate-400 space-y-2 pt-2 border-t border-white/5">
          <div class="flex justify-between items-center">
            <span>Path MTU Clamping</span>
            <span class="font-mono text-cyan-300 bg-cyan-950/40 px-1.5 py-0.5 rounded border border-cyan-500/20 text-[10px]">1420 Bytes (GTP)</span>
          </div>
          <div class="flex justify-between items-center">
            <span>TCP Congestion Control</span>
            <span class="font-mono text-emerald-400 text-[10px]">BBR active</span>
          </div>
          <div class="flex justify-between items-center">
            <span>DNS Overrides</span>
            <span class="font-mono text-slate-300 text-[10px]">1.1.1.1, 8.8.8.8</span>
          </div>
        </div>
      </div>

      <!-- Real-Time Latency & Jitter Pulse Oscilloscope -->
      <div class="lg:col-span-2 panel rounded-xl p-5 flex flex-col justify-between space-y-3">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-xs font-semibold text-slate-200">Live Latency & Jitter Pulse Oscilloscope</h2>
            <p class="text-[11px] text-slate-400 mt-0.5">Real-time round-trip latency stream (ping to Cloudflare 1.1.1.1)</p>
          </div>
          <div class="flex items-center space-x-3 text-[11px]">
            <span class="flex items-center space-x-1.5"><span class="w-2 h-2 rounded-full bg-cyan-400"></span><span class="text-slate-300 font-mono">Latency</span></span>
            <span class="flex items-center space-x-1.5"><span class="w-2 h-2 rounded-full bg-amber-400"></span><span class="text-slate-300 font-mono">Jitter</span></span>
            <span id="canvas-rate" class="font-mono text-slate-500 text-[10px]">1s Pulse</span>
          </div>
        </div>

        <div class="h-48 w-full bg-obsidian rounded-lg relative overflow-hidden border border-white/5">
          <canvas id="osc-canvas" class="w-full h-full block"></canvas>
        </div>
      </div>

    </div>

    <!-- Multi-Band Comparison Scorecard & Rain Attenuation Matrix -->
    <div class="panel rounded-xl p-5 space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 class="text-sm font-semibold text-white">Cellular Band Performance & Rain Attenuation Matrix</h2>
          <p class="text-xs text-slate-400 mt-0.5">Comparative benchmark across Sri Lankan carrier frequencies (Band 8 900MHz, Band 3 1800MHz, Band 1, Band 40, Auto)</p>
        </div>
        <a href="/api/report" download="calibration-report.md" target="_blank" class="self-start sm:self-auto px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-muted hover:bg-surface-border/40 text-slate-200 border border-white/10 transition flex items-center space-x-1.5">
          <svg class="w-3.5 h-3.5 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span>Export Markdown Report</span>
        </a>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="text-[11px] text-slate-400 border-b border-white/10 font-mono">
            <tr>
              <th class="py-2.5 px-3.5 font-medium">Carrier Band</th>
              <th class="py-2.5 px-3.5 font-medium">Frequency</th>
              <th class="py-2.5 px-3.5 font-medium">Packet Loss</th>
              <th class="py-2.5 px-3.5 font-medium">Latency (avg)</th>
              <th class="py-2.5 px-3.5 font-medium">Jitter</th>
              <th class="py-2.5 px-3.5 font-medium">SINR</th>
              <th class="py-2.5 px-3.5 font-medium">Rain Resilience</th>
              <th class="py-2.5 px-3.5 font-medium text-right">Action</th>
            </tr>
          </thead>
          <tbody id="matrix-tbody" class="divide-y divide-white/5 font-mono">
            <tr>
              <td colspan="8" class="py-8 text-center text-slate-500 font-sans text-xs">
                No bands evaluated yet. Click <span class="font-medium text-cyan-400">Start Calibration</span> above to initiate autonomous sweep.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- AGY Autonomous Recommendation Intelligence Card -->
    <div id="agy-card" class="hidden panel-accent rounded-xl p-5 border border-cyan-500/30 space-y-3">
      <div class="flex items-center space-x-2 text-cyan-400">
        <svg class="w-5 h-5 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        <h3 class="text-xs font-semibold uppercase tracking-wider text-white font-mono">Google Antigravity (AGY) Autonomous Recommendation</h3>
      </div>
      <div id="agy-summary" class="text-xs text-slate-200 leading-relaxed font-sans">
        Evaluating telemetry and rain attenuation metrics...
      </div>
      <div id="agy-actions" class="flex items-center space-x-3 pt-1">
        <!-- Injected button -->
      </div>
    </div>

    <!-- Live Execution Telemetry Stream -->
    <div class="panel rounded-xl p-5 space-y-2.5">
      <div class="flex items-center justify-between">
        <h2 class="text-xs font-semibold text-slate-300">Live Telemetry & Engine Execution Log</h2>
        <span id="log-count" class="text-[10px] text-slate-500 font-mono">0 events</span>
      </div>
      <div id="log-box" class="h-36 overflow-y-auto rounded-lg bg-black/60 p-3.5 font-mono text-[11px] text-slate-300 space-y-1 border border-white/5">
        <div>[00:00:00] [INFO] Dashboard initialized. Awaiting calibration trigger.</div>
      </div>
    </div>

  </main>

  <!-- Technical Footer -->
  <footer class="mt-auto px-6 py-4 border-t border-white/5 text-center text-[11px] text-slate-500 flex flex-col sm:flex-row items-center justify-between max-w-7xl w-full mx-auto">
    <span>TP-Link Universal Agentic Ecosystem • Archer MR200 LTE Suite</span>
    <span>Created by <a href="https://dulith.me" target="_blank" class="text-cyan-400 hover:underline font-medium">Dulith Divisekara</a> (SLIIT Malabe) • Powered by Google Antigravity SDK</span>
  </footer>

  <script>
    const canvas = document.getElementById('osc-canvas');
    const ctx = canvas.getContext('2d');
    let pingHistory = [];

    function resizeCanvas() {
      if (!canvas.parentElement) return;
      canvas.width = canvas.parentElement.clientWidth;
      canvas.height = canvas.parentElement.clientHeight;
      drawOscilloscope();
    }
    window.addEventListener('resize', resizeCanvas);
    setTimeout(resizeCanvas, 50);

    function drawOscilloscope() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const w = canvas.width;
      const h = canvas.height;

      // Draw subtle oscilloscope grid lines
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.06)';
      ctx.lineWidth = 1;
      for (let y = 20; y < h; y += 28) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }
      for (let x = 20; x < w; x += 40) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }

      // If no history yet, draw an active resting baseline wave
      if (pingHistory.length < 2) {
        ctx.beginPath();
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.25)';
        ctx.lineWidth = 1.5;
        const midY = h / 2;
        ctx.moveTo(0, midY);
        for (let x = 0; x < w; x += 10) {
          ctx.lineTo(x, midY + Math.sin(x * 0.05) * 4);
        }
        ctx.stroke();
        return;
      }

      const step = w / Math.max(20, pingHistory.length - 1);

      // Gradient area fill under Latency curve
      const grad = ctx.createLinearGradient(0, 0, 0, h);
      grad.addColorStop(0, 'rgba(0, 229, 255, 0.25)');
      grad.addColorStop(1, 'rgba(0, 229, 255, 0.0)');

      ctx.beginPath();
      pingHistory.forEach((p, idx) => {
        const x = idx * step;
        const normalized = Math.min(h - 10, Math.max(10, h - (p.latency_ms / 150) * (h - 20)));
        if (idx === 0) ctx.moveTo(x, normalized);
        else ctx.lineTo(x, normalized);
      });
      ctx.lineTo((pingHistory.length - 1) * step, h);
      ctx.lineTo(0, h);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();

      // Latency line (Cyan)
      ctx.beginPath();
      ctx.strokeStyle = '#00e5ff';
      ctx.lineWidth = 2;
      pingHistory.forEach((p, idx) => {
        const x = idx * step;
        const normalized = Math.min(h - 10, Math.max(10, h - (p.latency_ms / 150) * (h - 20)));
        if (idx === 0) ctx.moveTo(x, normalized);
        else ctx.lineTo(x, normalized);
      });
      ctx.stroke();

      // Jitter line (Amber)
      ctx.beginPath();
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 1.5;
      pingHistory.forEach((p, idx) => {
        const x = idx * step;
        const normalized = Math.min(h - 10, Math.max(10, h - (p.jitter_ms / 60) * (h - 20)));
        if (idx === 0) ctx.moveTo(x, normalized);
        else ctx.lineTo(x, normalized);
      });
      ctx.stroke();
    }

    function updateUI(state) {
      if (!state) return;

      // Status Indicator
      const statusPill = document.getElementById('status-pill');
      const statusText = document.getElementById('status-text');
      statusText.innerText = state.status + (state.current_phase ? ' (' + state.current_phase + ')' : '');

      if (state.status === 'RUNNING') {
        statusPill.className = "flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-cyan-500/10 text-cyan-300 border border-cyan-500/30";
      } else if (state.status === 'COMPLETED') {
        statusPill.className = "flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/30";
      } else {
        statusPill.className = "flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-slate-800 text-slate-300 border border-white/10";
      }

      // Active Telemetry Metrics
      const active = state.active_metrics || {};
      document.getElementById('active-band').innerText = (state.current_band || 'AUTO').toUpperCase();
      document.getElementById('active-freq').innerText = state.current_band === '8' ? '900 MHz FDD' : state.current_band === '3' ? '1800 MHz FDD' : state.current_band === '1' ? '2100 MHz FDD' : state.current_band === '40' ? '2300 MHz TDD' : 'Dynamic Roaming';
      document.getElementById('metric-latency').innerText = (active.latency_ms || 0.0).toFixed(1);
      document.getElementById('metric-jitter').innerText = 'Jitter: ' + (active.jitter_ms || 0.0).toFixed(1) + ' ms';
      document.getElementById('metric-loss').innerText = (active.loss_pct || 0.0).toFixed(1) + '%';

      if (active.loss_pct > 5.0) {
        document.getElementById('metric-loss').className = "text-3xl font-extrabold text-rose-400 font-mono tabular-nums";
        document.getElementById('metric-weather-alert').innerText = "Rain Attenuation: ELEVATED FADE DETECTED";
        document.getElementById('metric-weather-alert').className = "mt-1 text-[11px] text-rose-400 font-medium";
      } else {
        document.getElementById('metric-loss').className = "text-3xl font-extrabold text-emerald-400 font-mono tabular-nums";
        document.getElementById('metric-weather-alert').innerText = "Rain Attenuation: Normal";
        document.getElementById('metric-weather-alert').className = "mt-1 text-[11px] text-slate-400";
      }

      // Watchdog Timer
      const watchdogSec = state.watchdog_remaining_sec || 0;
      const watchdogElem = document.getElementById('watchdog-val');
      if (watchdogSec > 0) {
        watchdogElem.innerText = watchdogSec + 's';
        watchdogElem.className = "text-3xl font-extrabold text-amber-400 font-mono tabular-nums animate-pulse";
      } else {
        watchdogElem.innerText = "ARMED";
        watchdogElem.className = "text-3xl font-extrabold text-indigo-300 font-mono";
      }

      // RF Signal Gauges
      document.getElementById('gauge-rsrp').innerText = active.rsrp ? active.rsrp + ' dBm' : '-85 dBm';
      document.getElementById('gauge-rsrq').innerText = active.rsrq ? active.rsrq + ' dB' : '-10 dB';
      document.getElementById('gauge-sinr').innerText = active.sinr ? active.sinr + ' dB' : '15 dB';

      // History Oscilloscope
      if (state.live_pings && state.live_pings.length > 0) {
        pingHistory = state.live_pings;
        drawOscilloscope();
      }

      // Band Matrix Scorecard Table
      const tbody = document.getElementById('matrix-tbody');
      if (state.bands_evaluated && state.bands_evaluated.length > 0) {
        tbody.innerHTML = '';
        state.bands_evaluated.forEach(b => {
          const tr = document.createElement('tr');
          const isWinner = state.recommendation && state.recommendation.winning_band === b.band;
          if (isWinner) tr.className = "bg-cyan-500/10 font-bold border-l-4 border-cyan-400";

          const rainBadge = b.rain_score >= 80 ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : b.rain_score >= 50 ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-rose-500/20 text-rose-300 border border-rose-500/30';

          tr.innerHTML = `
            <td class="py-2.5 px-3.5 font-semibold text-white">
              <div class="flex items-center space-x-2">
                <span>${b.name}</span>
                ${isWinner ? '<span class="px-1.5 py-0.5 rounded text-[9px] bg-cyan-400 text-black font-bold">WINNER</span>' : ''}
              </div>
            </td>
            <td class="py-2.5 px-3.5 text-slate-400">${b.frequency}</td>
            <td class="py-2.5 px-3.5 ${b.loss_pct > 0 ? 'text-rose-400' : 'text-emerald-400'}">${b.loss_pct.toFixed(1)}%</td>
            <td class="py-2.5 px-3.5 text-slate-200 tabular-nums">${b.latency_avg_ms.toFixed(1)} ms</td>
            <td class="py-2.5 px-3.5 text-amber-300 tabular-nums">${b.jitter_ms.toFixed(1)} ms</td>
            <td class="py-2.5 px-3.5 text-cyan-300 tabular-nums">${b.sinr} dB</td>
            <td class="py-2.5 px-3.5"><span class="px-2 py-0.5 rounded-md text-[10px] ${rainBadge}">${b.rain_score}/100</span></td>
            <td class="py-2.5 px-3.5 text-right">
              <button onclick="lockBand('${b.band}')" class="px-2.5 py-1 rounded-md bg-surface-muted hover:bg-surface-border text-cyan-300 text-[11px] border border-white/10 transition active:scale-95">
                Lock Carrier
              </button>
            </td>
          `;
          tbody.appendChild(tr);
        });
      }

      // AGY Decision Synthesis Card
      const agyCard = document.getElementById('agy-card');
      if (state.recommendation) {
        agyCard.classList.remove('hidden');
        document.getElementById('agy-summary').innerText = state.recommendation.reasoning_summary;
        const agyActions = document.getElementById('agy-actions');
        agyActions.innerHTML = `
          <button onclick="lockBand('${state.recommendation.winning_band}')" class="px-4 py-2 rounded-lg text-xs font-bold bg-cyan-400 hover:bg-cyan-300 text-black shadow-lg shadow-cyan-500/25 transition active:scale-95 flex items-center space-x-1.5">
            <span>Apply Selected Carrier (${state.recommendation.winning_band_name})</span>
          </button>
        `;
      }

      // Logs Box
      if (state.logs) {
        const logBox = document.getElementById('log-box');
        logBox.innerHTML = state.logs.map(l => {
          let color = 'text-slate-300';
          if (l.includes('[ERROR]')) color = 'text-rose-400 font-semibold';
          else if (l.includes('[WARN]')) color = 'text-amber-300';
          else if (l.includes('🏆') || l.includes('✓')) color = 'text-cyan-300 font-semibold';
          return `<div class="${color}">${l}</div>`;
        }).join('');
        logBox.scrollTop = logBox.scrollHeight;
        document.getElementById('log-count').innerText = state.logs.length + ' events';
      }
    }

    // Server-Sent Events (SSE) Stream
    function initSSE() {
      const source = new EventSource('/api/events');
      source.onmessage = (e) => {
        try {
          const state = JSON.parse(e.data);
          updateUI(state);
        } catch(err) {
          console.error("SSE parse error", err);
        }
      };
      source.onerror = () => {
        console.warn("SSE disconnected. Falling back to HTTP polling.");
        setTimeout(pollFallback, 2000);
      };
    }

    function pollFallback() {
      fetch('/api/state')
        .then(r => r.json())
        .then(state => {
          updateUI(state);
          setTimeout(pollFallback, 2000);
        })
        .catch(() => setTimeout(pollFallback, 4000));
    }

    function startCalibration() {
      const btn = document.getElementById('btn-calibrate');
      btn.classList.add('opacity-70', 'cursor-not-allowed');
      fetch('/api/action/calibrate', { method: 'POST' })
        .then(r => r.json())
        .then(d => console.log('Calibration initiated', d))
        .finally(() => {
          setTimeout(() => btn.classList.remove('opacity-70', 'cursor-not-allowed'), 2000);
        });
    }

    function revertAuto() {
      fetch('/api/action/revert', { method: 'POST' })
        .then(r => r.json())
        .then(d => alert('Emergency Revert Triggered: ' + d.message));
    }

    function lockBand(band) {
      fetch('/api/action/lock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ band: band })
      })
      .then(r => r.json())
      .then(d => alert('Carrier Lock Applied: ' + d.message));
    }

    initSSE();
  </script>
</body>
</html>
"""


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """Handles HTTP and SSE connections for real-time dashboard."""

    def log_message(self, format, *args):
        # Silence routine access logs
        return

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))
            return

        elif self.path == "/api/state":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            state = self._read_state()
            self.wfile.write(json.dumps(state).encode("utf-8"))
            return

        elif self.path == "/api/events":
            # Server-Sent Events (SSE)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            try:
                while True:
                    state = self._read_state()
                    payload = f"data: {json.dumps(state)}\n\n"
                    self.wfile.write(payload.encode("utf-8"))
                    self.wfile.flush()
                    time.sleep(1.0)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        elif self.path == "/api/report":
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="calibration-report.md"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            state = self._read_state()
            rec = state.get("recommendation") or {}
            md = rec.get("markdown_report") or "# No report available yet.\n\nPlease run the autonomous calibration sweep first."
            self.wfile.write(md.encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        global GLOBAL_CALIBRATOR
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""

        if self.path == "/api/action/calibrate":
            if GLOBAL_CALIBRATOR and not GLOBAL_CALIBRATOR.running:
                t = threading.Thread(target=GLOBAL_CALIBRATOR.run_sweep, daemon=True)
                t.start()
                resp = {"status": "started", "message": "Calibration sweep started"}
            elif GLOBAL_CALIBRATOR and GLOBAL_CALIBRATOR.running:
                resp = {"status": "already_running", "message": "Calibration is already active"}
            else:
                resp = {"status": "no_calibrator", "message": "Calibrator daemon not bound"}

            self._send_json(resp)
            return

        elif self.path == "/api/action/revert":
            if GLOBAL_CALIBRATOR:
                GLOBAL_CALIBRATOR.revert_to_auto()
                resp = {"status": "ok", "message": "Router reverted to AUTO mode."}
            else:
                resp = {"status": "error", "message": "Calibrator not loaded."}
            self._send_json(resp)
            return

        elif self.path == "/api/action/lock":
            try:
                data = json.loads(body) if body else {}
                band = data.get("band", "auto")
                if GLOBAL_CALIBRATOR:
                    GLOBAL_CALIBRATOR.set_band_safe(band)
                    resp = {"status": "ok", "message": f"Locking to Band {band}."}
                else:
                    resp = {"status": "error", "message": "Calibrator not loaded."}
            except Exception as e:
                resp = {"status": "error", "message": str(e)}
            self._send_json(resp)
            return

        self.send_response(404)
        self.end_headers()

    def _send_json(self, data: dict):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _read_state(self) -> dict:
        global GLOBAL_CALIBRATOR
        if GLOBAL_CALIBRATOR:
            return GLOBAL_CALIBRATOR.get_state()
        if DEFAULT_STATE_FILE.exists():
            try:
                with open(DEFAULT_STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"status": "IDLE", "message": "Waiting for calibrator to start..."}


def start_dashboard_server(
    calibrator=None,
    host: str = "0.0.0.0",
    port: int = 8765,
    blocking: bool = True
) -> ThreadingHTTPServer:
    """Starts the real-time HTTP + SSE calibration dashboard server."""
    global GLOBAL_CALIBRATOR
    if calibrator:
        GLOBAL_CALIBRATOR = calibrator

    server = ThreadingHTTPServer((host, port), DashboardRequestHandler)
    logger.info(f"Calibration Web Dashboard running at http://{host}:{port}/")

    if blocking:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.shutdown()
    else:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server
