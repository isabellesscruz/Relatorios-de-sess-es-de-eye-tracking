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
git remote add origin https://github.com/isabellesscruz/Relatorios-de-sess-es-de-eye-tracking.git
git push -u origin main
```

## 3. Fluxo para cada nova sessão

```powershell
# Processar localmente (fora deste repositório), depois:
git add <session_id>/ output/<session_id>/ catalogo_sessoes.csv docs/evolucao_metricas.md
git commit -m "Adiciona sessão <session_id> (build X.Y.Z)"
git push
```

## 4. O que está versionado

| Incluído | Excluído (.gitignore) |
|---|---|
| CSVs brutos (`EyeTrackingData.csv`) | Pipeline Python (`scripts/`, `cocoa_analysis/`, etc.) |
| Metadados (`session_meta.txt`, `diagnostic.txt`) | `*.parquet` (regenerável) |
| Outputs de análise (`output/<id>/`) | Artefatos soltos na raiz |
| Catálogo e documentação | Projeto Unity (`Library/`, etc.) |

## 5. Baseline de referência

- **Sessão:** `9.15-teste2-ajustes`
- **Build:** 0.9.15
- **Relatório:** [`docs/relatorio_baseline_9.15-teste2-ajustes.md`](relatorio_baseline_9.15-teste2-ajustes.md)
- **Evolução:** [`evolucao_metricas.md`](evolucao_metricas.md)

## 6. GitHub CLI (opcional)

Se instalar o [GitHub CLI](https://cli.github.com/):

```powershell
gh repo create Relatorios-de-sess-es-de-eye-tracking --public --source=. --remote=origin --push
```
