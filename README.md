# Cocoa Fabric — Relatórios de Sessões de Eye-Tracking

Repositório de **relatórios e evolução das sessões de teste** eye-tracking no ambiente VR **Cocoa Fabric** (Heurística #5 Nielsen — Prevenção de Erros).

Documenta a evolução desde builds piloto (0.9.8) até a **primeira sessão calibrada** (`9.15-teste2-ajustes`, build 0.9.15).

> O pipeline de análise Python roda **localmente** e não é versionado aqui — este repositório contém apenas dados, resultados e documentação.

## Sessão de referência (baseline)

| Campo | Valor |
|---|---|
| **ID** | `9.15-teste2-ajustes` |
| **Build Unity** | 0.9.15 |
| **Data** | 2026-07-06 |
| **Marco** | Primeira captura confiável de tutoriais, máquinas, itens e sacadas de socorro |
| **Relatório** | [`output/9.15-teste2-ajustes/relatorio_primeira_sessao_calibrada.md`](output/9.15-teste2-ajustes/relatorio_primeira_sessao_calibrada.md) |

## Estrutura do repositório

```
├── README.md
├── catalogo_sessoes.csv         ← índice de todas as sessões
├── docs/
│   ├── evolucao_metricas.md     ← comparação entre sessões
│   ├── relatorio_baseline_9.15-teste2-ajustes.md
│   └── COMO_ADICIONAR_SESSAO.md
├── <session_id>/                ← dados brutos por sessão
│   ├── EyeTrackingData.csv
│   ├── session_meta.txt
│   └── diagnostic.txt
└── output/<session_id>/         ← resultados da análise
    ├── summary_session.csv
    ├── tutorial_consultations.csv
    ├── residual_pupil_timeline.png
    └── ...
```

## Evolução das sessões (resumo)

| Fase | Builds | Sessões | Situação |
|---|---|---|---|
| Piloto | 0.9.8 – 0.9.10 | teste1, teste2, piloto | Pipeline inicial; captura instável |
| Colliders | 0.9.11 – 0.9.13 | 9.11, 9.12, 9.13 | Máquinas aparecem; tutoriais ainda raros |
| Unificação | 0.9.14 | 9.14, 9.15 | GazeTarget + itens; ainda ~95% parede/chão |
| **Calibrada** | **0.9.15** | **9.15-teste2-ajustes** | **composeGazeWithCamera; 46% tutorial** |

Ver tabela completa em [`docs/evolucao_metricas.md`](docs/evolucao_metricas.md) e [`catalogo_sessoes.csv`](catalogo_sessoes.csv).

## Adicionar nova sessão

1. Processe localmente com o pipeline Python (fora deste repositório).
2. Copie para cá os dados brutos e os outputs gerados.
3. Atualize `catalogo_sessoes.csv` e `docs/evolucao_metricas.md`.
4. Commit e push.

Detalhes: [`docs/COMO_ADICIONAR_SESSAO.md`](docs/COMO_ADICIONAR_SESSAO.md).

## Principais outputs por sessão

| Arquivo | Conteúdo |
|---|---|
| `summary_session.csv` | Métricas agregadas da sessão |
| `summary_by_activity.csv` | Métricas por etapa (CortarCacau, SecarSemente…) |
| `tutorial_consultations.csv` | Consultas ao tutorial (antes/depois da tarefa) |
| `rescue_saccades.csv` | Sacadas de socorro (busca por ajuda) |
| `fixations.csv` | Fixações I-DT |
| `dwell_by_target.csv` | Tempo por alvo (máquina, item, painel) |
| `eckert_plr_fit.png` | Filtro de luminância (modelo Eckert) |
| `residual_pupil_timeline.png` | Timeline de carga cognitiva |

## Pesquisa

- **Heurística Nielsen #5:** Prevenção de erros — sacadas de socorro e consulta a tutoriais.
- **Modelo Eckert:** Pupila residual como indicador de carga cognitiva.
- **Métricas de confusão:** Entropia de olhar, coeficiente K (Krejtz et al.).

## Licença

Apache-2.0 — ver [`LICENSE`](LICENSE). Uso acadêmico — Mestrado MTI/Lab.
