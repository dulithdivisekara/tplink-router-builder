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
from http.server import HTTPServer, BaseHTTPRequestHandler
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
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            tplink: { cyan: '#00B4D8', dark: '#0A1128', card: '#111827', accent: '#0077B6' }
          }
        }
      }
    }
  </script>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    .glass { background: rgba(17, 24, 39, 0.75); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); }
    .pulse-ring { animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: .4; transform: scale(1.05); } }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col selection:bg-cyan-500 selection:text-white">

  <!-- Top Navigation Header -->
  <header class="glass sticky top-0 z-50 px-6 py-4 border-b border-white/10 flex items-center justify-between">
    <div class="flex items-center space-x-3">
      <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-600 to-sky-400 flex items-center justify-center shadow-lg shadow-cyan-500/20 font-bold text-white text-lg">
        TP
      </div>
      <div>
        <h1 class="text-base font-semibold tracking-tight text-white flex items-center space-x-2">
          <span>TP-Link Autonomous RF Calibration Lab</span>
          <span class="px-2 py-0.5 text-[10px] uppercase font-mono tracking-wider rounded-full bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">AGY SDK</span>
        </h1>
        <p class="text-xs text-slate-400">Malabe, Sri Lanka (SLIIT Zone) • Hutch 20Mbps Unlimited LTE</p>
      </div>
    </div>

    <!-- Live Status Indicators & Controls -->
    <div class="flex items-center space-x-3">
      <div id="status-pill" class="flex items-center space-x-2 px-3 py-1.5 rounded-full text-xs font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
        <span class="w-2 h-2 rounded-full bg-emerald-400 pulse-ring"></span>
        <span id="status-text">CONNECTING</span>
      </div>

      <button onclick="revertAuto()" class="px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/30 transition flex items-center space-x-1">
        <span>⟳ Emergency Auto</span>
      </button>

      <button id="btn-calibrate" onclick="startCalibration()" class="px-4 py-1.5 rounded-lg text-xs font-semibold bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white shadow-md shadow-cyan-500/20 transition">
        ▶ Start Calibration
      </button>
    </div>
  </header>

  <!-- Main Container -->
  <main class="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">

    <!-- Active Telemetry & Watchdog Banner -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <!-- Active Band Card -->
      <div class="glass rounded-2xl p-5 border border-white/5 relative overflow-hidden">
        <div class="text-xs font-medium uppercase tracking-wider text-slate-400">Active Carrier Band</div>
        <div class="mt-2 flex items-baseline space-x-2">
          <span id="active-band" class="text-3xl font-extrabold text-cyan-400 font-mono">--</span>
          <span id="active-freq" class="text-xs text-slate-400 font-mono">Scanning...</span>
        </div>
        <div id="active-rain-tag" class="mt-3 text-[11px] text-slate-400">Penetration: Analyzing RF link</div>
      </div>

      <!-- Ping Latency Card -->
      <div class="glass rounded-2xl p-5 border border-white/5">
        <div class="text-xs font-medium uppercase tracking-wider text-slate-400">WAN Latency (1.1.1.1)</div>
        <div class="mt-2 flex items-baseline space-x-2">
          <span id="metric-latency" class="text-3xl font-extrabold text-white font-mono">0.0</span>
          <span class="text-xs text-slate-400 font-mono">ms</span>
        </div>
        <div id="metric-jitter" class="mt-3 text-[11px] text-amber-400">Jitter: 0.0 ms</div>
      </div>

      <!-- Packet Loss Card -->
      <div class="glass rounded-2xl p-5 border border-white/5">
        <div class="text-xs font-medium uppercase tracking-wider text-slate-400">Packet Loss</div>
        <div class="mt-2 flex items-baseline space-x-2">
          <span id="metric-loss" class="text-3xl font-extrabold text-emerald-400 font-mono">0.0%</span>
        </div>
        <div id="metric-weather-alert" class="mt-3 text-[11px] text-slate-400">Rain Attenuation: Normal</div>
      </div>

      <!-- Fail-Safe Watchdog Countdown -->
      <div class="glass rounded-2xl p-5 border border-white/5">
        <div class="text-xs font-medium uppercase tracking-wider text-slate-400">45s Watchdog Fail-Safe</div>
        <div class="mt-2 flex items-baseline space-x-2">
          <span id="watchdog-val" class="text-3xl font-extrabold text-indigo-400 font-mono">ARMED</span>
        </div>
        <div class="mt-3 text-[11px] text-slate-400">Auto-reverts to AUTO if WAN blackouts</div>
      </div>
    </div>

    <!-- RF Telemetry Arc Gauges & Live Oscilloscope -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- RF Gauges -->
      <div class="glass rounded-2xl p-6 border border-white/5 flex flex-col justify-between">
        <h3 class="text-sm font-semibold text-white tracking-tight flex items-center space-x-2">
          <span>Radio Frequency (RF) Signal Metrics</span>
        </h3>

        <div class="grid grid-cols-3 gap-3 my-6 text-center">
          <!-- RSRP Gauge -->
          <div class="p-3 rounded-xl bg-white/5 border border-white/5">
            <div class="text-[10px] text-slate-400 uppercase font-mono">RSRP (Power)</div>
            <div id="gauge-rsrp" class="text-xl font-bold font-mono text-cyan-400 mt-1">-85</div>
            <div class="text-[9px] text-slate-500">dBm (Target: &gt;-90)</div>
          </div>
          <!-- RSRQ Gauge -->
          <div class="p-3 rounded-xl bg-white/5 border border-white/5">
            <div class="text-[10px] text-slate-400 uppercase font-mono">RSRQ (Quality)</div>
            <div id="gauge-rsrq" class="text-xl font-bold font-mono text-sky-300 mt-1">-10</div>
            <div class="text-[9px] text-slate-500">dB (Target: &gt;-12)</div>
          </div>
          <!-- SINR Gauge -->
          <div class="p-3 rounded-xl bg-white/5 border border-white/5">
            <div class="text-[10px] text-slate-400 uppercase font-mono">SINR (SNR)</div>
            <div id="gauge-sinr" class="text-xl font-bold font-mono text-emerald-400 mt-1">18</div>
            <div class="text-[9px] text-slate-500">dB (Target: &gt;13)</div>
          </div>
        </div>

        <div class="text-xs text-slate-400 space-y-1">
          <div class="flex justify-between"><span>Path MTU Clamping:</span> <span class="font-mono text-cyan-300">1420 Bytes (GTP Clamped)</span></div>
          <div class="flex justify-between"><span>Congestion Control:</span> <span class="font-mono text-emerald-400">BBR active</span></div>
          <div class="flex justify-between"><span>DNS Override:</span> <span class="font-mono text-slate-300">8.8.8.8, 1.1.1.1</span></div>
        </div>
      </div>

      <!-- Real-Time Latency Oscilloscope -->
      <div class="lg:col-span-2 glass rounded-2xl p-6 border border-white/5 flex flex-col justify-between">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold text-white tracking-tight">Live Latency & Jitter Pulse Oscilloscope</h3>
          <span class="text-xs text-slate-500 font-mono">Continuous Ping to 1.1.1.1</span>
        </div>
        <div class="my-3 h-44 w-full bg-slate-900/60 rounded-xl relative overflow-hidden border border-white/5">
          <canvas id="osc-canvas" class="w-full h-full block"></canvas>
        </div>
        <div class="flex items-center justify-between text-xs text-slate-400">
          <span class="flex items-center space-x-1.5"><span class="w-2.5 h-2.5 rounded-full bg-cyan-400"></span><span>Latency (ms)</span></span>
          <span class="flex items-center space-x-1.5"><span class="w-2.5 h-2.5 rounded-full bg-amber-400"></span><span>Jitter Variance</span></span>
          <span id="canvas-rate" class="font-mono text-slate-500 text-[10px]">Real-Time Pulse (1s)</span>
        </div>
      </div>
    </div>

    <!-- Multi-Band Comparison Scorecard Table -->
    <div class="glass rounded-2xl p-6 border border-white/5 space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-sm font-semibold text-white tracking-tight">Cellular Band Performance & Rain Attenuation Matrix</h3>
          <p class="text-xs text-slate-400">Real-time sweep across Hutch Sri Lanka carriers (Band 8 900MHz, Band 3 1800MHz, Band 1, Band 40, Auto)</p>
        </div>
        <a href="/api/report" target="_blank" class="px-3 py-1.5 rounded-lg text-xs font-medium bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10 transition">
          📄 Export Markdown Report
        </a>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="text-[11px] uppercase tracking-wider text-slate-400 border-b border-white/10 font-mono">
            <tr>
              <th class="py-3 px-4">Carrier Band</th>
              <th class="py-3 px-4">Frequency</th>
              <th class="py-3 px-4">Packet Loss</th>
              <th class="py-3 px-4">Latency (avg)</th>
              <th class="py-3 px-4">Jitter</th>
              <th class="py-3 px-4">SINR</th>
              <th class="py-3 px-4">Rain Resilience</th>
              <th class="py-3 px-4">Status / Action</th>
            </tr>
          </thead>
          <tbody id="matrix-tbody" class="divide-y divide-white/5 font-mono">
            <tr>
              <td colspan="8" class="py-8 text-center text-slate-500 font-sans">
                No bands evaluated yet. Click <strong>Start Calibration</strong> above to initiate autonomous sweep.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- AGY Decision Synthesis Box -->
    <div id="agy-card" class="hidden glass rounded-2xl p-6 border border-cyan-500/30 bg-gradient-to-br from-cyan-950/20 via-slate-900/60 to-slate-950 space-y-3">
      <div class="flex items-center space-x-2 text-cyan-400">
        <span class="text-lg">🧠</span>
        <h3 class="text-sm font-bold tracking-tight text-white uppercase font-mono">Google Antigravity (AGY) Autonomous Recommendation</h3>
      </div>
      <div id="agy-summary" class="text-sm text-slate-200 leading-relaxed">
        Evaluating...
      </div>
      <div id="agy-actions" class="flex items-center space-x-3 pt-2">
        <!-- Injected button -->
      </div>
    </div>

    <!-- Live Execution Logs -->
    <div class="glass rounded-2xl p-6 border border-white/5 space-y-3">
      <div class="flex items-center justify-between">
        <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400 font-mono">Live Telemetry & Engine Execution Log</h3>
        <span id="log-count" class="text-[10px] text-slate-500 font-mono">0 events</span>
      </div>
      <div id="log-box" class="h-36 overflow-y-auto rounded-xl bg-black/50 p-4 font-mono text-[11px] text-slate-300 space-y-1">
        <div>[00:00:00] [INFO] Dashboard initialized. Awaiting calibration trigger.</div>
      </div>
    </div>
  </main>

  <footer class="mt-auto px-6 py-4 border-t border-white/5 text-center text-xs text-slate-500">
    TP-Link Universal Agentic Ecosystem • Created by <a href="https://dulith.me" class="text-cyan-400 hover:underline">Dulith Divisekara</a> (SLIIT Malabe) • Powered by Google Antigravity SDK
  </footer>

  <script>
    const canvas = document.getElementById('osc-canvas');
    const ctx = canvas.getContext('2d');
    let pingHistory = [];

    function resizeCanvas() {
      canvas.width = canvas.parentElement.clientWidth;
      canvas.height = canvas.parentElement.clientHeight;
    }
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    function drawOscilloscope() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const w = canvas.width;
      const h = canvas.height;

      // Draw grid
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
      ctx.lineWidth = 1;
      for (let y = 20; y < h; y += 30) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }

      if (pingHistory.length < 2) return;

      const step = w / Math.max(20, pingHistory.length - 1);

      // Latency line (Cyan)
      ctx.beginPath();
      ctx.strokeStyle = '#00B4D8';
      ctx.lineWidth = 2;
      pingHistory.forEach((p, idx) => {
        const x = idx * step;
        const normalized = Math.min(h - 10, Math.max(10, h - (p.latency_ms / 200) * (h - 20)));
        if (idx === 0) ctx.moveTo(x, normalized);
        else ctx.lineTo(x, normalized);
      });
      ctx.stroke();

      // Jitter line (Amber)
      ctx.beginPath();
      ctx.strokeStyle = '#F59E0B';
      ctx.lineWidth = 1.5;
      pingHistory.forEach((p, idx) => {
        const x = idx * step;
        const normalized = Math.min(h - 10, Math.max(10, h - (p.jitter_ms / 100) * (h - 20)));
        if (idx === 0) ctx.moveTo(x, normalized);
        else ctx.lineTo(x, normalized);
      });
      ctx.stroke();
    }

    function updateUI(state) {
      if (!state) return;

      // Status
      const statusPill = document.getElementById('status-pill');
      const statusText = document.getElementById('status-text');
      statusText.innerText = state.status + (state.current_phase ? ' (' + state.current_phase + ')' : '');

      if (state.status === 'RUNNING') {
        statusPill.className = "flex items-center space-x-2 px-3 py-1.5 rounded-full text-xs font-mono font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/30";
      } else if (state.status === 'COMPLETED') {
        statusPill.className = "flex items-center space-x-2 px-3 py-1.5 rounded-full text-xs font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30";
      }

      // Active metrics
      const active = state.active_metrics || {};
      document.getElementById('active-band').innerText = (state.current_band || 'AUTO').toUpperCase();
      document.getElementById('active-freq').innerText = state.current_band === '8' ? '900 MHz' : state.current_band === '3' ? '1800 MHz' : state.current_band === '1' ? '2100 MHz' : state.current_band === '40' ? '2300 MHz' : 'Multi-Band';
      document.getElementById('metric-latency').innerText = (active.latency_ms || 0.0).toFixed(1);
      document.getElementById('metric-jitter').innerText = 'Jitter: ' + (active.jitter_ms || 0.0).toFixed(1) + ' ms';
      document.getElementById('metric-loss').innerText = (active.loss_pct || 0.0).toFixed(1) + '%';

      if (active.loss_pct > 5.0) {
        document.getElementById('metric-loss').className = "text-3xl font-extrabold text-rose-400 font-mono";
        document.getElementById('metric-weather-alert').innerText = "Rain Attenuation: ELEVATED FADE DETECTED";
        document.getElementById('metric-weather-alert').className = "mt-3 text-[11px] text-rose-400 font-semibold";
      } else {
        document.getElementById('metric-loss').className = "text-3xl font-extrabold text-emerald-400 font-mono";
        document.getElementById('metric-weather-alert').innerText = "Rain Attenuation: Normal";
        document.getElementById('metric-weather-alert').className = "mt-3 text-[11px] text-slate-400";
      }

      // Watchdog
      const watchdogSec = state.watchdog_remaining_sec || 0;
      const watchdogElem = document.getElementById('watchdog-val');
      if (watchdogSec > 0) {
        watchdogElem.innerText = watchdogSec + 's';
        watchdogElem.className = "text-3xl font-extrabold text-amber-400 font-mono animate-pulse";
      } else {
        watchdogElem.innerText = "ARMED";
        watchdogElem.className = "text-3xl font-extrabold text-indigo-400 font-mono";
      }

      // RF Gauges
      document.getElementById('gauge-rsrp').innerText = active.rsrp ? active.rsrp + ' dBm' : '-85 dBm';
      document.getElementById('gauge-rsrq').innerText = active.rsrq ? active.rsrq + ' dB' : '-10 dB';
      document.getElementById('gauge-sinr').innerText = active.sinr ? active.sinr + ' dB' : '15 dB';

      // History Oscilloscope
      if (state.live_pings && state.live_pings.length > 0) {
        pingHistory = state.live_pings;
        drawOscilloscope();
      }

      // Band matrix table
      const tbody = document.getElementById('matrix-tbody');
      if (state.bands_evaluated && state.bands_evaluated.length > 0) {
        tbody.innerHTML = '';
        state.bands_evaluated.forEach(b => {
          const tr = document.createElement('tr');
          const isWinner = state.recommendation && state.recommendation.winning_band === b.band;
          if (isWinner) tr.className = "bg-cyan-500/10 font-bold border-l-4 border-cyan-400";

          const rainBadge = b.rain_score >= 80 ? 'bg-emerald-500/20 text-emerald-400' : b.rain_score >= 50 ? 'bg-amber-500/20 text-amber-400' : 'bg-rose-500/20 text-rose-400';

          tr.innerHTML = `
            <td class="py-3 px-4 font-semibold text-white flex items-center space-x-2">
              <span>${b.name}</span>
              ${isWinner ? '<span class="px-1.5 py-0.5 rounded text-[9px] bg-cyan-400 text-slate-950">WINNER</span>' : ''}
            </td>
            <td class="py-3 px-4 text-slate-400">${b.frequency}</td>
            <td class="py-3 px-4 ${b.loss_pct > 0 ? 'text-rose-400' : 'text-emerald-400'}">${b.loss_pct.toFixed(1)}%</td>
            <td class="py-3 px-4 text-slate-200">${b.latency_avg_ms.toFixed(1)} ms</td>
            <td class="py-3 px-4 text-amber-300">${b.jitter_ms.toFixed(1)} ms</td>
            <td class="py-3 px-4 text-cyan-300">${b.sinr} dB</td>
            <td class="py-3 px-4"><span class="px-2 py-0.5 rounded-full text-[10px] ${rainBadge}">${b.rain_score}/100</span></td>
            <td class="py-3 px-4">
              <button onclick="lockBand('${b.band}')" class="px-2.5 py-1 rounded bg-white/5 hover:bg-white/10 text-cyan-300 text-[10px] border border-white/10 transition">
                Lock
              </button>
            </td>
          `;
          tbody.appendChild(tr);
        });
      }

      // AGY Decision Card
      const agyCard = document.getElementById('agy-card');
      if (state.recommendation) {
        agyCard.classList.remove('hidden');
        document.getElementById('agy-summary').innerText = state.recommendation.reasoning_summary;
        const agyActions = document.getElementById('agy-actions');
        agyActions.innerHTML = `
          <button onclick="lockBand('${state.recommendation.winning_band}')" class="px-4 py-2 rounded-xl text-xs font-bold bg-cyan-500 hover:bg-cyan-400 text-slate-950 shadow-lg shadow-cyan-500/20 transition">
            Apply Winning Band (${state.recommendation.winning_band_name})
          </button>
        `;
      }

      // Logs
      if (state.logs) {
        const logBox = document.getElementById('log-box');
        logBox.innerHTML = state.logs.map(l => `<div>${l}</div>`).join('');
        logBox.scrollTop = logBox.scrollHeight;
        document.getElementById('log-count').innerText = state.logs.length + ' events';
      }
    }

    // SSE Stream
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
        console.warn("SSE disconnected. Polling fallback active.");
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
      fetch('/api/action/calibrate', { method: 'POST' })
        .then(r => r.json())
        .then(d => console.log('Calibration initiated', d));
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
      .then(d => alert('Band locked: ' + d.message));
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
            self.send_header("Content-Disposition", "inline; filename=calibration-report.md")
            self.end_headers()
            state = self._read_state()
            rec = state.get("recommendation", {})
            md = rec.get("markdown_report", "# No report available yet.\nRun calibration first.")
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
) -> HTTPServer:
    """Starts the real-time HTTP + SSE calibration dashboard server."""
    global GLOBAL_CALIBRATOR
    if calibrator:
        GLOBAL_CALIBRATOR = calibrator

    server = HTTPServer((host, port), DashboardRequestHandler)
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
