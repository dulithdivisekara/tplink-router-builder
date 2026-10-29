#!/usr/bin/env node
import * as esbuild from 'esbuild';
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const outfile = resolve(__dirname, '../tplink_router/cli/ink_ui/tui.mjs');

mkdirSync(dirname(outfile), { recursive: true });

// Stub optional react-devtools-core so Ink runs standalone with zero external node_modules
const stubDevtoolsPlugin = {
  name: 'stub-react-devtools',
  setup(build) {
    build.onResolve({ filter: /^react-devtools-core$/ }, () => ({
      path: 'react-devtools-core',
      namespace: 'stub-devtools',
    }));
    build.onLoad({ filter: /.*/, namespace: 'stub-devtools' }, () => ({
      contents: 'export default { initialize() {}, connectToDevTools() {} };',
      loader: 'js',
    }));
  },
};

await esbuild.build({
  entryPoints: [resolve(__dirname, 'src/index.tsx')],
  outfile,
  bundle: true,
  minify: true,
  platform: 'node',
  format: 'esm',
  target: 'node20',
  jsx: 'automatic',
  plugins: [stubDevtoolsPlugin],
  define: {
    'process.env.DEV': '"false"',
    'process.env.NODE_ENV': '"production"',
  },
  banner: {
    js: [
      '#!/usr/bin/env node',
      'import { createRequire as __tplinkCreateRequire } from "node:module";',
      'const require = __tplinkCreateRequire(import.meta.url);',
    ].join('\n'),
  },
  logLevel: 'info',
});

console.log(`✓ Bundled vadimdemedes/ink React TUI -> ${outfile}`);
