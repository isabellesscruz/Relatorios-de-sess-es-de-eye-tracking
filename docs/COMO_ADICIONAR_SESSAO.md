# Como adicionar uma nova sessão de teste

## 1. Coleta no VR (Unity)

Após cada teste no headset, copie do dispositivo para o PC (armazenamento **local**, não vai ao GitHub):

```
EyeTrackingData.csv
session_meta.txt      ← contém buildVersion (ex.: 0.9.16)
diagnostic.txt        ← confirma composeGazeWithCamera, headReference, etc.
csv_status.txt        ← opcional
```

## 2. Nomear a sessão

Use um ID descritivo e único — será o nome da pasta em `output/<session_id>/`.

Exemplos já usados:
- `9.15-teste2-ajustes` — primeira sessão calibrada (baseline)
- `teste-9.12` — teste focal com debug visual
- `sessao-01-9.11-05-07-2026` — piloto com ciclo parcial

**Convenção sugerida a partir da baseline:**

```
<versao_build>-<participante_ou_teste>-<data curta>
```

Ex.: `0.9.16-p02-0707`

## 3. Processar localmente

Rode o pipeline Python na sua máquina e gere `output/<session_id>/`.

## 4. Atualizar o catálogo de evolução

Edite:
- `catalogo_sessoes.csv`
- `docs/evolucao_metricas.md`

## 5. (Opcional) Relatório em Markdown/PDF

Copie ou adapte o template em:

```
output/9.15-teste2-ajustes/relatorio_primeira_sessao_calibrada.md
```

## 6. Commit no Git

```bash
git add output/<session_id>/ catalogo_sessoes.csv docs/
git commit -m "Adiciona sessão <session_id> (build X.Y.Z)"
git push
```

## Checklist de qualidade antes de incluir no repositório

- [ ] Pipeline rodou sem erro (localmente)
- [ ] `tutorial_dwell_pct` > 5% (sessão calibrada esperada)
- [ ] `catalogo_sessoes.csv` atualizado
- [ ] Apenas `output/<session_id>/` adicionado — **sem dados brutos**

## Sessão de referência

Compare sempre com a baseline **`9.15-teste2-ajustes`** (build 0.9.15):

| Métrica baseline | Valor |
|---|---:|
| tutorial_dwell_pct | 46,6% |
| n_rescue_saccades | 63 |
| n_tutorial_fixations | 329 |
| machine_dwell_s | 82,3 s |
| confusion_pct | 11,8% |
