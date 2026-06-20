# Smart File Organizer

Intelligent file organizer that monitors folders in real-time and automatically sorts files using configurable rules + local AI (Ollama) as a fallback.

## Features

- **Real-time monitoring** — Watches folders using native OS events (watchdog)
- **Rule-based sorting** — Match by extension, regex, file size with dynamic destination templates
- **AI fallback** — Uses local Ollama LLM to classify files no rule can match
- **Cross-platform** — Windows Service, systemd daemon, macOS compatible
- **Desktop UI** — System tray icon + dashboard + visual rules editor (PyQt6)
- **Safe operations** — Atomic moves, conflict resolution (rename/overwrite/skip), undo log
- **IPC architecture** — Core (service) and UI (tray) communicate via ZeroMQ

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Core Service (Backend)                 │
│  ┌─────────┐  ┌──────────┐  ┌───────────┐  ┌────────┐ │
│  │ Watcher │→│ Debouncer │→│ Dispatcher │→│  Mover  │ │
│  └─────────┘  └──────────┘  └─────┬─────┘  └────────┘ │
│                                    │                     │
│                          ┌─────────┴─────────┐          │
│                          │   Rule Engine      │          │
│                          │   AI Engine (fallback) │      │
│                          └───────────────────┘          │
│                                    │                     │
│                              IPC Server (ZMQ)            │
└────────────────────────────────────┬────────────────────┘
                                     │
                              IPC Client (ZMQ)
                                     │
┌────────────────────────────────────┴────────────────────┐
│                    UI (Frontend)                          │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────────┐ │
│  │ Tray Icon│  │ Dashboard │  │ Rules Editor (YAML)  │ │
│  └──────────┘  └───────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.12+
- [Ollama](https://ollama.ai) (optional, for AI classification)

### Installation

```bash
git clone https://github.com/Mendoncaa/SmartFileOrganizer.git
cd SmartFileOrganizer
python -m venv .venv
# Windows
.venv\Scripts\Activate.ps1
# Unix
source .venv/bin/activate

pip install -e ".[all]"
```

### Configuration

Edit `config/settings.yaml` to set your watch folders:

```yaml
watch_folders:
  - path: "~/Downloads"
    recursive: false
    enabled: true

debounce_seconds: 2.0
conflict_strategy: "rename"
```

Edit `config/rules.yaml` to define organization rules:

```yaml
rules:
  - name: "Invoices"
    priority: 20
    condition:
      extensions: [pdf]
      name_pattern: "(?i)(invoice|fatura|receipt)"
    destination: "~/Documents/Invoices/{year}/{month}/"

  - name: "Images"
    priority: 5
    condition:
      extensions: [jpg, png, gif, webp]
    destination: "~/Pictures/{year}/{month}/"
```

### Running

**Core service (terminal):**
```bash
python -m src.core.main
```

**UI (tray icon + dashboard):**
```bash
python -m src.ui.main
```

### Install as System Service

**Windows:**
```bash
python scripts/install_service.py
```

**Linux (systemd):**
```bash
python scripts/install_service.py
# Follow the printed instructions
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/
```

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| File Monitoring | watchdog |
| Config/Validation | Pydantic v2 + PyYAML |
| AI (local) | Ollama |
| IPC | ZeroMQ (pyzmq) |
| UI | PyQt6 |
| Logging | structlog |
| Testing | pytest |

## License

MIT
