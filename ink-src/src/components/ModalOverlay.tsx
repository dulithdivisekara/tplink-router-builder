import React from 'react';
import { Box, Text } from 'ink';
import { getPalette } from '../theme.js';

export interface ModalOption {
  value: string;
  label: string;
  hint: string;
  checked?: boolean;
}

export interface ModalConfig {
  kind: 'single' | 'multi' | 'toggles' | 'input';
  actionId: string;
  title: string;
  subtitle: string;
  options: ModalOption[];
  cursor: number;
  textValue?: string;
}

export interface ModalOverlayProps {
  modal: ModalConfig;
  mono: boolean;
  tick: number;
  animated: boolean;
}

export const ModalOverlay: React.FC<ModalOverlayProps> = ({
  modal,
  mono,
  tick,
  animated,
}) => {
  const p = getPalette(mono);
  const cursorBlink = !animated || Math.floor(tick / 4) % 2 === 0;

  return (
    <Box
      borderStyle="round"
      borderColor={p.borderActive}
      paddingX={2}
      paddingY={1}
      flexDirection="column"
      width="100%"
    >
      <Box flexDirection="row" justifyContent="space-between" marginBottom={1}>
        <Text color={p.brand} bold>
          ◆ {modal.title}
        </Text>
        <Text color={p.muted}>[Esc] Cancel</Text>
      </Box>

      <Text color={p.muted}>{modal.subtitle}</Text>

      <Box flexDirection="column" marginTop={1}>
        {modal.kind === 'input' ? (
          <Box
            borderStyle="round"
            borderColor={p.brand}
            paddingX={1}
            flexDirection="row"
          >
            <Text color={p.brand} bold>
              USSD Code ❯{' '}
            </Text>
            <Text color={p.white} bold>
              {modal.textValue || ''}
            </Text>
            <Text color={p.brand}>{cursorBlink ? '█' : ' '}</Text>
          </Box>
        ) : (
          modal.options.map((opt, idx) => {
            const focused = idx === modal.cursor;
            const ptr = focused ? '❯' : ' ';

            if (modal.kind === 'toggles') {
              const pill = opt.checked ? '[● ON ]' : '[○ OFF]';
              const pillColor = opt.checked ? p.success : p.muted;
              return (
                <Box key={opt.value} flexDirection="row" justifyContent="space-between">
                  <Box flexDirection="row" gap={1}>
                    <Text color={focused ? p.brand : p.muted} bold={focused}>
                      {ptr}
                    </Text>
                    <Text color={pillColor} bold={Boolean(opt.checked)}>
                      {pill}
                    </Text>
                    <Text color={focused ? p.white : p.text} bold={focused}>
                      {opt.label}
                    </Text>
                  </Box>
                  <Text color={p.muted}>{opt.hint}</Text>
                </Box>
              );
            }

            if (modal.kind === 'multi') {
              const box = opt.checked ? '[✔]' : '[ ]';
              const boxColor = opt.checked ? p.success : p.muted;
              return (
                <Box key={opt.value} flexDirection="row" justifyContent="space-between">
                  <Box flexDirection="row" gap={1}>
                    <Text color={focused ? p.brand : p.muted} bold={focused}>
                      {ptr}
                    </Text>
                    <Text color={boxColor} bold={Boolean(opt.checked)}>
                      {box}
                    </Text>
                    <Text color={focused ? p.white : p.text} bold={focused}>
                      {opt.label}
                    </Text>
                  </Box>
                  <Text color={p.muted}>{opt.hint}</Text>
                </Box>
              );
            }

            // single choice
            const radio = focused ? '(●)' : '( )';
            return (
              <Box key={opt.value} flexDirection="row" justifyContent="space-between">
                <Box flexDirection="row" gap={1}>
                  <Text color={focused ? p.brand : p.muted} bold={focused}>
                    {ptr} {radio}
                  </Text>
                  <Text color={focused ? p.white : p.text} bold={focused}>
                    {opt.label}
                  </Text>
                </Box>
                <Text color={p.muted}>{opt.hint}</Text>
              </Box>
            );
          })
        )}
      </Box>

      <Box marginTop={1} flexDirection="row" justifyContent="space-between">
        <Text color={p.muted}>
          {modal.kind === 'toggles'
            ? '↑/↓ Move • Space Flip [● ON / ○ OFF] • Enter Apply Changes • Esc Cancel'
            : modal.kind === 'multi'
            ? '↑/↓ Move • Space Toggle [✔] • Enter Run Sweep • Esc Cancel'
            : modal.kind === 'input'
            ? 'Type USSD (*344#, *123#) • Enter Send Query • Esc Cancel'
            : '↑/↓ Move • Space / Enter Confirm Selection • Esc Cancel'}
        </Text>
      </Box>
    </Box>
  );
};
