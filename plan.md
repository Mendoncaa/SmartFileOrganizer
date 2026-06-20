# Smart File Organizer — Roadmap

> Atualizado automaticamente após cada etapa concluída.

## Fase 1: Fundação (Scaffolding + Infraestrutura)

| Etapa | Descrição | Status |
|---|---|---|
| 1.1 | Criar estrutura de pastas + `pyproject.toml` + `.gitignore` + `git init` | ✅ |
| 1.2 | Configurar `ruff` (linting/format) + `pytest` | ✅ |
| 1.3 | Definir modelos Pydantic (`shared/models.py`) | ✅ |
| 1.4 | Implementar loader de configuração + `rules.yaml` exemplo | ✅ |
| 1.5 | Setup de logging estruturado (`structlog`) | ✅ |

## Fase 2: Core — Motor de Monitorização

| Etapa | Descrição | Status |
|---|---|---|
| 2.1 | `watcher.py` — detecção de ficheiros novos via watchdog | ✅ |
| 2.2 | Debounce/estabilização (esperar ficheiro completar download) | ✅ |
| 2.3 | Testes unitários do watcher | ✅ |

## Fase 3: Core — Motor de Regras

| Etapa | Descrição | Status |
|---|---|---|
| 3.1 | `rule_engine.py` — matching por extensão, regex, tamanho | ⬜ |
| 3.2 | Templates dinâmicos no destino (`{year}`, `{month}`, `{ext}`) | ⬜ |
| 3.3 | Testes unitários do rule engine | ⬜ |

## Fase 4: Core — Mover Ficheiros com Segurança

| Etapa | Descrição | Status |
|---|---|---|
| 4.1 | `mover.py` — move atómico + tratamento de conflitos | ⬜ |
| 4.2 | Undo log (registo para reversão) | ⬜ |
| 4.3 | Testes unitários do mover | ⬜ |

## Fase 5: Core — Dispatcher (Orquestração)

| Etapa | Descrição | Status |
|---|---|---|
| 5.1 | `dispatcher.py` — pipeline completo | ⬜ |
| 5.2 | Teste de integração end-to-end | ⬜ |

## Fase 6: Core — IA Local (Ollama)

| Etapa | Descrição | Status |
|---|---|---|
| 6.1 | `content_reader.py` — extração de texto | ⬜ |
| 6.2 | `ai_engine.py` — classificação via Ollama | ⬜ |
| 6.3 | Integrar AI como fallback no dispatcher | ⬜ |
| 6.4 | Testes com mocking do Ollama | ⬜ |

## Fase 7: IPC — Comunicação Core↔UI

| Etapa | Descrição | Status |
|---|---|---|
| 7.1 | `ipc_server.py` — pub/sub de eventos | ⬜ |
| 7.2 | `ipc_client.py` — subscrição + comandos | ⬜ |
| 7.3 | Teste de integração IPC | ⬜ |

## Fase 8: UI — Tray Icon + Dashboard

| Etapa | Descrição | Status |
|---|---|---|
| 8.1 | `tray.py` — ícone + menu | ⬜ |
| 8.2 | `dashboard.py` — logs tempo real | ⬜ |
| 8.3 | `rules_editor.py` — editor visual | ⬜ |

## Fase 9: Serviço do Sistema

| Etapa | Descrição | Status |
|---|---|---|
| 9.1 | `windows_service.py` | ⬜ |
| 9.2 | `unix_daemon.py` + systemd unit | ⬜ |
| 9.3 | Scripts install/uninstall | ⬜ |

## Fase 10: Packaging + Distribuição

| Etapa | Descrição | Status |
|---|---|---|
| 10.1 | PyInstaller (executáveis) | ⬜ |
| 10.2 | README + documentação | ⬜ |
