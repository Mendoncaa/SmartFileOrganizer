# Smart File Organizer — Plano de Implementação

Ferramenta cross-platform (Windows/macOS/Linux) que monitoriza pastas em tempo real e organiza ficheiros automaticamente usando regras YAML + IA local (Ollama). Arquitetura desacoplada: serviço de sistema (backend) + tray icon com painel PyQt6 (frontend), comunicação via ZeroMQ IPC.

---

## 1. Tech Stack

| Componente | Tecnologia | Justificação |
|---|---|---|
| Linguagem | **Python 3.12+** | Ecossistema rico, cross-platform, Pydantic nativo |
| File Monitoring | **watchdog** | Maduro, cross-platform, event-driven |
| Validação/Config | **Pydantic v2** + **PyYAML** | Schema-driven, validação estrita |
| IA Local | **Ollama** (API HTTP local) | Privado, gratuito, modelos leves (phi3/llama3) |
| IPC Core↔UI | **ZeroMQ** (`pyzmq`) | Rápido, pub/sub + req/rep, sem overhead HTTP |
| UI/Tray | **PyQt6** | Nativo, cross-platform, rico |
| Serviço Windows | `pywin32` | Windows Service nativo |
| Daemon Unix | `python-daemon` + systemd | Standard Linux/macOS |
| Logging | **structlog** | JSON structured, rotação |
| Testes | **pytest** | Standard, fixtures, mocking |
| Packaging | **PyInstaller** | Executável standalone |
| Lint/Format | **ruff** | Ultra-rápido, all-in-one |

**Análise inteligente sem gastar recursos:** O motor de regras determinísticas (extensão, regex, tamanho) corre primeiro em ~0ms. Ollama só é invocado como fallback quando nenhuma regra faz match — evita uso constante de GPU/CPU.

---

## 2. Arquitetura de Pastas

```
smart-file-organizer/
├── src/
│   ├── core/                    # Backend (Serviço/Daemon)
│   │   ├── __init__.py
│   │   ├── main.py              # Entry point do serviço
│   │   ├── watcher.py           # Monitor de ficheiros (watchdog)
│   │   ├── dispatcher.py        # Orquestra: evento → análise → mover
│   │   ├── analyzer/
│   │   │   ├── __init__.py
│   │   │   ├── rule_engine.py   # Regras determinísticas
│   │   │   ├── ai_engine.py     # Classificação Ollama (fallback)
│   │   │   └── content_reader.py # Extrai metadados (PDF, OCR)
│   │   ├── mover.py             # Move atómico + undo log
│   │   ├── ipc_server.py        # Servidor ZeroMQ
│   │   └── service/
│   │       ├── __init__.py
│   │       ├── windows_service.py
│   │       └── unix_daemon.py
│   ├── ui/                      # Frontend (Tray + Painel)
│   │   ├── __init__.py
│   │   ├── main.py              # Entry point da UI
│   │   ├── tray.py              # System tray icon
│   │   ├── dashboard.py         # Logs em tempo real + stats
│   │   ├── rules_editor.py      # Editor visual de regras
│   │   └── ipc_client.py        # Cliente ZeroMQ
│   └── shared/                  # Código partilhado
│       ├── __init__.py
│       ├── models.py            # Modelos Pydantic (Rule, FileEvent, Config)
│       ├── config.py            # Loader + validator de configuração
│       └── constants.py         # Paths, portas, enums
├── config/
│   ├── rules.yaml               # Regras de organização
│   └── settings.yaml            # Configurações gerais
├── tests/
│   ├── unit/
│   │   ├── test_rule_engine.py
│   │   ├── test_watcher.py
│   │   ├── test_mover.py
│   │   └── test_models.py
│   ├── integration/
│   │   ├── test_dispatcher.py
│   │   └── test_ipc.py
│   └── conftest.py
├── scripts/
│   ├── install_service.py
│   └── uninstall_service.py
├── docs/
│   └── architecture.md
├── plan.md                      # Roadmap com status
├── pyproject.toml
├── README.md
└── .gitignore
```

---

## 3. Roadmap — Micro-Etapas

### Fase 1: Fundação (Scaffolding + Infraestrutura)

| Etapa | Descrição | Depende de | Status |
|---|---|---|---|
| 1.1 | Criar estrutura de pastas + `pyproject.toml` + `.gitignore` + `git init` | — | ⬜ |
| 1.2 | Configurar `ruff` (linting/format) + `pytest` | 1.1 | ⬜ |
| 1.3 | Definir modelos Pydantic (`shared/models.py`) — Rule, FileEvent, Config, Settings | 1.1 | ⬜ |
| 1.4 | Implementar loader de configuração (`shared/config.py`) + `rules.yaml` exemplo | 1.3 | ⬜ |
| 1.5 | Setup de logging estruturado (`structlog`) com rotação | 1.1 | ⬜ |

### Fase 2: Core — Motor de Monitorização

| Etapa | Descrição | Depende de | Status |
|---|---|---|---|
| 2.1 | Implementar `watcher.py` — detecção de ficheiros novos via watchdog | 1.5 | ⬜ |
| 2.2 | Implementar debounce/estabilização (esperar ficheiro completar download) | 2.1 | ⬜ |
| 2.3 | Testes unitários do watcher (mock filesystem events) | 2.2 | ⬜ |

