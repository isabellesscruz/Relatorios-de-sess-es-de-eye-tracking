# Como adicionar uma nova sessão de teste

## 1. Coleta no VR (Unity)

Após cada teste no headset, copie do dispositivo para o PC:

```
EyeTrackingData.csv
session_meta.txt      ← contém buildVersion (ex.: 0.9.16)
diagnostic.txt        ← confirma composeGazeWithCamera, headReference, etc.
csv_status.txt        ← opcional
```

## 2. Nomear a pasta

Use um ID descritivo e único:

```
sessoes/<build>-<descricao>/
```

Exemplos já usados:
- `9.15-teste2-ajustes` — primeira sessão calibrada (baseline)
- `teste-9.12` — teste focal com debug visual
- `sessao-01-9.11-05-07-2026` — piloto com ciclo parcial

**Convenção sugerida a partir da baseline:**

```
<versao_build>-<participante_ou_teste>-<data curta>
```

Ex.: `0.9.16-p02-0707`

## 3. Rodar o pipeline

Na raiz `sessoes/`:

```bash
python process_eyetracking.py <session_id>/EyeTrackingData.csv \
    --config config/default_config.yaml \
    --output output/<session_id>
```

## 4. Atualizar o catálogo de evolução

```bash
python scripts/build_catalog.py
```

Isso regera:
- `catalogo_sessoes.csv`
- `docs/evolucao_metricas.md`

## 5. (Opcional) Relatório em Markdown/PDF

Copie ou adapte o template em:

```
output/9.15-teste2-ajustes/relatorio_primeira_sessao_calibrada.md
```

## 6. Commit no Git

```bash
git add <session_id>/ output/<session_id>/ catalogo_sessoes.csv docs/
git commit -m "Adiciona sessão <session_id> (build X.Y.Z)"
git push
```

## Checklist de qualidade antes de incluir no repositório

- [ ] `session_meta.txt` com `buildVersion` correto
- [ ] `diagnostic.txt` com `composeGazeWithCamera=True` (builds ≥ 0.9.15)
- [ ] Pipeline rodou sem erro
- [ ] `tutorial_dwell_pct` > 5% (sessão calibrada esperada)
- [ ] `catalogo_sessoes.csv` atualizado

## Sessão de referência

Compare sempre com a baseline **`9.15-teste2-ajustes`** (build 0.9.15):

| Métrica baseline | Valor |
|---|---:|
| tutorial_dwell_pct | 46,6% |
| n_rescue_saccades | 63 |
| n_tutorial_fixations | 329 |
| machine_dwell_s | 82,3 s |
| confusion_pct | 11,8% |
