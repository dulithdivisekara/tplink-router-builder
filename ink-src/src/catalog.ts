export type InteractiveMode =
  | null
  | 'toggles'
  | 'band_picker'
  | 'band'
  | 'calibrate'
  | 'ipv6'
  | 'upnp'
  | 'wifi'
  | 'leds'
  | 'dns'
  | 'sms'
  | 'ussd'
  | 'reboot';

export interface CommandSpec {
  name: string;
  summary: string;
  category: 'quick' | 'cellular' | 'network' | 'wifi' | 'nat' | 'admin';
  details: string;
  examples: string[];
  batchable: boolean;
  isWizard?: boolean;
  interactiveMode: InteractiveMode;
}

export interface TabSpec {
  id: string;
  shortKey: string;
  label: string;
  icon: string;
}

export const TUI_TABS: TabSpec[] = [
  { id: 'quick', shortKey: '1', label: 'Quick', icon: '★' },
  { id: 'live', shortKey: '2', label: 'Live RF', icon: '◉' },
  { id: 'cellular', shortKey: '3', label: 'Cellular', icon: '▲' },
  { id: 'network', shortKey: '4', label: 'WAN/LAN', icon: '◆' },
  { id: 'wifi', shortKey: '5', label: 'Wi-Fi', icon: '≈' },
  { id: 'nat', shortKey: '6', label: 'NAT/Sys', icon: '⇄' },
  { id: 'admin', shortKey: '7', label: 'Admin', icon: '⚙' },
];

