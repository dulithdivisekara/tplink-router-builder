#!/usr/bin/env bash
# Universal Installer for tplink-cli
# Designed by Dulith Divisekara (SLIIT Malabe)
set -e

INSTALL_DIR="${HOME}/.local/bin"
REPO_URL="https://github.com/dulithdivisekara/tplink-cli.git"
CLONE_DIR="${HOME}/.tplink-cli"

echo "=================================================="
echo "  Installing TP-Link Router CLI (tplink-cli)"
echo "  Author: Dulith Divisekara (SLIIT Malabe)"
echo "=================================================="

mkdir -p "${INSTALL_DIR}"

if command -v git >/dev/null 2>&1; then
  if [ -d "${CLONE_DIR}" ]; then
    echo "Updating existing installation in ${CLONE_DIR}..."
    cd "${CLONE_DIR}" && git pull --quiet
  else
    echo "Cloning tplink-cli repository..."
    git clone --quiet "${REPO_URL}" "${CLONE_DIR}"
  fi
else
  echo "Error: git is required to install tplink-cli."
  exit 1
fi

# Create launcher script in ~/.local/bin
cat << 'EOF' > "${INSTALL_DIR}/tplink-cli"
#!/usr/bin/env bash
PYTHON_BIN="$(command -v python3 || command -v python)"
if [ -z "$PYTHON_BIN" ]; then
  echo "Error: Python 3 is required to run tplink-cli."
  exit 1
fi
export PYTHONPATH="${HOME}/.tplink-cli:${PYTHONPATH}"
exec "$PYTHON_BIN" -m tplink_cli.cli.main "$@"
EOF

chmod +x "${INSTALL_DIR}/tplink-cli"

echo "=================================================="
echo "  [✓] Successfully installed tplink-cli!"
echo "  Binary location: ${INSTALL_DIR}/tplink-cli"
echo "  Run: tplink-cli status"
echo "=================================================="
