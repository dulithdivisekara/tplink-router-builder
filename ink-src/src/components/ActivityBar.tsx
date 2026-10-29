import React from 'react';
import { Box, Text } from 'ink';
import { getPalette } from '../theme.js';

const STARBURST_FRAMES = ['✢', '✳', '✶', '✻', '✽', '✻', '✶', '✳'];
const BRAILLE_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

export interface BusyTask {
  label: string;
  startedAt: number;
}

export interface ActivityBarProps {
  busyTask: BusyTask | null;
  lastSummary: string;
  tick: number;
  mono: boolean;
  animated: boolean;
  queuedCount: number;
}

interface ShimmerChunk {
  text: string;
  color: string;
  bold: boolean;
}

function buildShimmerChunks(text: string, tick: number, mono: boolean, animated: boolean): ShimmerChunk[] {
  const p = getPalette(mono);
  if (!animated || !text) {
    return [{ text, color: p.brandBright, bold: true }];
  }

  const period = Math.max(14, text.length + 10);
  const crest = (tick * 2) % period - 4;
  const chunks: ShimmerChunk[] = [];

  for (let i = 0; i < text.length; i++) {
    const dist = Math.abs(i - crest);
    let color = p.text;
    let bold = false;
    if (dist === 0) {
      color = p.crest;
      bold = true;
    } else if (dist === 1) {
      color = p.brandBright;
      bold = true;
    } else if (dist <= 3) {
      color = p.brand;
      bold = false;
    }

    const prev = chunks[chunks.length - 1];
    if (prev && prev.color === color && prev.bold === bold) {
      prev.text += text[i];
    } else {
      chunks.push({ text: text[i], color, bold });
    }
  }
  return chunks;
}

export const ActivityBar: React.FC<ActivityBarProps> = ({
  busyTask,
  lastSummary,
  tick,
  mono,
  animated,
  queuedCount,
}) => {
  const p = getPalette(mono);

  if (busyTask) {
    const star = animated ? STARBURST_FRAMES[tick % STARBURST_FRAMES.length] : '✶';
    const braille = animated ? BRAILLE_FRAMES[tick % BRAILLE_FRAMES.length] : '…';
    const elapsedSec = Math.max(0, (Date.now() - busyTask.startedAt) / 1000).toFixed(1);
    const chunks = buildShimmerChunks(busyTask.label, tick, mono, animated);

    return (
      <Box flexDirection="row" justifyContent="space-between" width="100%">
        <Box flexGrow={1} flexShrink={1} marginRight={1}>
          <Text wrap="truncate-end">
            <Text color={p.brand} bold>
              {star}{' '}
            </Text>
            {chunks.map((c, idx) => (
              <Text key={idx} color={c.color} bold={c.bold}>
                {c.text}
              </Text>
            ))}
            <Text color={p.muted}>
              {'  '}
              {braille} {elapsedSec}s
            </Text>
          </Text>
        </Box>
        <Box flexShrink={0}>
          <Text color={p.warning}>[RSA-1024 Session]</Text>
        </Box>
      </Box>
    );
  }

  return (
    <Box flexDirection="row" justifyContent="space-between" width="100%">
      <Box flexGrow={1} flexShrink={1} marginRight={1}>
        <Text wrap="truncate-end">
          <Text color={p.success} bold>
            ✓{' '}
          </Text>
          <Text color={p.muted}>{lastSummary}</Text>
        </Text>
      </Box>
      <Box flexShrink={0}>
        <Text>
          {queuedCount > 0 ? (
            <Text color={p.brand} bold>
              [✔ {queuedCount} QUEUED]{' '}
            </Text>
          ) : null}
          <Text color={animated ? p.brand : p.muted}>
            [{animated ? '✦ MOTION' : '⏸ PAUSED'}:a]{' '}
          </Text>
          <Text color={mono ? p.white : p.brand} bold>
            [{mono ? 'MONO B&W' : 'CYAN'}:m]
          </Text>
        </Text>
      </Box>
    </Box>
  );
};
