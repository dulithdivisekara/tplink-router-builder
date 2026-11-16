# Contributing to TP-Link Router Suite

Thank you for your interest in contributing to the TP-Link Router Suite. This document details local environment setup, architectural constraints, test execution, and pull request standards.

## Code of Conduct

All contributors and maintainers are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Please report unacceptable behavior to `dulithdivisekara@gmail.com`.

## Architectural Guidelines

When submitting code changes, observe the following four core invariants:

1. **Atomic Session Leasing (`SafeSession`)**:
   Never leave an unclosed administrative session against a router. All hardware communication must use the `SafeSession` context manager to guarantee logout on completion or error.
2. **Multi-Environment Network Guard**:
   Network mutations must integrate with `NetworkGuard` to prevent executing operations against university or public Wi-Fi networks.
3. **Dual Interface Compatibility**:
   Core router features in `tplink_router/core/` and `tplink_router/clients/` must be exposed through both the CLI suite (`tplink_router/cli/`) and the Model Context Protocol server (`tplink_router/mcp/`).
4. **Destructive Operation Gates**:
   Any action that severs or interrupts connectivity (reboot, cell lock, band change) must enforce an explicit boolean `confirm=True` parameter.

## Development Workflow

### 1. Clone and Virtual Environment Setup
```bash
git clone https://github.com/dulithdivisekara/tplink-router-suite.git
cd tplink-router-suite

python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

### 2. Node.js & React Ink TUI Setup (Optional)
If modifying the animated terminal interface in `ink-src/`:
```bash
cd ink-src
npm install
npm run build
cd ..
```

### 3. Web Showcase & Catalog Re-generation
If adding or amending CLI subcommands or MCP tools:
```bash
# Re-extract schemas from Python signatures into web/
python3 scripts/extract-catalog.py

# Validate schemas and build web pre-renders
python3 web/scripts/build.py
```

### 4. Running the Automated Test Suite
All contributions must pass the complete unit test suite across Python 3.10 through 3.14:
```bash
python3 -m unittest discover tests
```

## Branching & Commit Conventions

- Use feature branches branched from `main`: `git checkout -b feat/your-feature-name` or `fix/issue-description`.
- Use conventional commit messages:
  - `feat(cli): add port forwarding status subcommand`
  - `fix(session): resolve lockfile timeout on POSIX systems`
  - `docs(readme): update MCP tools catalog reference`

## Pull Request Submission

1. Ensure all 90+ tests pass locally before pushing.
2. Verify that any new markdown documentation is free of decorative emojis and adheres to the `minimal-readme` standard.
3. Fill out the pull request template completely, documenting hardware models tested or simulation mocks used.
