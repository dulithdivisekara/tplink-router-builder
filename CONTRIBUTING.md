# Contributing to Universal TP-Link MCP

Contributions are welcome! Whether you are adding support for a new router model, improving cellular optimization routines, or enhancing cross-platform compatibility, your help is appreciated.

## Development Workflow

1. Fork the repository on GitHub.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/<your-username>/universal-tplink-mcp.git
   cd universal-tplink-mcp
   ```
3. Set up a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e .
   ```
4. Run the test suite:
   ```bash
   python -m unittest discover tests
   ```
5. Submit a Pull Request describing your changes.

## Model Compatibility Guidelines
- Ensure any new endpoint calls handle authentication session leasing gracefully (always log out to avoid holding the single-admin lock).
- Maintain multi-OS compatibility (Linux, macOS, Windows).
- Use `NetworkGuard` to prevent accidental execution on unintended networks.
