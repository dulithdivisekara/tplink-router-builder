import { ChildProcessWithoutNullStreams, spawn } from 'node:child_process';
import { createInterface, Interface as ReadlineInterface } from 'node:readline';

export interface TelemetryData {
  online: boolean;
  elapsed_ms: number;
  timestamp: number;
  model?: string;
  hw_version?: string;
  fw_version?: string;
  carrier?: string;
  sim_status?: string;
  connected?: boolean;
  band?: string;
  earfcn?: string;
  pci?: string;
  cell_locked?: boolean;
  bars?: number;
  rssi_dbm?: number;
  rssi_rating?: string;
  rsrp_dbm?: number;
  rsrp_rating?: string;
  rsrq_db?: number;
  rsrq_rating?: string;
  snr_db?: number;
  snr_rating?: string;
  rx_kbps?: number;
  tx_kbps?: number;
  total_mb?: number;
  wan_ip?: string;
  gateway?: string;
  dns?: string[];
  ipv6_enabled?: boolean;
  ipv6_status?: string;
  error?: string;
}

export interface SwitchStates {
  ipv6: boolean;
  wifi_2g: boolean;
  wifi_5g: boolean;
  guest_wifi: boolean;
  upnp: boolean;
  led_night: boolean;
}

export interface BridgeClientOptions {
  pythonBin: string;
  bridgeModule: string;
  host: string;
  mock?: boolean;
}

interface PendingReq {
  resolve: (val: any) => void;
  reject: (err: Error) => void;
}

export class RouterBridgeClient {
  private proc: ChildProcessWithoutNullStreams | null = null;
  private rl: ReadlineInterface | null = null;
  private nextId = 1;
  private pending = new Map<number, PendingReq>();
  private opts: BridgeClientOptions;
  private closed = false;

  constructor(opts: BridgeClientOptions) {
    this.opts = opts;
    if (!opts.mock) {
      this.startProcess();
    }
  }

  private startProcess(): void {
    const args = ['-m', this.opts.bridgeModule];
    if (this.opts.host) {
      args.push('--host', this.opts.host);
    }
    const child = spawn(this.opts.pythonBin, args, {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONUNBUFFERED: '1', TPLINK_NO_ANIM: '1' },
    });
    this.proc = child;
    // Drain stderr silently so pipe buffer never fills
    child.stderr.resume();

    this.rl = createInterface({ input: child.stdout });
    this.rl.on('line', (line) => {
      const trimmed = line.trim();
      if (!trimmed) return;
      try {
        const msg = JSON.parse(trimmed);
        const id = msg.id;
        const entry = this.pending.get(id);
        if (entry) {
          this.pending.delete(id);
          if (msg.ok) {
            entry.resolve(msg.result);
          } else {
            entry.reject(new Error(msg.error || 'Bridge error'));
          }
        }
      } catch {
        // Ignore non-JSON lines
      }
    });

    child.on('exit', () => {
      for (const [, entry] of this.pending.entries()) {
        entry.reject(new Error('Router bridge process exited'));
      }
      this.pending.clear();
      this.proc = null;
    });
  }

  public get isBusy(): boolean {
    return this.pending.size > 0;
  }

  public request<T = any>(method: string, params: Record<string, any> = {}): Promise<T> {
    if (this.opts.mock) {
      return this.mockRequest(method, params) as Promise<T>;
    }
    if (this.closed) {
      return Promise.reject(new Error('Bridge client is closed'));
    }
    if (!this.proc) {
      this.startProcess();
    }
    const id = this.nextId++;
    return new Promise<T>((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      try {
        this.proc!.stdin.write(JSON.stringify({ id, method, params }) + '\n');
      } catch (err: any) {
        this.pending.delete(id);
        reject(err instanceof Error ? err : new Error(String(err)));
      }
    });
  }

  public getTelemetry(): Promise<TelemetryData> {
    return this.request<TelemetryData>('telemetry');
  }

  public runCommand(argv: string[], mono: boolean): Promise<{ output: string; command: string; elapsed_ms: number }> {
    return this.request('run_command', { argv, mono });
  }

  public runBatch(commands: string[][], mono: boolean): Promise<{ output: string; count: number; elapsed_ms: number }> {
    return this.request('run_batch', { commands, mono });
  }

  public getToggles(): Promise<{ states: SwitchStates }> {
    return this.request('get_toggles');
  }

  public applyToggles(
    initial: SwitchStates,
    updated: SwitchStates,
    mono: boolean
  ): Promise<{ output: string; changed: number }> {
    return this.request('apply_toggles', { initial, updated, mono });
  }

  public shutdown(): void {
    this.closed = true;
    if (this.proc) {
      try {
        this.proc.stdin.write(JSON.stringify({ id: 999999, method: 'shutdown' }) + '\n');
        this.proc.stdin.end();
      } catch {
        // ignore
      }
      setTimeout(() => {
        if (this.proc) {
          this.proc.kill('SIGTERM');
          this.proc = null;
        }
      }, 150).unref();
    }
    if (this.rl) {
      this.rl.close();
      this.rl = null;
    }
  }

  private async mockRequest(method: string, params: Record<string, any>): Promise<any> {
    if (method === 'telemetry') {
      return {
        online: true,
        elapsed_ms: 420,
        timestamp: Date.now() / 1000,
        model: 'Archer MR200',
        hw_version: 'Archer MR200 v5.3 00000001',
        fw_version: '1.3.0 0.9.1 v0001.0 Build 230816',
        carrier: 'Hutch Internet',
        sim_status: 'Ready',
        connected: true,
        band: 'Band 8 (900 MHz)',
        earfcn: '3738',
        pci: '0',
        cell_locked: false,
        bars: 4,
        rssi_dbm: -63,
        rssi_rating: 'Excellent',
        rsrp_dbm: -84,
        rsrp_rating: 'Excellent',
        rsrq_db: -7,
        rsrq_rating: 'Excellent',
        snr_db: 18.4,
        snr_rating: 'Excellent',
        rx_kbps: 2480,
        tx_kbps: 640,
        total_mb: 1428.5,
        wan_ip: '100.82.14.91',
        gateway: '100.82.14.1',
        dns: ['1.1.1.1', '8.8.8.8'],
        ipv6_enabled: true,
        ipv6_status: 'Enabled',
      } satisfies TelemetryData;
    }
    if (method === 'get_toggles') {
      return {
        states: {
          ipv6: true,
          wifi_2g: true,
          wifi_5g: true,
          guest_wifi: false,
          upnp: true,
          led_night: false,
        } satisfies SwitchStates,
      };
    }
    if (method === 'run_command') {
      const cmd = (params.argv || []).join(' ');
      return {
        command: `tplink-cli ${cmd}`,
        elapsed_ms: 380,
        output: `╭─ ◆ MOCK OUTPUT: ${cmd.toUpperCase()} ─╮\n│ Status: OK (Headless Ink Render Test) │\n╰───────────────────────────────────────╯`,
      };
    }
    if (method === 'run_batch') {
      return {
        count: (params.commands || []).length,
        elapsed_ms: 510,
        output: '▸ [1/2] tplink-cli status\nOK',
      };
    }
    return { output: 'OK', changed: 1 };
  }
}
