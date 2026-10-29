import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Box, Text, useApp, useInput, useStdout } from 'ink';
import { writeFileSync } from 'node:fs';
import {
  RouterBridgeClient,
  SwitchStates,
  TelemetryData,
} from './bridgeClient.js';
import {
  COMMAND_SPECS,
  CommandSpec,
  getTabItems,
  InteractiveMode,
  TUI_TABS,
} from './catalog.js';
import { ActivityBar, BusyTask } from './components/ActivityBar.js';
import { LiveMonitor } from './components/LiveMonitor.js';
import { TPLinkLogo } from './components/Logo.js';
import { ModalConfig, ModalOverlay } from './components/ModalOverlay.js';
import {
  formatThroughput,
  getPalette,
  renderSignalStepBars,
} from './theme.js';

export type TestScene = 'workspace' | 'busy' | 'live' | 'switchboard';

export interface AppProps {
  bridge: RouterBridgeClient;
  host: string;
  initialMono?: boolean;
  initialAnimated?: boolean;
  initialTick?: number;
  handoffFile?: string;
  overrideCols?: number;
  overrideRows?: number;
  testScene?: TestScene;
  noInitialPoll?: boolean;
  onPrintOnExit?: (output: string) => void;
}

function buildInteractiveModal(mode: InteractiveMode): ModalConfig | null {
  switch (mode) {
    case 'band':
    case 'band_picker':
      return {
        kind: 'single',
        actionId: 'band',
        title: 'LTE FREQUENCY BAND LOCK PICKER',
        subtitle: 'Select carrier LTE frequency band to inspect or lock hardware modem:',
        cursor: mode === 'band_picker' ? 1 : 0,
        options: [
          { value: '__view__', label: 'Inspect Active Band', hint: 'Read current band, EARFCN & PCI' },
          { value: '8', label: 'Lock Band 8  (900 MHz)', hint: 'Extended range & indoor wall penetration' },
          { value: '3', label: 'Lock Band 3  (1800 MHz)', hint: 'High capacity urban FDD carrier' },
          { value: '1', label: 'Lock Band 1  (2100 MHz)', hint: 'Standard 4G LTE capacity band' },
          { value: '40', label: 'Lock Band 40 (2300 MHz)', hint: 'High-speed TDD carrier band' },
          { value: 'auto', label: 'Auto Carrier Selection', hint: 'Allow modem automatic band roaming' },
        ],
      };
    case 'calibrate':
      return {
        kind: 'multi',
        actionId: 'calibrate',
        title: 'MULTI-BAND RF CALIBRATION CHECKLIST',
        subtitle: 'Use Spacebar to toggle candidate LTE bands [✔], then press Enter:',
        cursor: 0,
        options: [
          { value: '8', label: 'Band 8  (900 MHz)', hint: 'Low-band coverage anchor', checked: true },
          { value: '3', label: 'Band 3  (1800 MHz)', hint: 'Mid-band throughput carrier', checked: true },
          { value: '1', label: 'Band 1  (2100 MHz)', hint: 'Core 2100MHz LTE layer', checked: false },
          { value: '40', label: 'Band 40 (2300 MHz)', hint: 'High-capacity TDD band', checked: false },
          { value: 'auto', label: 'Auto Baseline', hint: 'Include automatic modem baseline', checked: true },
        ],
      };
    case 'ipv6':
      return {
        kind: 'single',
        actionId: 'ipv6',
        title: 'ROUTER IPv6 STACK CONTROL',
        subtitle: 'Inspect or toggle router WAN IPv6 bearer stack:',
        cursor: 0,
        options: [
          { value: '__view__', label: 'Inspect IPv6 Status', hint: 'Check enabled state, IPv6 IP & DNS' },
          { value: 'on', label: 'Enable IPv6 Stack', hint: 'Turn WAN IPv6 addressing ON' },
          { value: 'off', label: 'Disable IPv6 Stack', hint: 'Turn WAN IPv6 addressing OFF' },
        ],
      };
    case 'upnp':
      return {
        kind: 'single',
        actionId: 'upnp',
        title: 'UNIVERSAL PLUG AND PLAY (UPnP)',
        subtitle: 'Inspect active dynamic port mappings or toggle UPnP service:',
        cursor: 0,
        options: [
          { value: '__view__', label: 'Inspect UPnP Status & Leases', hint: 'Show active UPnP table' },
          { value: 'on', label: 'Enable UPnP Service', hint: 'Allow automatic LAN port mappings' },
          { value: 'off', label: 'Disable UPnP Service', hint: 'Harden NAT perimeter' },
        ],
      };
    case 'wifi':
      return {
        kind: 'single',
        actionId: 'wifi',
        title: 'DUAL-BAND WI-FI RADIO CONTROL',
        subtitle: 'Inspect wireless radios or toggle 2.4GHz / 5GHz bands:',
        cursor: 0,
        options: [
          { value: '__view__', label: 'Inspect 2.4GHz & 5GHz Status', hint: 'View SSIDs, channels & clients' },
          { value: '2.4_on', label: 'Enable 2.4GHz Wi-Fi Radio', hint: 'Turn 2.4GHz wireless ON' },
          { value: '5_on', label: 'Enable 5GHz Wi-Fi Radio', hint: 'Turn 5GHz wireless ON' },
          { value: '5_off', label: 'Disable 5GHz Wi-Fi Radio', hint: 'Save power when 5GHz unused' },
        ],
      };
    case 'leds':
      return {
        kind: 'single',
        actionId: 'leds',
        title: 'HARDWARE LED & NIGHT MODE CONTROL',
        subtitle: 'Inspect front-panel LEDs or toggle Night Mode quiet schedule:',
        cursor: 0,
        options: [
          { value: '__view__', label: 'Inspect LED & Night Mode', hint: 'Read current LED schedule' },
          { value: 'on', label: 'Enable LED Night Mode', hint: 'Quiet hours 22:00 -> 07:00' },
          { value: 'off', label: 'Disable LED Night Mode', hint: 'Keep status LEDs active 24/7' },
        ],
      };
    case 'dns':
      return {
        kind: 'single',
        actionId: 'dns',
        title: 'WAN DNS RESOLVER PRESETS',
        subtitle: 'Inspect active WAN DNS servers or apply encrypted/fast resolver pair:',
        cursor: 0,
        options: [
          { value: '__view__', label: 'Inspect Active DNS Servers', hint: 'Read current primary & secondary DNS' },
          { value: '1.1.1.1,1.0.0.1', label: 'Cloudflare DNS (1.1.1.1)', hint: 'Ultra-low latency privacy resolver' },
          { value: '8.8.8.8,8.8.4.4', label: 'Google Public DNS (8.8.8.8)', hint: 'Global high-availability DNS' },
          { value: '9.9.9.9,149.112.112.112', label: 'Quad9 Security DNS (9.9.9.9)', hint: 'Malware & phishing domain blocking' },
          { value: '94.140.14.14,94.140.15.15', label: 'AdGuard DNS (94.140.14.14)', hint: 'Network-wide ad & tracker filtering' },
        ],
      };
    case 'sms':
      return {
        kind: 'single',
        actionId: 'sms',
        title: 'CELLULAR SIM SMS FOLDERS',
        subtitle: 'Choose SIM message mailbox to inspect:',
        cursor: 0,
        options: [
          { value: 'inbox', label: 'Read SMS Inbox', hint: 'Incoming carrier & OTP messages' },
          { value: 'sent', label: 'Read Sent Messages', hint: 'Outgoing transmitted SMS messages' },
        ],
      };
    case 'ussd':
      return {
        kind: 'input',
        actionId: 'ussd',
        title: 'CELLULAR USSD SESSION QUERY',
        subtitle: 'Enter GSM/LTE USSD code to transmit to cellular carrier:',
        cursor: 0,
        options: [],
        textValue: '*344#',
      };
    case 'reboot':
      return {
        kind: 'single',
        actionId: 'reboot',
        title: 'PROTECTED HARDWARE REBOOT',
        subtitle: 'Confirm router restart (temporarily drops Wi-Fi & LTE for ~75s):',
        cursor: 0,
        options: [
          { value: 'cancel', label: 'Cancel (Keep Router Online)', hint: 'Abort reboot safely' },
          { value: 'confirm', label: 'Confirm Hardware Reboot Now', hint: 'Executes tplink-cli reboot --yes' },
        ],
      };
    default:
      return null;
  }
}

