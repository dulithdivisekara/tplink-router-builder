import React from 'react';
import { render } from 'ink';
import { EventEmitter } from 'node:events';
import { App, TestScene } from './App.js';
import { RouterBridgeClient } from './bridgeClient.js';

interface ParsedFlags {
  host: string;
  pythonBin: string;
  bridgeModule: string;
  mono: boolean;
  animated: boolean;
  handoffFile: string;
  testRender: boolean;
  testScene: TestScene;
  tick: number;
  cols: number;
  rows: number;
  noInitialPoll: boolean;
}

function parseCliArgs(argv: string[]): ParsedFlags {
  const out: ParsedFlags = {
    host: 'http://192.168.1.1',
    pythonBin: 'python3',
    bridgeModule: 'tplink_router.cli.bridge',
    mono: Boolean(process.env.NO_COLOR),
    animated: !process.env.NO_COLOR && !process.env.TPLINK_NO_ANIM,
    handoffFile: '',
    testRender: false,
    testScene: 'workspace',
    tick: 0,
    cols: 104,
    rows: 28,
    noInitialPoll: false,
  };

  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--host' && argv[i + 1]) {
      out.host = argv[++i];
    } else if (a === '--python' && argv[i + 1]) {
      out.pythonBin = argv[++i];
    } else if (a === '--bridge-module' && argv[i + 1]) {
      out.bridgeModule = argv[++i];
    } else if (a === '--handoff-file' && argv[i + 1]) {
      out.handoffFile = argv[++i];
    } else if (a === '--mono') {
      out.mono = true;
    } else if (a === '--no-anim') {
      out.animated = false;
    } else if (a === '--no-initial-poll') {
      out.noInitialPoll = true;
    } else if (a === '--test-render') {
      out.testRender = true;
    } else if (a.startsWith('--test-scene=')) {
      out.testScene = a.split('=')[1] as TestScene;
    } else if (a === '--test-scene' && argv[i + 1]) {
      out.testScene = argv[++i] as TestScene;
    } else if (a.startsWith('--tick=')) {
      out.tick = Number(a.split('=')[1]) || 0;
    } else if (a === '--tick' && argv[i + 1]) {
      out.tick = Number(argv[++i]) || 0;
    } else if (a.startsWith('--cols=')) {
      out.cols = Number(a.split('=')[1]) || 104;
    } else if (a.startsWith('--rows=')) {
      out.rows = Number(a.split('=')[1]) || 28;
    }
  }
  return out;
}

async function run(): Promise<void> {
  const flags = parseCliArgs(process.argv.slice(2));

  // Headless snapshot mode for automated CI & visual screenshot / GIF capture
  if (flags.testRender) {
    const bridge = new RouterBridgeClient({
      pythonBin: flags.pythonBin,
      bridgeModule: flags.bridgeModule,
      host: flags.host,
      mock: true,
    });

    let lastFrame = '';
    const fakeOut = Object.assign(new EventEmitter(), {
      columns: flags.cols,
      rows: flags.rows,
      isTTY: true,
      write(chunk: string | Uint8Array) {
        const str = typeof chunk === 'string' ? chunk : Buffer.from(chunk).toString('utf-8');
        if (str.trim().length > 0 && str.includes('╭')) {
          lastFrame = str;
        }
        return true;
      },
    }) as unknown as NodeJS.WriteStream;

    const inst = render(
      <App
        bridge={bridge}
        host={flags.host}
        initialMono={flags.mono}
        initialAnimated={flags.animated}
        initialTick={flags.tick}
        overrideCols={flags.cols}
        overrideRows={flags.rows}
        testScene={flags.testScene}
        noInitialPoll={true}
      />,
      {
        stdout: fakeOut,
        debug: true,
        exitOnCtrlC: false,
        patchConsole: false,
      }
    );

    await new Promise((r) => setTimeout(r, 35));
    inst.unmount();
    bridge.shutdown();
    process.stdout.write(lastFrame + '\n');
    return;
  }

  const bridge = new RouterBridgeClient({
    pythonBin: flags.pythonBin,
    bridgeModule: flags.bridgeModule,
    host: flags.host,
  });

  let printAfterExit = '';

  // Enter alternate screen buffer cleanly
  process.stdout.write('\x1b[?1049h\x1b[2J\x1b[H');

  const cleanupScreen = () => {
    process.stdout.write('\x1b[?25h\x1b[?1049l');
  };

  try {
    const inst = render(
      <App
        bridge={bridge}
        host={flags.host}
        initialMono={flags.mono}
        initialAnimated={flags.animated}
        handoffFile={flags.handoffFile}
        noInitialPoll={flags.noInitialPoll}
        onPrintOnExit={(txt) => {
          printAfterExit = txt;
        }}
      />,
      {
        exitOnCtrlC: true,
      }
    );

    await inst.waitUntilExit();
  } finally {
    bridge.shutdown();
    cleanupScreen();
  }

  if (printAfterExit) {
    process.stdout.write(`\n${printAfterExit}\n\n`);
  }
}

run().catch((err) => {
  process.stdout.write('\x1b[?25h\x1b[?1049l');
  console.error(err);
  process.exit(1);
});