### Fase 3: Core — Motor de Regras

| Etapa | Descrição | Depende de | Status |
|---|---|---|---|
| 3.1 | Implementar `rule_engine.py` — matching por extensão, regex no nome, tamanho | 1.4 | ⬜ |
| 3.2 | Suporte a templates dinâmicos no destino (ex: `{year}`, `{month}`, `{ext}`) | 3.1 | ⬜ |
| 3.3 | Testes unitários do rule engine (>90% coverage nas regras) | 3.2 | ⬜ |

### Fase 4: Core — Mover Ficheiros com Segurança

| Etapa | Descrição | Depende de | Status |
|---|---|---|---|
| 4.1 | Implementar `mover.py` — move atómico, tratamento de conflitos (rename) | 1.3 | ⬜ |
| 4.2 | Implementar undo log (registo de movimentos para reversão) | 4.1 | ⬜ |
| 4.3 | Testes unitários do mover (conflitos, permissões, paths longos) | 4.2 | ⬜ |

### Fase 5: Core — Dispatcher (Orquestração)

| Etapa | Descrição | Depende de | Status |
|---|---|---|---|
| 5.1 | Implementar `dispatcher.py` — pipeline: evento → análise → decisão → mover | 2.3, 3.3, 4.3 | ⬜ |
| 5.2 | Teste de integração end-to-end (ficheiro criado → movido para pasta correta) | 5.1 | ⬜ |

### Fase 6: Core — IA Local (Ollama)

| Etapa | Descrição | Depende de | Status |
|---|---|---|---|
| 6.1 | Implementar `content_reader.py` — extração de texto (PDF, imagem OCR, nome) | 1.1 | ⬜ |
| 6.2 | Implementar `ai_engine.py` — classificação via Ollama (prompt engineering) | 6.1 | ⬜ |
| 6.3 | Integrar AI como fallback no dispatcher (regras primeiro, IA se inconclusivo) | 5.2, 6.2 | ⬜ |
| 6.4 | Testes com mocking do Ollama (respostas simuladas) | 6.3 | ⬜ |

### Fase 7: IPC — Comunicação Core↔UI

| Etapa | Descrição | Depende de | Status |
|---|---|---|---|
| 7.1 | Implementar `ipc_server.py` — publica eventos (ficheiro movido, erro) + aceita comandos | 5.2 | ⬜ |
| 7.2 | Implementar `ipc_client.py` — subscreve eventos + envia comandos (pause, resume, reload) | 7.1 | ⬜ |
| 7.3 | Teste de integração IPC (client↔server round-trip) | 7.2 | ⬜ |

### Fase 8: UI — Tray Icon + Dashboard

| Etapa | Descrição | Depende de | Status |
|---|---|---|---|
| 8.1 | Implementar `tray.py` — ícone com menu (Pause/Resume/Open Dashboard/Quit) | 7.2 | ⬜ |
| 8.2 | Implementar `dashboard.py` — log em tempo real + estatísticas | 8.1 | ⬜ |
| 8.3 | Implementar `rules_editor.py` — editor visual YAML com validação Pydantic | 8.2 | ⬜ |

### Fase 9: Serviço do Sistema

| Etapa | Descrição | Depende de | Status |
|---|---|---|---|
| 9.1 | Implementar `windows_service.py` — registo como Windows Service | 5.2 | ⬜ |
| 9.2 | Implementar `unix_daemon.py` + ficheiro systemd .service | 5.2 | ⬜ |
| 9.3 | Scripts de instalação/desinstalação | 9.1, 9.2 | ⬜ |

### Fase 10: Packaging + Distribuição

| Etapa | Descrição | Depende de | Status |
|---|---|---|---|
| 10.1 | Configurar PyInstaller (build executável para Win/Mac/Linux) | 9.3, 8.3 | ⬜ |
| 10.2 | README final + documentação de uso | 10.1 | ⬜ |

---

## 4. Decisões Arquitecturais

- **IPC via ZeroMQ** (não REST): Mais leve, sem overhead HTTP, bidireccional, pub/sub nativo
- **Ollama como fallback**: Regras determinísticas correm primeiro (~0ms). IA só invocada quando nenhuma regra faz match (evita custo computacional)
- **Move atómico**: `shutil.move` com fallback para copy+delete em cross-device. Undo log em SQLite local
- **Debounce no watcher**: Espera 2s após último evento de escrita antes de processar (evita mover ficheiros incompletos)
- **YAML com schema Pydantic**: O utilizador edita YAML legível; o sistema valida com Pydantic antes de aplicar

---

## 5. Scope

**Incluído (v1):**
- Monitorização em tempo real de N pastas configuráveis
- Regras por extensão, regex, tamanho, data
- Classificação IA local (Ollama) como fallback
- UI com tray icon + dashboard + editor de regras
- Serviço nativo do SO (Windows Service / systemd daemon)
- Undo/histórico de movimentos
- Cross-platform (Windows, macOS, Linux)

**Excluído (v1):**
- Sync cloud (Google Drive, OneDrive)
- Interface web (apenas desktop nativo)
- Múltiplos utilizadores
- Auto-update