export const App: React.FC<AppProps> = ({
  bridge,
  host,
  initialMono = false,
  initialAnimated = true,
  initialTick = 0,
  handoffFile,
  overrideCols,
  overrideRows,
  testScene,
  noInitialPoll = false,
  onPrintOnExit,
}) => {
  const { exit } = useApp();
  const { stdout } = useStdout();

  const [dims, setDims] = useState<{ cols: number; rows: number }>({
    cols: overrideCols || stdout?.columns || 100,
    rows: overrideRows || stdout?.rows || 30,
  });

  useEffect(() => {
    if (overrideCols || overrideRows || !stdout) return;
    const onResize = () => {
      setDims({
        cols: stdout.columns || 100,
        rows: stdout.rows || 30,
      });
    };
    stdout.on('resize', onResize);
    return () => {
      stdout.off('resize', onResize);
    };
  }, [stdout, overrideCols, overrideRows]);

  const [mono, setMono] = useState<boolean>(initialMono);
  const [animated, setAnimated] = useState<boolean>(initialAnimated);
  const [tick, setTick] = useState<number>(initialTick);

  const [tabIdx, setTabIdx] = useState<number>(testScene === 'live' ? 1 : 0);
  const [cursor, setCursor] = useState<number>(0);
  const [checkedSet, setCheckedSet] = useState<string[]>(
    testScene === 'workspace' ? ['status', 'signal'] : []
  );
  const [searchMode, setSearchMode] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');

  const [viewMode, setViewMode] = useState<'workspace' | 'output'>('workspace');
  const [outputTitle, setOutputTitle] = useState<string>('');
  const [outputLines, setOutputLines] = useState<string[]>([]);
  const [outputScroll, setOutputScroll] = useState<number>(0);
  const [lastRunCommand, setLastRunCommand] = useState<string[] | null>(null);

  const [busyTask, setBusyTask] = useState<BusyTask | null>(
    testScene === 'busy'
      ? {
          label: `Negotiating RSA-1024 session lease & polling ${host} RF telemetry…`,
          startedAt: Date.now() - 840,
        }
      : null
  );
  const [lastSummary, setLastSummary] = useState<string>(
    testScene
      ? 'Connected to Archer MR200 (Hutch Internet • Band 8 • 420ms)'
      : 'Ready • Press Enter to execute, Space to queue [✔], or l for Live RF Stream'
  );

  const [telemetry, setTelemetry] = useState<TelemetryData | null>(
    testScene
      ? {
          online: true,
          elapsed_ms: 410,
          timestamp: Date.now() / 1000,
          model: 'Archer MR200',
          carrier: 'Hutch Internet',
          connected: true,
          band: 'Band 8 (900 MHz)',
          earfcn: '3738',
          pci: '0',
          cell_locked: false,
          bars: 4,
          rssi_dbm: -63,
          rsrp_dbm: 0,
          rsrp_rating: 'Excellent',
          rsrq_db: 0,
          snr_db: 0,
          rx_kbps: 2840,
          tx_kbps: 710,
          total_mb: 1482.4,
          wan_ip: '100.82.14.91',
          dns: ['1.1.1.1', '8.8.8.8'],
          ipv6_enabled: true,
        }
      : null
  );

  const [rxHistory, setRxHistory] = useState<number[]>(
    testScene ? [420, 680, 1240, 1890, 2410, 1950, 2680, 3120, 2740, 2290, 2910, 2840] : []
  );
  const [txHistory, setTxHistory] = useState<number[]>(
    testScene ? [120, 210, 340, 490, 520, 410, 680, 790, 610, 540, 720, 710] : []
  );
  const [barHistory, setBarHistory] = useState<number[]>(
    testScene ? [4, 4, 4, 3, 4, 4, 4, 4, 4, 4, 4, 4] : []
  );
  const [sampleCount, setSampleCount] = useState<number>(testScene ? 12 : 0);
  const [liveStreaming, setLiveStreaming] = useState<boolean>(true);

  const initialSwitchesRef = useRef<SwitchStates>({
    ipv6: true,
    wifi_2g: true,
    wifi_5g: true,
    guest_wifi: false,
    upnp: true,
    led_night: false,
  });

  const [modal, setModal] = useState<ModalConfig | null>(
    testScene === 'switchboard'
      ? {
          kind: 'toggles',
          actionId: 'toggles',
          title: 'QUICK FEATURE SWITCHBOARD (LIVE ROUTER TOGGLES)',
          subtitle: 'Flip hardware features with Spacebar [● ON / ○ OFF], then press Enter:',
          cursor: 0,
          options: [
            { value: 'ipv6', label: 'IPv6 WAN Stack', hint: 'Dual-stack IPv6 bearer & SLAAC', checked: true },
            { value: 'wifi_2g', label: '2.4GHz Wi-Fi Radio', hint: 'Primary 2.4GHz wireless coverage', checked: true },
            { value: 'wifi_5g', label: '5GHz Wi-Fi Radio', hint: 'High-speed 5GHz AC wireless', checked: true },
            { value: 'guest_wifi', label: 'Guest Wi-Fi Network', hint: 'Isolated visitor wireless SSID', checked: false },
            { value: 'upnp', label: 'UPnP Port Mapping', hint: 'Automatic NAT traversal leases', checked: true },
            { value: 'led_night', label: 'LED Night Mode', hint: 'Auto-dim front LEDs (22:00-07:00)', checked: false },
          ],
        }
      : null
  );

  const p = getPalette(mono);
  const activeTab = TUI_TABS[tabIdx] || TUI_TABS[0];
  const items = useMemo(
    () => getTabItems(activeTab.id, searchQuery),
    [activeTab.id, searchQuery]
  );

  useEffect(() => {
    if (cursor >= items.length && items.length > 0) {
      setCursor(items.length - 1);
    }
  }, [items.length, cursor]);

  // Shared 12.5 FPS animation clock (disabled in static testScene snapshots)
  useEffect(() => {
    if (!animated || testScene) return;
    const timer = setInterval(() => {
      setTick((t) => (t + 1) % 100000);
    }, 80);
    return () => clearInterval(timer);
  }, [animated, testScene]);

  const pollTelemetry = useCallback(
    async (silent = false) => {
      if (bridge.isBusy) return;
      if (!silent) {
        setBusyTask({
          label: `Polling TP-Link Gateway (${host}) RF & WAN telemetry…`,
          startedAt: Date.now(),
        });
      }
      try {
        const data = await bridge.getTelemetry();
        setTelemetry(data);
        if (data.online) {
          setRxHistory((prev) => [...prev.slice(-47), data.rx_kbps ?? 0]);
          setTxHistory((prev) => [...prev.slice(-47), data.tx_kbps ?? 0]);
          setBarHistory((prev) => [...prev.slice(-47), data.bars ?? 0]);
          setSampleCount((c) => c + 1);
          setLastSummary(
            `Synced ${data.model || 'Router'} • ${data.carrier || 'WAN'} • ${data.band || ''} (${data.elapsed_ms}ms)`
          );
        } else {
          setLastSummary(`Gateway unreachable (${host}) • Press r to retry`);
        }
      } catch (err: any) {
        setLastSummary(`Telemetry poll failed: ${err?.message || err}`);
      } finally {
        if (!silent) {
          setBusyTask(null);
        }
      }
    },
    [bridge, host]
  );

  // Automatic non-blocking initial telemetry poll on mount
  useEffect(() => {
    if (testScene || noInitialPoll) return;
    void pollTelemetry(false);
  }, [testScene, noInitialPoll, pollTelemetry]);

  // Live RF Stream auto-polling every 3.5s when on Tab 2 ('live')
  useEffect(() => {
    if (testScene || activeTab.id !== 'live' || !liveStreaming) return;
    if (sampleCount === 0 && !bridge.isBusy) {
      void pollTelemetry(false);
    }
    const interval = setInterval(() => {
      if (!bridge.isBusy && !modal) {
        void pollTelemetry(true);
      }
    }, 3500);
    return () => clearInterval(interval);
  }, [testScene, activeTab.id, liveStreaming, modal, bridge, pollTelemetry, sampleCount]);

  const executeSingleCommand = useCallback(
    async (argv: string[], label?: string) => {
      setBusyTask({
        label: label || `Executing tplink-cli ${argv.join(' ')} on ${host}…`,
        startedAt: Date.now(),
      });
      try {
        const res = await bridge.runCommand(argv, mono);
        setOutputTitle(res.command);
        setOutputLines((res.output || '(Command completed with no output)').split('\n'));
        setOutputScroll(0);
        setLastRunCommand(argv);
        setViewMode('output');
        setLastSummary(`Completed ${res.command} in ${(res.elapsed_ms / 1000).toFixed(2)}s`);
      } catch (err: any) {
        setOutputTitle(`tplink-cli ${argv.join(' ')}`);
        setOutputLines([`✖ Error: ${err?.message || String(err)}`]);
        setOutputScroll(0);
        setViewMode('output');
      } finally {
        setBusyTask(null);
      }
    },
    [bridge, host, mono]
  );

  const executeBatchQueue = useCallback(async () => {
    if (checkedSet.length === 0) return;
    const cmds = checkedSet.map((c) => [c]);
    setBusyTask({
      label: `Running batch queue (${cmds.length} commands: ${checkedSet.join(', ')})…`,
      startedAt: Date.now(),
    });
    try {
      const res = await bridge.runBatch(cmds, mono);
      setOutputTitle(`BATCH EXECUTION (${res.count} COMMANDS)`);
      setOutputLines((res.output || 'Completed.').split('\n'));
      setOutputScroll(0);
      setLastRunCommand(null);
      setViewMode('output');
      setLastSummary(`Batch of ${res.count} commands completed in ${(res.elapsed_ms / 1000).toFixed(2)}s`);
    } catch (err: any) {
      setOutputTitle('BATCH EXECUTION ERROR');
      setOutputLines([`✖ ${err?.message || String(err)}`]);
      setViewMode('output');
    } finally {
      setBusyTask(null);
    }
  }, [bridge, checkedSet, mono]);

  const openSwitchboardWizard = useCallback(async () => {
    setBusyTask({
      label: `Reading live router switchboard states from ${host}…`,
      startedAt: Date.now(),
    });
    try {
      const res = await bridge.getToggles();
      const st = res.states;
      initialSwitchesRef.current = { ...st };
      setModal({
        kind: 'toggles',
        actionId: 'toggles',
        title: 'QUICK FEATURE SWITCHBOARD (LIVE ROUTER TOGGLES)',
        subtitle: 'Flip hardware features with Spacebar [● ON / ○ OFF], then press Enter:',
        cursor: 0,
        options: [
          { value: 'ipv6', label: 'IPv6 WAN Stack', hint: 'Dual-stack IPv6 bearer & SLAAC', checked: st.ipv6 },
          { value: 'wifi_2g', label: '2.4GHz Wi-Fi Radio', hint: 'Primary 2.4GHz wireless coverage', checked: st.wifi_2g },
          { value: 'wifi_5g', label: '5GHz Wi-Fi Radio', hint: 'High-speed 5GHz AC wireless', checked: st.wifi_5g },
          { value: 'guest_wifi', label: 'Guest Wi-Fi Network', hint: 'Isolated visitor wireless SSID', checked: st.guest_wifi },
          { value: 'upnp', label: 'UPnP Port Mapping', hint: 'Automatic NAT traversal leases', checked: st.upnp },
          { value: 'led_night', label: 'LED Night Mode', hint: 'Auto-dim front LEDs (22:00-07:00)', checked: st.led_night },
        ],
      });
    } catch (err: any) {
      setLastSummary(`Switchboard read failed: ${err?.message || err}`);
    } finally {
      setBusyTask(null);
    }
  }, [bridge, host]);

  const confirmModal = useCallback(
    async (m: ModalConfig) => {
      setModal(null);

      if (m.kind === 'toggles') {
        const updated: SwitchStates = { ...initialSwitchesRef.current };
        for (const opt of m.options) {
          (updated as any)[opt.value] = Boolean(opt.checked);
        }
        setBusyTask({
          label: 'Applying modified Feature Switchboard settings to router…',
          startedAt: Date.now(),
        });
        try {
          const res = await bridge.applyToggles(initialSwitchesRef.current, updated, mono);
          setOutputTitle('QUICK FEATURE SWITCHBOARD');
          setOutputLines((res.output || 'Done.').split('\n'));
          setOutputScroll(0);
          setViewMode('output');
          setLastSummary(`Applied ${res.changed} hardware switch change(s)`);
        } finally {
          setBusyTask(null);
        }
        return;
      }

      if (m.kind === 'input' && m.actionId === 'ussd') {
        const code = (m.textValue || '').trim() || '*344#';
        await executeSingleCommand(['ussd', code], `Transmitting cellular USSD session '${code}'…`);
        return;
      }

      if (m.kind === 'multi' && m.actionId === 'calibrate') {
        const chosen = m.options.filter((o) => o.checked).map((o) => o.value);
        const bandsArg = chosen.length > 0 ? chosen.join(',') : '8,3,auto';
        await executeSingleCommand(
          ['calibrate', '--no-web', '--bands', bandsArg, '--dry-run'],
          `Sweeping candidate LTE bands (${bandsArg})…`
        );
        return;
      }

      const sel = m.options[m.cursor]?.value;
      if (!sel) return;

      switch (m.actionId) {
        case 'band':
          if (sel === '__view__') {
            await executeSingleCommand(['band']);
          } else {
            await executeSingleCommand(['band', sel], `Retuning LTE cellular baseband to '${sel}'…`);
            void pollTelemetry(true);
          }
          break;
        case 'ipv6':
          await executeSingleCommand(sel === '__view__' ? ['ipv6'] : ['ipv6', sel]);
          break;
        case 'upnp':
          await executeSingleCommand(sel === '__view__' ? ['upnp'] : ['upnp', sel]);
          break;
        case 'wifi':
          if (sel === '__view__') await executeSingleCommand(['wifi']);
          else if (sel === '2.4_on') await executeSingleCommand(['wifi', '--band', '2.4GHz', '--toggle', 'on']);
          else if (sel === '5_on') await executeSingleCommand(['wifi', '--band', '5GHz', '--toggle', 'on']);
          else if (sel === '5_off') await executeSingleCommand(['wifi', '--band', '5GHz', '--toggle', 'off']);
          break;
        case 'leds':
          await executeSingleCommand(
            sel === '__view__' ? ['leds'] : ['leds', '--night-mode', sel, '--start', '22:00', '--end', '07:00']
          );
          break;
        case 'dns':
          if (sel === '__view__') {
            await executeSingleCommand(['dns']);
          } else {
            const [d1, d2] = sel.split(',');
            await executeSingleCommand(['dns', 'set', d1, d2]);
          }
          break;
        case 'sms':
          await executeSingleCommand(['sms', '--folder', sel]);
          break;
        case 'reboot':
          if (sel === 'confirm') {
            await executeSingleCommand(['reboot', '--yes'], 'Sending protected hardware reboot signal…');
          }
          break;
      }
    },
    [bridge, executeSingleCommand, mono, pollTelemetry]
  );

  const activateSpec = useCallback(
    async (spec: CommandSpec) => {
      if (spec.name === 'repl') {
        if (handoffFile) {
          try {
            writeFileSync(handoffFile, 'repl', 'utf-8');
          } catch {
            // ignore
          }
        }
        bridge.shutdown();
        exit();
        return;
      }

      if (spec.interactiveMode === 'toggles') {
        await openSwitchboardWizard();
        return;
      }

      if (spec.interactiveMode) {
        const nextModal = buildInteractiveModal(spec.interactiveMode);
        if (nextModal) {
          setModal(nextModal);
          return;
        }
      }

      await executeSingleCommand([spec.name]);
    },
    [bridge, executeSingleCommand, exit, handoffFile, openSwitchboardWizard]
  );

  const maxOutputViewportLines = Math.max(6, dims.rows - 15);

  useInput(
    (input, key) => {
      if (key.ctrl && input === 'c') {
        bridge.shutdown();
        exit();
        return;
      }

      // 1. Active Modal Input Handling
      if (modal) {
        if (key.escape) {
          setModal(null);
          return;
        }
        if (modal.kind === 'input') {
          if (key.return) {
            if (!busyTask) void confirmModal(modal);
          } else if (key.backspace || key.delete) {
            setModal({ ...modal, textValue: (modal.textValue || '').slice(0, -1) });
          } else if (input && !key.ctrl && !key.meta && input.length === 1) {
            setModal({ ...modal, textValue: (modal.textValue || '') + input });
          }
          return;
        }

        if (key.upArrow || input === 'k') {
          setModal({
            ...modal,
            cursor: (modal.cursor - 1 + modal.options.length) % modal.options.length,
          });
        } else if (key.downArrow || input === 'j') {
          setModal({
            ...modal,
            cursor: (modal.cursor + 1) % modal.options.length,
          });
        } else if (input === ' ') {
          if (modal.kind === 'multi' || modal.kind === 'toggles') {
            const nextOpts = modal.options.map((o, idx) =>
              idx === modal.cursor ? { ...o, checked: !o.checked } : o
            );
            setModal({ ...modal, options: nextOpts });
          } else if (!busyTask) {
            void confirmModal(modal);
          }
        } else if (key.return && !busyTask) {
          void confirmModal(modal);
        }
        return;
      }

      // 2. Search Input Mode
      if (searchMode) {
        if (key.escape) {
          setSearchMode(false);
          setSearchQuery('');
          setCursor(0);
        } else if (key.return) {
          setSearchMode(false);
        } else if (key.upArrow) {
          if (items.length > 0) setCursor((c) => (c - 1 + items.length) % items.length);
        } else if (key.downArrow) {
          if (items.length > 0) setCursor((c) => (c + 1) % items.length);
        } else if (key.backspace || key.delete) {
          setSearchQuery((q) => q.slice(0, -1));
          setCursor(0);
        } else if (input && !key.ctrl && !key.meta) {
          setSearchQuery((q) => q + input);
          setCursor(0);
        }
        return;
      }

      // 3. Output Viewport Mode
      if (viewMode === 'output') {
        const maxScroll = Math.max(0, outputLines.length - maxOutputViewportLines);
        if (key.escape || key.backspace || key.delete || input === 'b') {
          setViewMode('workspace');
        } else if (input === 'q') {
          bridge.shutdown();
          exit();
        } else if (key.return) {
          if (onPrintOnExit) {
            onPrintOnExit(outputLines.join('\n'));
          }
          bridge.shutdown();
          exit();
        } else if (key.upArrow || input === 'k') {
          setOutputScroll((s) => Math.max(0, s - 1));
        } else if (key.downArrow || input === 'j') {
          setOutputScroll((s) => Math.min(maxScroll, s + 1));
        } else if (key.pageUp) {
          setOutputScroll((s) => Math.max(0, s - 10));
        } else if (key.pageDown || input === ' ') {
          setOutputScroll((s) => Math.min(maxScroll, s + 10));
        } else if (input === 'm') {
          setMono((m) => !m);
        } else if (input === 'a') {
          setAnimated((a) => !a);
        } else if (input === 'r' && lastRunCommand && !busyTask) {
          void executeSingleCommand(lastRunCommand);
        }
        return;
      }

      // 4. Main Workspace & Live RF Monitor Navigation (always responsive even during background telemetry sync!)
      if (input === 'q' || (key.escape && searchQuery.length === 0)) {
        bridge.shutdown();
        exit();
        return;
      }
      if (key.escape && searchQuery.length > 0) {
        setSearchQuery('');
        setCursor(0);
        return;
      }

      if (input === 'm') {
        setMono((v) => !v);
        return;
      }
      if (input === 'a') {
        setAnimated((v) => !v);
        return;
      }
      if (input === 'l') {
        setTabIdx(1); // Jump straight to Tab 2: Live RF Stream
        return;
      }
      if (input === 'r') {
        if (!busyTask) void pollTelemetry(false);
        return;
      }
      if (input === '/') {
        if (activeTab.id === 'live') {
          setTabIdx(0);
        }
        setSearchMode(true);
        return;
      }
      if (input === 'c') {
        setCheckedSet([]);
        return;
      }

      // Direct Tab Hotkeys 1..7 & Left/Right/Tab
      if (input >= '1' && input <= String(TUI_TABS.length)) {
        setTabIdx(Number(input) - 1);
        setCursor(0);
        return;
      }
      if (key.tab || key.rightArrow) {
        setTabIdx((i) => (i + 1) % TUI_TABS.length);
        setCursor(0);
        return;
      }
      if (key.leftArrow) {
        setTabIdx((i) => (i - 1 + TUI_TABS.length) % TUI_TABS.length);
        setCursor(0);
        return;
      }

      // Live RF Tab specific shortcuts
      if (activeTab.id === 'live') {
        if (input === 'p') {
          setLiveStreaming((s) => !s);
        } else if (input === 'b') {
          setModal(buildInteractiveModal('band_picker'));
        }
        return;
      }

      // List scrolling, Spacebar multi-select, Enter run
      if (key.upArrow || input === 'k') {
        if (items.length > 0) {
          setCursor((c) => (c - 1 + items.length) % items.length);
        }
      } else if (key.downArrow || input === 'j') {
        if (items.length > 0) {
          setCursor((c) => (c + 1) % items.length);
        }
      } else if (input === ' ') {
        const cur = items[cursor];
        if (!cur) return;
        if (!cur.batchable) {
          if (!busyTask) void activateSpec(cur);
          return;
        }
        setCheckedSet((prev) =>
          prev.includes(cur.name) ? prev.filter((x) => x !== cur.name) : [...prev, cur.name]
        );
      } else if (key.return) {
        if (busyTask) return;
        if (checkedSet.length > 0) {
          void executeBatchQueue();
        } else if (items[cursor]) {
          void activateSpec(items[cursor]);
        }
      }
    },
    { isActive: !testScene }
  );

  // Compute visible command slice so list always fits terminal height
  const listViewportRows = Math.max(6, dims.rows - 16);
  const startIdx = Math.max(
    0,
    Math.min(cursor - Math.floor(listViewportRows / 2), Math.max(0, items.length - listViewportRows))
  );
  const visibleItems = items.slice(startIdx, startIdx + listViewportRows);
  const focusedSpec: CommandSpec | undefined = items[cursor];
  const logoVariant = dims.rows >= 26 && dims.cols >= 88 ? 'compact' : 'mini';

  return (
    <Box flexDirection="column" width={dims.cols} paddingX={1}>
      {/* Top Brand Header + Shimmering Half-Block Logo + Claude-Code Activity Bar */}
      <Box
        borderStyle="round"
        borderColor={p.borderActive}
        paddingX={1}
        flexDirection="row"
        gap={2}
      >
        <TPLinkLogo
          variant={logoVariant}
          mono={mono}
          animated={animated}
          tick={tick}
        />

        <Box flexDirection="column" flexGrow={1} flexShrink={1} justifyContent="space-between">
          <Box flexDirection="row" justifyContent="space-between" width="100%">
            <Box flexGrow={1} flexShrink={1} marginRight={1}>
              <Text wrap="truncate-end">
                <Text color={p.brand} bold>
                  tp-link
                </Text>
                <Text color={p.white} bold>
                  {'  '}Router & LTE RF Control
                </Text>
                <Text color={p.muted}>  •  Ink React UI</Text>
              </Text>
            </Box>
            <Box flexShrink={0}>
              <Text color={p.muted}>
                Gateway: <Text color={p.white}>{host}</Text>
              </Text>
            </Box>
          </Box>

          {/* Live Hardware Telemetry Strip */}
          <Box flexDirection="row" width="100%">
            {telemetry?.online ? (
              <Text wrap="truncate-end">
                <Text color={p.success} bold>
                  ● ONLINE
                </Text>
                <Text color={p.white} bold>
                  {'  '}{telemetry.model}
                </Text>
                <Text color={p.muted}>  │  </Text>
                <Text color={p.text}>{telemetry.carrier}</Text>
                <Text color={p.muted}>  │  </Text>
                <Text color={p.brandBright} bold>
                  {telemetry.band}
                </Text>
                <Text color={p.muted}>  │  </Text>
                <Text color={p.brand}>
                  {renderSignalStepBars(telemetry.bars ?? 0)} {telemetry.bars ?? 0}/4
                </Text>
                <Text color={p.muted}>  │  </Text>
                <Text color={p.text}>
                  ↓ {formatThroughput(telemetry.rx_kbps ?? 0)}
                </Text>
                <Text color={p.muted}>  │  WAN {telemetry.wan_ip}</Text>
              </Text>
            ) : (
              <Text color={p.muted} wrap="truncate-end">
                ◌ Gateway {host} • Press [r] to poll live LTE RF & WAN telemetry
              </Text>
            )}
          </Box>

          {/* Claude-Code-Style Thinking & Shimmer Activity Strip */}
          <ActivityBar
            busyTask={busyTask}
            lastSummary={lastSummary}
            tick={tick}
            mono={mono}
            animated={animated}
            queuedCount={checkedSet.length}
          />
        </Box>
      </Box>

      {/* Subsystem Tab Bar + Fuzzy Search Pill */}
      <Box flexDirection="row" justifyContent="space-between" paddingX={1} width="100%">
        <Box flexGrow={1} flexShrink={1} marginRight={1}>
          <Text wrap="truncate-end">
            {TUI_TABS.map((t, idx) => {
              const isActive = idx === tabIdx && !searchQuery;
              return (
                <Text
                  key={t.id}
                  color={isActive ? p.crest : p.muted}
                  backgroundColor={isActive ? (mono ? '#374151' : '#0E7490') : undefined}
                  bold={isActive}
                >
                  {isActive ? ` ${t.shortKey} ${t.icon} ${t.label} ` : ` ${t.shortKey} ${t.label} `}
                </Text>
              );
            })}
          </Text>
        </Box>

        <Box flexShrink={0}>
          {searchMode || searchQuery ? (
            <Text color={p.brand} bold>
              / {searchQuery}
              {searchMode ? '█' : ''} ({items.length})
            </Text>
          ) : (
            <Text color={p.muted}>[/] Search ({COMMAND_SPECS.length})</Text>
          )}
        </Box>
      </Box>

      {/* Main Content Area: Modal OR Output Viewport OR Live RF Monitor OR Split-Pane Workspace */}
      {modal ? (
        <ModalOverlay modal={modal} mono={mono} tick={tick} animated={animated} />
      ) : viewMode === 'output' ? (
        <Box
          borderStyle="round"
          borderColor={p.borderActive}
          paddingX={1}
          flexDirection="column"
          flexGrow={1}
        >
          <Box flexDirection="row" justifyContent="space-between">
            <Text color={p.brand} bold>
              ◆ OUTPUT: {outputTitle}
            </Text>
            <Text color={p.muted}>
              Lines {outputScroll + 1}-
              {Math.min(outputLines.length, outputScroll + maxOutputViewportLines)} of{' '}
              {outputLines.length}
            </Text>
          </Box>
          <Box flexDirection="column" marginTop={0}>
            {outputLines
              .slice(outputScroll, outputScroll + maxOutputViewportLines)
              .map((line, idx) => (
                <Text key={idx}>{line || ' '}</Text>
              ))}
          </Box>
        </Box>
      ) : activeTab.id === 'live' && !searchQuery ? (
        <LiveMonitor
          telemetry={telemetry}
          rxHistory={rxHistory}
          txHistory={txHistory}
          barHistory={barHistory}
          streaming={liveStreaming}
          sampleCount={sampleCount}
          tick={tick}
          mono={mono}
          animated={animated}
          columns={dims.cols}
        />
      ) : (
        <Box flexDirection="row" width="100%" gap={1} flexGrow={1}>
          {/* Left Pane: Navigable Command & Wizard List */}
          <Box
            borderStyle="round"
            borderColor={p.borderActive}
            paddingX={1}
            flexDirection="column"
            width="55%"
          >
            <Box flexDirection="row" justifyContent="space-between">
              <Text color={p.brand} bold>
                ▸ {searchQuery ? 'SEARCH RESULTS' : `${activeTab.label.toUpperCase()} ACTIONS`}
              </Text>
              <Text color={p.muted}>
                {items.length > 0 ? `${cursor + 1}/${items.length}` : '0/0'}
              </Text>
            </Box>

            {visibleItems.length === 0 ? (
              <Text color={p.muted}>No matching commands. Press Esc to clear filter.</Text>
            ) : (
              visibleItems.map((item, idx) => {
                const realIdx = startIdx + idx;
                const focused = realIdx === cursor;
                const isChecked = checkedSet.includes(item.name);
                const ptr = focused ? '❯' : ' ';
                const badge = item.isWizard
                  ? '[✦]'
                  : item.batchable
                  ? isChecked
                    ? '[✔]'
                    : '[ ]'
                  : ' • ';
                const badgeColor = item.isWizard
                  ? p.brandBright
                  : isChecked
                  ? p.success
                  : p.muted;
                const displayName = item.name.replace('wizard:', '★ ').padEnd(15, ' ');

                return (
                  <Text key={item.name} wrap="truncate-end">
                    <Text color={focused ? p.brand : p.muted} bold={focused}>
                      {ptr}{' '}
                    </Text>
                    <Text color={badgeColor} bold={isChecked || Boolean(item.isWizard)}>
                      {badge}{' '}
                    </Text>
                    <Text color={focused ? p.white : p.brand} bold={focused}>
                      {displayName}{' '}
                    </Text>
                    <Text color={focused ? p.text : p.muted}>
                      {item.summary}
                    </Text>
                  </Text>
                );
              })
            )}
          </Box>

          {/* Right Pane: Live Command Inspector & Spacebar Batch Queue */}
          <Box
            borderStyle="round"
            borderColor={p.border}
            paddingX={1}
            flexDirection="column"
            width="45%"
            justifyContent="space-between"
          >
            {focusedSpec ? (
              <Box flexDirection="column">
                <Box flexDirection="row" justifyContent="space-between">
                  <Text color={p.brand} bold>
                    ◆ INSPECTOR: {focusedSpec.name.replace('wizard:', '').toUpperCase()}
                  </Text>
                  <Text color={focusedSpec.interactiveMode ? p.brandBright : p.muted}>
                    {focusedSpec.interactiveMode ? '[Interactive Wizard]' : `[${focusedSpec.category}]`}
                  </Text>
                </Box>

                <Box marginTop={1}>
                  <Text color={p.text}>{focusedSpec.details}</Text>
                </Box>

                <Box flexDirection="column" marginTop={1}>
                  <Text color={p.white} bold>
                    CLI & Interactive Usage:
                  </Text>
                  {focusedSpec.examples.map((ex, i) => (
                    <Text key={i} color={p.brandBright}>
                      {'  '}$ {ex}
                    </Text>
                  ))}
                </Box>
              </Box>
            ) : (
              <Text color={p.muted}>Select an action to inspect.</Text>
            )}

            <Box flexDirection="column" marginTop={1}>
              {checkedSet.length > 0 ? (
                <Box flexDirection="column">
                  <Text color={p.success} bold>
                    ✔ Spacebar Batch Queue ({checkedSet.length}):
                  </Text>
                  <Text color={p.white}>{checkedSet.join(' → ')}</Text>
                  <Text color={p.muted}>Press Enter to execute all • [c] Clear</Text>
                </Box>
              ) : (
                <Text color={p.muted}>
                  Tip: Press [Space] to queue multiple tools or [l] for Live RF Waveforms.
                </Text>
              )}
            </Box>
          </Box>
        </Box>
      )}

      {/* Contextual Keybind Footer */}
      <Box flexDirection="row" justifyContent="space-between" paddingX={1} width="100%">
        {viewMode === 'output' ? (
          <Text color={p.muted} wrap="truncate-end">
            <Text color={p.brand}>↑↓/PgUp/PgDn</Text> Scroll •{' '}
            <Text color={p.brand}>Esc/b</Text> Back •{' '}
            <Text color={p.brand}>r</Text> Re-run •{' '}
            <Text color={p.brand}>Enter</Text> Exit & Print to Shell •{' '}
            <Text color={p.brand}>q</Text> Quit
          </Text>
        ) : (
          <Text color={p.muted} wrap="truncate-end">
            <Text color={p.brand}>↑↓</Text> Move ·{' '}
            <Text color={p.brand}>←→/1-7</Text> Tab ·{' '}
            <Text color={p.brand}>Space</Text> [✔] ·{' '}
            <Text color={p.brand}>Enter</Text> Run ·{' '}
            <Text color={p.brand}>l</Text> Live ·{' '}
            <Text color={p.brand}>/</Text> Find ·{' '}
            <Text color={p.brand}>m</Text> Mono ·{' '}
            <Text color={p.brand}>a</Text> Anim ·{' '}
            <Text color={p.brand}>r</Text> Poll ·{' '}
            <Text color={p.brand}>q</Text> Quit
          </Text>
        )}
      </Box>
    </Box>
  );
};
