# Publicar no GitHub

Este diretório (`sessoes/`) é o repositório de evolução das sessões de teste eye-tracking do Cocoa Fabric.

## 1. Criar o repositório remoto

No GitHub: **New repository** → nome sugerido: `cocoa-fabric-eyetracking-sessoes` (ou similar).

- Visibilidade: **Private** (dados de participantes) ou **Public** (se anonimizados).
- **Não** marque "Add README" — já existe localmente.

## 2. Inicializar e enviar (primeira vez)

No PowerShell, na pasta `sessoes/`:

```powershell
git init
git add .
git status
git commit -m "Baseline: primeira sessão calibrada (9.15-teste2-ajustes, build 0.9.15)"
git branch -M main
git remote add origin https://github.com/<seu-usuario>/<nome-do-repo>.git
git push -u origin main
```

## 3. Fluxo para cada nova sessão

```powershell
python process_eyetracking.py <session_id>/EyeTrackingData.csv --config config/default_config.yaml --output output/<session_id>
python scripts/build_catalog.py
git add <session_id>/ output/<session_id>/ catalogo_sessoes.csv docs/evolucao_metricas.md
git commit -m "Adiciona sessão <session_id> (build X.Y.Z)"
git push
```

## 4. O que está versionado

| Incluído | Excluído (.gitignore) |
|---|---|
| CSVs brutos (`EyeTrackingData.csv`) | `__pycache__/`, `.venv/` |
| Metadados (`session_meta.txt`, `diagnostic.txt`) | `*.parquet` (regenerável) |
| Outputs de análise (`output/<id>/`) | Artefatos soltos na raiz |
| Scripts Python e config | Projeto Unity (`Library/`, etc.) |

## 5. Baseline de referência

- **Sessão:** `9.15-teste2-ajustes`
- **Build:** 0.9.15
- **Relatório:** [`docs/relatorio_baseline_9.15-teste2-ajustes.md`](relatorio_baseline_9.15-teste2-ajustes.md)
- **Evolução:** [`evolucao_metricas.md`](evolucao_metricas.md)

## 6. GitHub CLI (opcional)

Se instalar o [GitHub CLI](https://cli.github.com/):

```powershell
gh repo create cocoa-fabric-eyetracking-sessoes --private --source=. --remote=origin --push
```
