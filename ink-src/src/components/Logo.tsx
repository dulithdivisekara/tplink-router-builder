import React from 'react';
import { Box, Text } from 'ink';
import { getPalette } from '../theme.js';

const COMPACT_EMBLEM_GRID: string[] = [
  '......CCCCCC....',
  '....CCCCCCCCCC..',
  '...CCCCCCCCCCCC.',
  '...CCCC....CCCC.',
  '...CCCC.....CCCC',
  '...CCCC.....CCCC',
  '...CCCC.....CCCC',
  '............CCCC',
  'CCCCCCC..CCCCCCC',
  'CCCCCCC..CCCCCC.',
  'CCCCCCC..CCCCC..',
  '.CCCCCC..CCC....',
  '...CCCC.........',
  '...CCCC.........',
  '...CCCC.........',
  '....CC..........',
];

const MINI_EMBLEM_GRID: string[] = [
  '....CCCCC...',
  '...CCCCCCC..',
  '..CCC...CCC.',
  '..CCC....CCC',
  '..CCC....CCC',
  '.........CCC',
  'CCCCC.CCCCCC',
  'CCCCC.CCCCC.',
  'CCCCC.CCC...',
  '..CCC.......',
  '..CCC.......',
  '..CCC.......',
];

export interface LogoProps {
  variant?: 'compact' | 'mini';
  mono?: boolean;
  animated?: boolean;
  tick?: number;
}

interface CellSpan {
  text: string;
  fg?: string;
}

function resolveCellColor(
  x: number,
  cellRow: number,
  mono: boolean,
  animated: boolean,
  tick: number
): string {
  const p = getPalette(mono);
  if (!animated) return p.brand;

  const stops = p.shimmerStops;
  const period = 26;
  const raw = Math.floor(x + cellRow * 1.3 - tick * 1.4);
  const mod = ((raw % period) + period) % period;
  if (mod < stops.length) {
    return stops[mod];
  }
  return p.brand;
}

export const TPLinkLogo: React.FC<LogoProps> = ({
  variant = 'compact',
  mono = false,
  animated = true,
  tick = 0,
}) => {
  const grid = variant === 'mini' ? MINI_EMBLEM_GRID : COMPACT_EMBLEM_GRID;
  const rows: CellSpan[][] = [];

  for (let y = 0; y < grid.length; y += 2) {
    const cellRow = Math.floor(y / 2);
    const topRow = grid[y];
    const botRow = grid[y + 1] ?? '.'.repeat(topRow.length);
    const spans: CellSpan[] = [];

    for (let x = 0; x < topRow.length; x++) {
      const hasTop = topRow[x] !== '.';
      const hasBot = botRow[x] !== '.';

      let glyph = ' ';
      let fg: string | undefined;

      if (hasTop || hasBot) {
        fg = resolveCellColor(x, cellRow, mono, animated, tick);
        if (hasTop && hasBot) {
          glyph = '█';
        } else if (hasTop) {
          glyph = '▀';
        } else {
          glyph = '▄';
        }
      }

      const prev = spans[spans.length - 1];
      if (prev && prev.fg === fg) {
        prev.text += glyph;
      } else {
        spans.push({ text: glyph, fg });
      }
    }
    rows.push(spans);
  }

  return (
    <Box flexDirection="column" flexShrink={0}>
      {rows.map((spans, rIdx) => (
        <Text key={rIdx} wrap="truncate">
          {spans.map((sp, sIdx) => (
            <Text key={sIdx} color={sp.fg}>
              {sp.text}
            </Text>
          ))}
        </Text>
      ))}
    </Box>
  );
};