export const COMMAND_SPECS: CommandSpec[] = [
  {
    name: 'wizard:toggles',
    summary: 'Quick Feature Switchboard (Spacebar ON/OFF switches)',
    category: 'quick',
    details:
      'Live hardware switchboard for flipping IPv6 WAN Stack, 2.4GHz Wi-Fi, 5GHz Wi-Fi, Guest Wi-Fi, UPnP, and LED Night Mode with Spacebar and applying in one atomic session.',
    examples: ['Space : Flip [● ON] / [○ OFF]', 'Enter : Commit modified switches to router'],
    batchable: false,
    isWizard: true,
    interactiveMode: 'toggles',
  },
  {
    name: 'wizard:band',
    summary: 'Interactive LTE Band Lock Picker (Band 1/3/8/40/Auto)',
    category: 'quick',
    details:
      'Visual carrier frequency selector for locking the cellular LTE baseband onto Band 8 (900MHz), Band 3 (1800MHz), Band 1 (2100MHz), Band 40 (2300MHz), or Auto.',
    examples: ['tplink-cli band 8', 'tplink-cli band 3', 'tplink-cli band auto'],
    batchable: false,
    isWizard: true,
    interactiveMode: 'band_picker',
  },
  {
    name: 'wizard:calibrate',
    summary: 'Multi-Band RF Calibration Checklist (Spacebar picker)',
    category: 'quick',
    details:
      'Select candidate LTE bands with Spacebar [✔] and run an automated latency, jitter, and RF signal sweep with watchdog rollback protection.',
    examples: ['Space : Toggle candidate bands [✔]', 'Enter : Launch RF calibration sweep'],
    batchable: false,
    isWizard: true,
    interactiveMode: 'calibrate',
  },
  {
    name: 'status',
    summary: 'Complete router telemetry (modem, carrier, RF, WAN IP, usage)',
    category: 'network',
    details:
      'Polls full hardware, firmware, LTE carrier, active band/EARFCN, RSRP/RSRQ/SNR signal ratings, live throughput, and WAN IPv4/IPv6 state.',
    examples: ['tplink-cli status', 'tplink-cli --mono status', 'tplink-cli status --json'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'signal',
    summary: 'Real-time RF signal metrics (RSRP, RSRQ, SNR, step-bars)',
    category: 'cellular',
    details:
      'Instant cellular radio snapshot displaying visual signal step-bars (▂▄▆█), RSRP power (dBm), RSRQ cell load (dB), and SNR clarity.',
    examples: ['tplink-cli signal', 'tplink-cli signal --json'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'band',
    summary: 'View or lock LTE Band (e.g. 3, 8, 40, auto)',
    category: 'cellular',
    details:
      'Inspect active LTE frequency band or lock the cellular modem hardware onto a specific carrier band (Band 3, Band 8, Band 40, or Auto).',
    examples: ['tplink-cli band', 'tplink-cli band 8', 'tplink-cli band auto'],
    batchable: true,
    interactiveMode: 'band',
  },
  {
    name: 'cell-lock',
    summary: 'Lock modem to EARFCN carrier frequency and PCI cell identity',
    category: 'cellular',
    details:
      'Inspect or pin the cellular modem to a specific cell tower sector (EARFCN + Physical Cell ID) to eliminate tower-hopping.',
    examples: [
      'tplink-cli cell-lock',
      'tplink-cli cell-lock --enable --earfcn 3738 --pci 0',
      'tplink-cli cell-lock --disable',
    ],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'calibrate',
    summary: 'Autonomous RF multi-band calibration & live Web UI',
    category: 'cellular',
    details:
      'Benchmarks candidate LTE bands with watchdog safety rollback and recommends the highest-scoring frequency for throughput and latency.',
    examples: ['tplink-cli calibrate --no-web --dry-run', 'tplink-cli calibrate --bands 8,3,auto'],
    batchable: false,
    interactiveMode: 'calibrate',
  },
  {
    name: 'diag',
    summary: 'Run hardware diagnostic test (WAN ping, DNS, default gateway)',
    category: 'cellular',
    details:
      'Triggers the router internal WAN & NCSI internet connectivity self-diagnostic check and reports pass/fail status.',
    examples: ['tplink-cli diag', 'tplink-cli diag --json'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'data-limit',
    summary: 'Inspect or set monthly cellular data allowance quota',
    category: 'cellular',
    details:
      'Displays monthly SIM data cap enforcement, billing cycle reset day, warning threshold, and current period consumption.',
    examples: ['tplink-cli data-limit', 'tplink-cli data-limit --limit 50000 --day 1'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'dns',
    summary: 'Inspect or customize primary & secondary DNS resolvers',
    category: 'network',
    details:
      'View active WAN IPv4/IPv6 DNS servers or switch quickly to Cloudflare (1.1.1.1), Google (8.8.8.8), Quad9 (9.9.9.9), or AdGuard DNS.',
    examples: ['tplink-cli dns', 'tplink-cli dns set 1.1.1.1 1.0.0.1'],
    batchable: true,
    interactiveMode: 'dns',
  },
  {
    name: 'ipv6',
    summary: 'Inspect router IPv6 stack state or toggle on/off',
    category: 'network',
    details:
      'Checks router IPv6 WAN bearer state, SLAAC/address assignment, and toggles IPv6 stack enabled or disabled.',
    examples: ['tplink-cli ipv6', 'tplink-cli ipv6 on', 'tplink-cli ipv6 off'],
    batchable: true,
    interactiveMode: 'ipv6',
  },
  {
    name: 'clients',
    summary: 'List connected LAN & Wi-Fi devices (IP, MAC, hostname)',
    category: 'network',
    details:
      'Enumerates all connected Wi-Fi and Ethernet LAN clients with hostname, assigned IPv4 address, MAC address, and DHCP lease timer.',
    examples: ['tplink-cli clients', 'tplink-cli clients --json'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'reservation',
    summary: 'Manage DHCP static IP address reservations',
    category: 'network',
    details:
      'List, bind, or remove static MAC-to-IPv4 DHCP reservations so servers and local devices always receive fixed LAN addresses.',
    examples: ['tplink-cli reservation list', 'tplink-cli reservation add AA:BB:CC:DD:EE:FF 192.168.1.50'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'profile',
    summary: 'Validate active Wi-Fi profile and gateway safety',
    category: 'network',
    details:
      'Verifies your host machine connected Wi-Fi SSID, default gateway IP, and Network Guard safety match against the target router.',
    examples: ['tplink-cli profile', 'tplink-cli profile check'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'wifi-guard',
    summary: 'Verify and optimize Wi-Fi link stability (no Ethernet needed)',
    category: 'network',
    details:
      'Audits wireless interface power-save and NetworkManager autoconnect priority so LTE band changes never drop local Wi-Fi.',
    examples: ['tplink-cli wifi-guard', 'tplink-cli wifi-guard --optimize'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'wifi',
    summary: 'View or configure 2.4GHz / 5GHz radios and SSIDs',
    category: 'wifi',
    details:
      'Inspects dual-band 2.4GHz and 5GHz wireless radios, SSIDs, channels, and client counts, or toggles radio power state.',
    examples: ['tplink-cli wifi', 'tplink-cli wifi --band 5GHz --toggle on'],
    batchable: true,
    interactiveMode: 'wifi',
  },
  {
    name: 'guest-wifi',
    summary: 'Configure isolated dual-band Guest Wi-Fi and passwords',
    category: 'wifi',
    details:
      'Inspects or configures isolated 2.4GHz/5GHz Guest Wi-Fi networks, LAN isolation security, and WPA2 passphrases.',
    examples: ['tplink-cli guest-wifi', 'tplink-cli guest-wifi --toggle off'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'leds',
    summary: 'Control hardware indicator LEDs and Night Mode schedule',
    category: 'wifi',
    details:
      'Checks front-panel LED state and configures Night Mode quiet hours so status LEDs automatically turn off overnight.',
    examples: ['tplink-cli leds', 'tplink-cli leds --night-mode on --start 22:00 --end 07:00'],
    batchable: true,
    interactiveMode: 'leds',
  },
  {
    name: 'reboot-schedule',
    summary: 'Configure automated periodic reboot timer (daily/weekly)',
    category: 'wifi',
    details:
      'Inspects or schedules unattended periodic router maintenance reboots at a specified 24-hour clock time.',
    examples: ['tplink-cli reboot-schedule', 'tplink-cli reboot-schedule on --time 03:30 --mode daily'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'op-mode',
    summary: 'View router operating mode (3G/4G vs Wireless Router)',
    category: 'wifi',
    details:
      'Displays active router operating mode (3G/4G Cellular Router vs Wireless Router) and 4G WAN backup failover switch.',
    examples: ['tplink-cli op-mode', 'tplink-cli op-mode --json'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'port-forward',
    summary: 'Manage NAT virtual server port forwarding rules',
    category: 'nat',
    details:
      'Lists, creates, or deletes external-to-internal TCP/UDP NAT virtual server port forwarding rules.',
    examples: ['tplink-cli port-forward list', 'tplink-cli port-forward add web 8080 192.168.1.150 80 --proto TCP'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'dmz',
    summary: 'Inspect or configure DMZ host IP forwarding',
    category: 'nat',
    details:
      'Checks DMZ exposed host state or forwards all unmatched incoming WAN traffic to a designated LAN IP.',
    examples: ['tplink-cli dmz', 'tplink-cli dmz off'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'upnp',
    summary: 'Manage Universal Plug and Play (UPnP) service',
    category: 'nat',
    details:
      'Displays UPnP service state and active dynamic port mappings requested by LAN applications, or toggles UPnP on/off.',
    examples: ['tplink-cli upnp', 'tplink-cli upnp on', 'tplink-cli upnp off'],
    batchable: true,
    interactiveMode: 'upnp',
  },
  {
    name: 'ddns',
    summary: 'Inspect Dynamic DNS providers and connection status',
    category: 'nat',
    details:
      'Checks configured Dynamic DNS (TP-Link, No-IP, DynDNS) domain bindings and registration state.',
    examples: ['tplink-cli ddns', 'tplink-cli ddns --json'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'time',
    summary: 'View router clock or trigger network NTP time sync',
    category: 'nat',
    details:
      'Displays router local clock, timezone, DST status, configured NTP servers, or triggers an immediate NTP sync.',
    examples: ['tplink-cli time', 'tplink-cli time --sync'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'fw-check',
    summary: 'Check for official TP-Link online firmware updates',
    category: 'nat',
    details:
      'Queries TP-Link cloud metadata via the router to verify whether a newer official firmware build is available.',
    examples: ['tplink-cli fw-check', 'tplink-cli fw-check --json'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'sms',
    summary: 'Read inbox/sent/drafts, or send SMS text messages',
    category: 'admin',
    details:
      'Reads cellular SIM SMS messages (inbox or sent folder) with unread badges, or sends a new SMS message.',
    examples: ['tplink-cli sms', 'tplink-cli sms --folder sent', "tplink-cli sms send +94771234567 'Hello'"],
    batchable: true,
    interactiveMode: 'sms',
  },
  {
    name: 'ussd',
    summary: 'Execute cellular USSD queries (*344#, *123#, balance)',
    category: 'admin',
    details:
      'Sends live GSM/LTE USSD session codes (e.g., Hutch *344#, Dialog *123#, Mobitel *100#) and displays carrier response.',
    examples: ["tplink-cli ussd '*344#'", "tplink-cli ussd '*123#'"],
    batchable: false,
    interactiveMode: 'ussd',
  },
  {
    name: 'logs',
    summary: 'Read, filter, or clear system and cellular event logs',
    category: 'admin',
    details:
      'Fetches severity-colored router system, DHCP, and 4G LTE event logs with optional module/level filtering.',
    examples: ['tplink-cli logs', 'tplink-cli logs --lines 50 --module 4G'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'config',
    summary: 'Manage saved router credentials and endpoint settings',
    category: 'admin',
    details:
      'Displays encrypted configuration file location, target host, username, stored password status, and expected SSID.',
    examples: ['tplink-cli config show', 'tplink-cli config set-password'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'cookie',
    summary: 'Inspect or update cached browser session cookie',
    category: 'admin',
    details:
      'Shows active masked JSESSIONID browser session token or imports a fresh cookie string.',
    examples: ['tplink-cli cookie', 'tplink-cli cookie <JSESSIONID>'],
    batchable: true,
    interactiveMode: null,
  },
  {
    name: 'repl',
    summary: 'Launch interactive shell with tab auto-completion & history',
    category: 'admin',
    details:
      'Exits full-screen Ink TUI into a persistent single-session readline console (tplink>) holding an authenticated lease.',
    examples: ['tplink-cli repl'],
    batchable: false,
    interactiveMode: null,
  },
  {
    name: 'reboot',
    summary: 'Safely reboot the TP-Link hardware router',
    category: 'admin',
    details:
      'Protected hardware restart with explicit safety confirmation. Temporarily drops Wi-Fi & LTE for ~60-90 seconds.',
    examples: ['tplink-cli reboot', 'tplink-cli reboot --yes'],
    batchable: false,
    interactiveMode: 'reboot',
  },
];

const QUICK_FEATURED = new Set([
  'wizard:toggles',
  'wizard:band',
  'wizard:calibrate',
  'status',
  'signal',
  'band',
  'ipv6',
  'clients',
  'wifi',
  'diag',
  'ussd',
]);

export function getTabItems(tabId: string, searchQuery: string): CommandSpec[] {
  const q = searchQuery.trim().toLowerCase();
  if (q.length > 0) {
    const scored: Array<{ score: number; spec: CommandSpec }> = [];
    for (const spec of COMMAND_SPECS) {
      const name = spec.name.toLowerCase();
      const summary = spec.summary.toLowerCase();
      const details = spec.details.toLowerCase();
      if (name.startsWith(q)) {
        scored.push({ score: 0, spec });
      } else if (name.includes(q)) {
        scored.push({ score: 1, spec });
      } else if (summary.includes(q)) {
        scored.push({ score: 2, spec });
      } else if (details.includes(q) || spec.category.includes(q)) {
        scored.push({ score: 3, spec });
      }
    }
    scored.sort((a, b) => a.score - b.score);
    return scored.map((s) => s.spec);
  }

  if (tabId === 'quick') {
    return COMMAND_SPECS.filter((s) => QUICK_FEATURED.has(s.name));
  }
  if (tabId === 'live') {
    return [];
  }
  return COMMAND_SPECS.filter((s) => s.category === tabId);
}
