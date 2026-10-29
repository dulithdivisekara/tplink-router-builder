export interface ThemePalette {
  mono: boolean;
  brand: string;
  brandBright: string;
  brandDeep: string;
  crest: string;
  white: string;
  text: string;
  muted: string;
  border: string;
  borderActive: string;
  success: string;
  warning: string;
  danger: string;
  shimmerStops: string[];
}

export const CYAN_PALETTE: ThemePalette = {
  mono: false,
  brand: '#4DCCD5',       // Official TP-Link Brand Cyan
  brandBright: '#67E8F9', // Luminous Cyan
  brandDeep: '#0891B2',   // Deep Teal Cyan
  crest: '#ECFEFF',       // Ice Highlight Crest
  white: '#F8FAFC',
  text: '#CBD5E1',
  muted: '#64748B',
  border: '#1E3A5F',
  borderActive: '#4DCCD5',
  success: '#10B981',
  warning: '#F59E0B',
  danger: '#EF4444',
  shimmerStops: [
    '#0E7490',
    '#22D3EE',
    '#4DCCD5',
    '#4DCCD5',
    '#67E8F9',
    '#A5F3FC',
    '#ECFEFF',
    '#A5F3FC',
    '#67E8F9',
    '#4DCCD5',
  ],
};

export const MONO_PALETTE: ThemePalette = {
  mono: true,
  brand: '#FFFFFF',
  brandBright: '#F3F4F6',
  brandDeep: '#9CA3AF',
  crest: '#FFFFFF',
  white: '#FFFFFF',
  text: '#D1D5DB',
  muted: '#8E8E98',
  border: '#4B5563',
  borderActive: '#FFFFFF',
  success: '#FFFFFF',
  warning: '#D1D5DB',
  danger: '#FFFFFF',
  shimmerStops: [
    '#9CA3AF',
    '#D1D5DB',
    '#E5E7EB',
    '#F3F4F6',
    '#FFFFFF',
    '#FFFFFF',
    '#F3F4F6',
    '#D1D5DB',
  ],
};

export function getPalette(mono: boolean): ThemePalette {
  return mono ? MONO_PALETTE : CYAN_PALETTE;
}

const SPARK_BLOCKS = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█'];

export function renderSparkline(values: number[], width: number, minFloor = 0): string {
  if (width <= 0) return '';
  if (values.length === 0) return '▁'.repeat(width);

  const slice = values.slice(-width);
  const padded =
    slice.length < width
      ? [...Array(width - slice.length).fill(slice[0] ?? 0), ...slice]
      : slice;

  const maxVal = Math.max(minFloor, ...padded, 1);
  const minVal = Math.min(0, ...padded);
  const span = Math.max(1e-6, maxVal - minVal);

  return padded
    .map((v) => {
      const norm = Math.max(0, Math.min(1, (v - minVal) / span));
      const idx = Math.min(SPARK_BLOCKS.length - 1, Math.floor(norm * (SPARK_BLOCKS.length - 1) + 0.25));
      return SPARK_BLOCKS[idx];
    })
    .join('');
}

export function renderSignalStepBars(bars: number): string {
  const clamped = Math.max(0, Math.min(4, Math.round(bars)));
  const glyphs = ['▂', '▄', '▆', '█'];
  return glyphs.map((g, idx) => (idx < clamped ? g : '░')).join('');
}

export function renderGaugeBar(value: number, max: number, width = 16): string {
  const ratio = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
  const filled = Math.round(ratio * width);
  return '━'.repeat(filled) + '─'.repeat(Math.max(0, width - filled));
}

export function formatThroughput(kbps: number): string {
  if (kbps >= 1024) {
    return `${(kbps / 1024).toFixed(2)} Mbps`;
  }
  return `${Math.round(kbps)} Kbps`;
}
