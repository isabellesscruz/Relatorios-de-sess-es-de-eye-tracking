#!/usr/bin/env python3
"""
Gera catalogo_sessoes.csv e docs/evolucao_metricas.md a partir das pastas de sessao.

Uso (na raiz do repositorio):
    python scripts/build_catalog.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASELINE_SESSION = "9.15-teste2-ajustes"

METRIC_COLS = [
    "session_duration_s",
    "tutorial_dwell_pct",
    "n_tutorial_fixations",
    "mean_tutorial_fixation_s",
    "n_rescue_saccades",
    "machine_dwell_s",
    "item_dwell_s",
    "confusion_pct",
    "mean_k_coefficient",
    "mean_residual_pupil_mm",
]


def _read_meta(session_dir: Path) -> dict[str, str]:
    meta_path = session_dir / "session_meta.txt"
    if not meta_path.exists():
        return {}
    info: dict[str, str] = {}
    for line in meta_path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            info[key.strip()] = value.strip()
    return info


def _has_raw_data(session_dir: Path) -> bool:
    return (session_dir / "EyeTrackingData.csv").exists()


def collect_sessions() -> pd.DataFrame:
    rows: list[dict] = []
    for session_dir in sorted(ROOT.iterdir()):
        if not session_dir.is_dir():
            continue
        if session_dir.name in {"output", "cocoa_analysis", "config", "scripts", "docs"}:
            continue
        if not _has_raw_data(session_dir):
            continue

        meta = _read_meta(session_dir)
        out_summary = ROOT / "output" / session_dir.name / "summary_session.csv"
        row: dict = {
            "session_id": session_dir.name,
            "build_version": meta.get("buildVersion", ""),
            "start_utc": meta.get("startUtc", ""),
            "scene": meta.get("scene", ""),
            "is_baseline": session_dir.name == BASELINE_SESSION,
            "has_analysis": out_summary.exists(),
            "raw_csv": f"{session_dir.name}/EyeTrackingData.csv",
            "output_dir": f"output/{session_dir.name}",
        }

        if out_summary.exists():
            summary = pd.read_csv(out_summary).iloc[0]
            for col in METRIC_COLS:
                row[col] = summary.get(col, pd.NA)

        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty and "start_utc" in df.columns:
        df = df.sort_values("start_utc").reset_index(drop=True)
    return df


def write_evolution_markdown(df: pd.DataFrame, path: Path) -> None:
    lines = [
        "# Evolução das métricas por sessão",
        "",
        f"**Sessão de referência (baseline calibrada):** `{BASELINE_SESSION}` (build 0.9.15)",
        "",
        "Tabela gerada automaticamente por `scripts/build_catalog.py`.",
        "",
        "| Sessão | Build | Tutorial % | Fixações tutorial | Sacadas socorro | Máquinas (s) | Confusão % | Análise |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]

    for _, r in df.iterrows():
        baseline = " **(baseline)**" if r.get("is_baseline") else ""
        analyzed = "sim" if r.get("has_analysis") else "pendente"
        tut = f"{r.get('tutorial_dwell_pct', 0):.1f}" if pd.notna(r.get("tutorial_dwell_pct")) else "-"
        fix = int(r["n_tutorial_fixations"]) if pd.notna(r.get("n_tutorial_fixations")) else "-"
        rescue = int(r["n_rescue_saccades"]) if pd.notna(r.get("n_rescue_saccades")) else "-"
        mach = f"{r.get('machine_dwell_s', 0):.1f}" if pd.notna(r.get("machine_dwell_s")) else "-"
        conf = f"{r.get('confusion_pct', 0):.1f}" if pd.notna(r.get("confusion_pct")) else "-"
        lines.append(
            f"| `{r['session_id']}`{baseline} | {r.get('build_version', '')} | {tut} | {fix} | {rescue} | {mach} | {conf} | {analyzed} |"
        )

    lines.extend(
        [
            "",
            "## Como atualizar",
            "",
            "1. Adicione a pasta da nova sessão em `sessoes/<nome>/` com `EyeTrackingData.csv` e `session_meta.txt`.",
            "2. Rode o pipeline: `python process_eyetracking.py <nome>/EyeTrackingData.csv --output output/<nome>`.",
            "3. Regere o catálogo: `python scripts/build_catalog.py`.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    df = collect_sessions()
    catalog_path = ROOT / "catalogo_sessoes.csv"
    df.to_csv(catalog_path, index=False)
    print(f"Catálogo: {catalog_path} ({len(df)} sessões)")

    docs_dir = ROOT / "docs"
    docs_dir.mkdir(exist_ok=True)
    evo_path = docs_dir / "evolucao_metricas.md"
    write_evolution_markdown(df, evo_path)
    print(f"Evolução: {evo_path}")


if __name__ == "__main__":
    main()
