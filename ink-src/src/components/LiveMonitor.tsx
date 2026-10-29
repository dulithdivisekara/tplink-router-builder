import React from 'react';
import { Box, Text } from 'ink';
import { TelemetryData } from '../bridgeClient.js';
import {
  formatThroughput,
  getPalette,
  renderGaugeBar,
  renderSignalStepBars,
  renderSparkline,
} from '../theme.js';

export interface LiveMonitorProps {
  telemetry: TelemetryData | null;
  rxHistory: number[];
  txHistory: number[];
  barHistory: number[];
  streaming: boolean;
  sampleCount: number;
  tick: number;
  mono: boolean;
  animated: boolean;
  columns: number;
}

export const LiveMonitor: React.FC<LiveMonitorProps> = ({
  telemetry,
  rxHistory,
  txHistory,
  barHistory,
  streaming,
  sampleCount,
  tick,
  mono,
  animated,
  columns,
}) => {
  const p = getPalette(mono);
  const pulseOn = !animated || Math.floor(tick / 4) % 2 === 0;
  const sparkWidth = Math.max(20, Math.min(54, columns - 44));

  const rxPeak = Math.max(0, ...rxHistory);
  const txPeak = Math.max(0, ...txHistory);
  const curRx = telemetry?.rx_kbps ?? 0;
  const curTx = telemetry?.tx_kbps ?? 0;
  const curBars = telemetry?.bars ?? 0;
  const effectiveRating =
    telemetry?.rsrp_rating && telemetry.rsrp_rating !== 'N/A'
      ? telemetry.rsrp_rating
      : telemetry?.rssi_rating && telemetry.rssi_rating !== 'N/A'
      ? telemetry.rssi_rating
      : 'Stable';

  return (
    <Box flexDirection="column" width="100%" flexGrow={1}>
      {/* Live Stream Status Header */}
      <Box
        borderStyle="round"
        borderColor={p.borderActive}
        paddingX={1}
        flexDirection="row"
        justifyContent="space-between"
      >
        <Box flexGrow={1} flexShrink={1} marginRight={1}>
          <Text wrap="truncate-end">
            <Text color={streaming ? p.success : p.warning} bold>
              {streaming ? (pulseOn ? '◉ LIVE RF STREAM' : '● LIVE RF STREAM') : '⏸ STREAM PAUSED'}
            </Text>
            <Text color={p.muted}>  •  </Text>
            <Text color={p.white} bold>
              {telemetry?.model || 'TP-Link LTE Gateway'}
            </Text>
            <Text color={p.muted}>
              {'  '}(Samples: {sampleCount} • SafeSession 3.5s)
            </Text>
          </Text>
        </Box>
        <Box flexShrink={0}>
          <Text>
            <Text color={p.brand}>[p]</Text>
            <Text color={p.muted}> {streaming ? 'Pause' : 'Resume'}  </Text>
            <Text color={p.brand}>[r]</Text>
            <Text color={p.muted}> Sample  </Text>
            <Text color={p.brand}>[b]</Text>
            <Text color={p.muted}> Band Lock</Text>
          </Text>
        </Box>
      </Box>

      {/* 3-Card Telemetry Row */}
      <Box flexDirection="row" width="100%" gap={1}>
        {/* Card 1: Cellular Baseband */}
        <Box
          borderStyle="round"
          borderColor={p.border}
          paddingX={1}
          flexDirection="column"
          width="34%"
        >
          <Text color={p.brand} bold wrap="truncate-end">
            ▲ CELLULAR BASEBAND
          </Text>
          <Box flexDirection="row" justifyContent="space-between">
            <Text color={p.muted}>Carrier</Text>
            <Text color={p.white} bold wrap="truncate-end">
              {telemetry?.carrier || 'Polling…'}
            </Text>
          </Box>
          <Box flexDirection="row" justifyContent="space-between">
            <Text color={p.muted}>LTE Band</Text>
            <Text color={p.brandBright} bold wrap="truncate-end">
              {telemetry?.band || '—'}
            </Text>
          </Box>
          <Box flexDirection="row" justifyContent="space-between">
            <Text color={p.muted}>EARFCN/PCI</Text>
            <Text color={p.text}>
              {telemetry?.earfcn || 'N/A'} / {telemetry?.pci || '0'}
            </Text>
          </Box>
          <Box flexDirection="row" justifyContent="space-between">
            <Text color={p.muted}>Cell Lock</Text>
            <Text color={telemetry?.cell_locked ? p.success : p.muted}>
              {telemetry?.cell_locked ? '● LOCKED' : '○ AUTO ROAM'}
            </Text>
          </Box>
        </Box>

        {/* Card 2: RF Signal Quality */}
        <Box
          borderStyle="round"
          borderColor={p.border}
          paddingX={1}
          flexDirection="column"
          width="33%"
        >
          <Text color={p.brand} bold wrap="truncate-end">
            ▂▄▆█ RF SIGNAL QUALITY
          </Text>
          <Box flexDirection="row" justifyContent="space-between">
            <Text color={p.muted}>Strength</Text>
            <Text color={p.brand} bold>
              {renderSignalStepBars(curBars)} {curBars}/4
            </Text>
          </Box>
          <Box flexDirection="row" justifyContent="space-between">
            <Text color={p.muted}>RF Meter</Text>
            <Text color={p.brandBright}>{renderGaugeBar(curBars, 4, 12)}</Text>
          </Box>
          <Box flexDirection="row" justifyContent="space-between">
            <Text color={p.muted}>RSSI</Text>
            <Text color={p.text}>
              {telemetry?.rssi_dbm ? `${telemetry.rssi_dbm} dBm` : '0 dBm'} ({effectiveRating})
            </Text>
          </Box>
          <Box flexDirection="row" justifyContent="space-between">
            <Text color={p.muted}>RSRQ / SNR</Text>
            <Text color={p.text}>
              {telemetry?.rsrq_db ?? 0} dB / {telemetry?.snr_db ?? 0} dB
            </Text>
          </Box>
        </Box>

        {/* Card 3: WAN & IPv6 Gateway */}
        <Box
          borderStyle="round"
          borderColor={p.border}
          paddingX={1}
          flexDirection="column"
          width="33%"
        >
          <Text color={p.brand} bold wrap="truncate-end">
            ◆ WAN & IPv6 STACK
          </Text>
          <Box flexDirection="row" justifyContent="space-between">
            <Text color={p.muted}>WAN IPv4</Text>
            <Text color={p.white} bold>
              {telemetry?.wan_ip || '—'}
            </Text>
          </Box>
          <Box flexDirection="row" justifyContent="space-between">
            <Text color={p.muted}>DNS</Text>
            <Text color={p.text} wrap="truncate-end">
              {telemetry?.dns && telemetry.dns.length > 0 ? telemetry.dns.slice(0, 2).join(', ') : 'ISP Auto'}
            </Text>
          </Box>
          <Box flexDirection="row" justifyContent="space-between">
            <Text color={p.muted}>IPv6 Stack</Text>
            <Text color={telemetry?.ipv6_enabled ? p.success : p.muted} bold>
              {telemetry?.ipv6_enabled ? '● ENABLED' : '○ DISABLED'}
            </Text>
          </Box>
          <Box flexDirection="row" justifyContent="space-between">
            <Text color={p.muted}>Transferred</Text>
            <Text color={p.text}>{telemetry?.total_mb ?? 0} MB</Text>
          </Box>
        </Box>
      </Box>

      {/* Real-Time Scrolling Sparkline Waveforms */}
      <Box
        borderStyle="round"
        borderColor={p.borderActive}
        paddingX={1}
        flexDirection="column"
        flexGrow={1}
      >
        <Box flexDirection="row" justifyContent="space-between">
          <Text color={p.brand} bold>
            ✦ REAL-TIME THROUGHPUT & RF STABILITY WAVEFORMS
          </Text>
          <Text color={p.muted}>
            Handshake RTT: {telemetry?.elapsed_ms ? `${telemetry.elapsed_ms} ms` : '—'}
          </Text>
        </Box>

        <Box flexDirection="row" justifyContent="space-between">
          <Text wrap="truncate-end">
            <Text color={p.brand} bold>
              ↓ Downlink{'  '}
            </Text>
            <Text color={p.brandBright}>{renderSparkline(rxHistory, sparkWidth, 64)}</Text>
          </Text>
          <Text color={p.white}>
            {formatThroughput(curRx)} <Text color={p.muted}>(Peak {formatThroughput(rxPeak)})</Text>
          </Text>
        </Box>

        <Box flexDirection="row" justifyContent="space-between">
          <Text wrap="truncate-end">
            <Text color={p.success} bold>
              ↑ Uplink  {'  '}
            </Text>
            <Text color={p.success}>{renderSparkline(txHistory, sparkWidth, 32)}</Text>
          </Text>
          <Text color={p.white}>
            {formatThroughput(curTx)} <Text color={p.muted}>(Peak {formatThroughput(txPeak)})</Text>
          </Text>
        </Box>

        <Box flexDirection="row" justifyContent="space-between">
          <Text wrap="truncate-end">
            <Text color={p.white} bold>
              ▲ RF Bars {'  '}
            </Text>
            <Text color={p.brand}>{renderSparkline(barHistory, sparkWidth, 4)}</Text>
          </Text>
          <Text color={p.white}>
            {curBars} / 4 Bars <Text color={p.muted}>({effectiveRating})</Text>
          </Text>
        </Box>
      </Box>
    </Box>
  );
};
