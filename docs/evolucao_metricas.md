# Evolução das métricas por sessão

**Sessão de referência (baseline calibrada):** `9.15-teste2-ajustes` (build 0.9.15)

Tabela gerada automaticamente por `scripts/build_catalog.py`.

| Sessão | Build | Tutorial % | Fixações tutorial | Sacadas socorro | Máquinas (s) | Confusão % | Análise |
|---|---:|---:|---:|---:|---:|---:|---|
| `sessao-teste1-03-07-2026-isabelle` | 0.9.8 | 0.0 | 0 | 0 | 0.0 | 59.2 | sim |
| `sessao-teste2-isabelle-03-07-2026` | 0.9.9 | 0.0 | 0 | 0 | 0.0 | 71.8 | sim |
| `teste3-03-06-2026-isabelle` | 0.9.10 | 0.0 | 0 | 0 | 0.0 | 72.5 | sim |
| `teste-piloto-user1-03-07-2026` | 0.9.10 | 0.1 | 0 | 0 | 0.0 | 40.3 | sim |
| `sessao-01-9.11-05-07-2026` | 0.9.11 | 0.4 | 0 | 0 | 0.1 | 53.1 | sim |
| `teste-9.12` | 0.9.12 | 1.9 | - | 1 | - | 26.6 | sim |
| `teste-9.13` | 0.9.13 | 0.9 | - | 0 | - | 30.6 | sim |
| `9.14-teste` | 0.9.14 | 4.5 | - | 1 | 0.0 | 65.5 | sim |
| `9.15-teste` | 0.9.14 | 1.4 | 13 | 6 | 5.8 | 57.4 | sim |
| `9.15-teste2-ajustes` **(baseline)** | 0.9.15 | 46.6 | 329 | 63 | 82.3 | 11.8 | sim |

## Como atualizar

1. Adicione a pasta da nova sessão em `sessoes/<nome>/` com `EyeTrackingData.csv` e `session_meta.txt`.
2. Rode o pipeline: `python process_eyetracking.py <nome>/EyeTrackingData.csv --output output/<nome>`.
3. Regere o catálogo: `python scripts/build_catalog.py`.
