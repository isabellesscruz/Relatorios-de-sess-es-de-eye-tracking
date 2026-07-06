# Cocoa Fabric — Eye-Tracking (Sessões de Teste)

Pipeline de análise eye-tracking para o ambiente VR **Cocoa Fabric** (Heurística #5 Nielsen — Prevenção de Erros).

Este repositório documenta a **evolução das sessões de teste**, desde builds piloto (0.9.8) até a **primeira sessão calibrada** (`9.15-teste2-ajustes`, build 0.9.15).

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
sessoes/
├── README.md                    ← este arquivo
├── catalogo_sessoes.csv         ← índice de todas as sessões (auto-gerado)
├── process_eyetracking.py       ← pipeline principal
├── requirements.txt
├── config/
│   └── default_config.yaml
├── cocoa_analysis/              ← módulos Python (Eckert, métricas, plots)
├── scripts/
│   └── build_catalog.py         ← regera catálogo e tabela de evolução
├── docs/
│   ├── evolucao_metricas.md     ← comparação entre sessões (auto-gerado)
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

## Instalação

```bash
cd sessoes
pip install -r requirements.txt
```

## Processar uma sessão

```bash
python process_eyetracking.py 9.15-teste2-ajustes/EyeTrackingData.csv \
    --config config/default_config.yaml \
    --output output/9.15-teste2-ajustes
```

## Adicionar nova sessão

1. Copie do headset a pasta com `EyeTrackingData.csv`, `session_meta.txt` e `diagnostic.txt`.
2. Crie `sessoes/<novo_id>/` com esses arquivos.
3. Rode o pipeline (comando acima, trocando o ID).
4. Atualize o catálogo: `python scripts/build_catalog.py`.
5. Commit com mensagem descritiva (build, participante, o que mudou).

Detalhes: [`docs/COMO_ADICIONAR_SESSAO.md`](docs/COMO_ADICIONAR_SESSAO.md).

## Publicar no GitHub

Instruções passo a passo: [`docs/SETUP_GITHUB.md`](docs/SETUP_GITHUB.md).

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

Uso acadêmico — Mestrado MTI/Lab.
