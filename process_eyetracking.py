#!/usr/bin/env python3
"""
Pipeline de Análise Eye-Tracking — Cocoa Fabric (Heurística #5 Nielsen).

Uso:
    python process_eyetracking.py EyeTrackingData1.csv \\
        --config config/default_config.yaml \\
        --output output/session1 \\
        --calibration calibration_p01.csv \\
        --interp linear
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from cocoa_analysis.cleaning import clean_blinks_and_tracking
from cocoa_analysis.eckert_model import apply_eckert_plr
from cocoa_analysis.gaze_metrics import (
    build_confusion_episodes,
    build_rescue_events_table,
    build_tutorial_consultations,
    compute_gaze_metrics,
    entropy_before_rescue,
)
from cocoa_analysis.io import load_config, load_eyetracking_csv
from cocoa_analysis.reporting import (
    build_data_quality,
    build_dwell_by_target,
    build_eckert_report,
    build_metrics_dictionary,
    build_session_summary,
    build_windowed_timeseries,
    save_csv,
    save_json,
)
from cocoa_analysis.segmentation import (
    build_activity_summary,
    build_phase_summary,
    compute_recovery_latency,
    iter_activity_segments,
    save_recovery_metrics,
)
from cocoa_analysis.visualization import (
    plot_activity_grid,
    plot_eckert_plr,
    plot_residual_pupil_timeline,
    save_summary_table,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Processa CSV de eye-tracking do Cocoa Fabric (H#5 — Prevenção de Erros).",
    )
    parser.add_argument(
        "csv_path",
        type=Path,
        help="Caminho para o arquivo EyeTrackingData.csv",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/default_config.yaml"),
        help="Arquivo YAML de configuração",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/session"),
        help="Diretório de saída",
    )
    parser.add_argument(
        "--calibration",
        type=Path,
        default=None,
        help="CSV opcional de calibração Eckert (luminance, pupil_diameter)",
    )
    parser.add_argument(
        "--interp",
        choices=["linear", "spline"],
        default=None,
        help="Método de interpolação de AvgPupil (sobrescreve config)",
    )
    parser.add_argument(
        "--no-parquet",
        action="store_true",
        help="Não salvar processed_data.parquet",
    )
    return parser.parse_args()


def run_pipeline(
    csv_path: Path,
    config_path: Path,
    output_dir: Path,
    calibration_path: Path | None = None,
    interp_method: str | None = None,
    save_parquet: bool = True,
) -> None:
    """Executa o pipeline completo de análise."""
    config = load_config(config_path)
    if interp_method is None:
        interp_method = config.get("cleaning", {}).get("interp_method", "linear")

    print(f"[1/5] Carregando {csv_path}...")
    df = load_eyetracking_csv(csv_path)
    print(f"      {len(df):,} registros carregados.")

    data_quality = build_data_quality(df, config)

    print(f"[2/5] Limpeza e interpolação ({interp_method})...")
    df = clean_blinks_and_tracking(df, interp_method=interp_method)
    stats = df.attrs.get("cleaning_stats", {})
    print(
        f"      {stats.get('rows_after', len(df)):,} registros válidos "
        f"({stats.get('rows_removed', 0)} removidos, "
        f"{stats.get('blinks_masked', 0)} piscadas mascaradas)."
    )

    print("[3/5] Aplicando modelo Eckert (correção PLR)...")
    df = apply_eckert_plr(df, config, calibration_path=calibration_path)
    plr = df.attrs.get("plr_params", {})
    print(
        f"      baseline={plr.get('baseline', '?'):.3f} mm, "
        f"RMSE={plr.get('rmse_mm', float('nan')):.3f} mm, "
        f"R2={plr.get('r2', float('nan')):.3f}, "
        f"calibrado={plr.get('calibrated', False)}."
    )

    print("[4/5] Calculando métricas de olhar (VOI, sacadas, entropia, confusão)...")
    df = compute_gaze_metrics(df, config)
    fixations = df.attrs.get("fixations_table")
    consultations = build_tutorial_consultations(df, fixations, config)
    n_rescue = int(df["RescueSaccade"].sum())
    n_before = int((consultations["timing"] == "antes").sum()) if not consultations.empty else 0
    n_after = int((consultations["timing"] == "depois").sum()) if not consultations.empty else 0
    print(
        f"      {n_rescue} sacadas de socorro (consultas ao tutorial): "
        f"{n_before} antes / {n_after} depois do início da tarefa."
    )
    confusion_episodes = build_confusion_episodes(df, config)
    print(f"      {len(confusion_episodes)} episódio(s) de confusão detectado(s).")

    print("[5/5] Segmentação, gráficos e exportação...")
    output_dir.mkdir(parents=True, exist_ok=True)

    recovery = compute_recovery_latency(df, config)
    save_recovery_metrics(recovery, output_dir / "recovery_metrics.json")

    summary = build_phase_summary(df)
    save_summary_table(summary, output_dir / "summary_by_phase.csv")

    rescue_events = build_rescue_events_table(df)
    fs = float(config.get("sampling_rate_hz", 120))
    window_s = float(config["gaze_entropy"]["window_seconds"])
    rescue_events = entropy_before_rescue(df, rescue_events, window_seconds=window_s, fs=fs)
    rescue_events.to_csv(output_dir / "rescue_saccades.csv", index=False)

    consultations.to_csv(output_dir / "tutorial_consultations.csv", index=False)

    confusion_episodes.to_csv(output_dir / "confusion_episodes.csv", index=False)

    plot_residual_pupil_timeline(
        df,
        output_dir / "residual_pupil_timeline.png",
    )

    eckert_report = build_eckert_report(df)
    save_json(eckert_report, output_dir / "eckert_model.json")
    save_csv(pd.DataFrame([eckert_report]), output_dir / "eckert_model.csv")
    plot_eckert_plr(
        df,
        output_dir / "eckert_plr_fit.png",
        plr_params=eckert_report,
    )

    fixations = df.attrs.pop("fixations_table", None)
    if fixations is not None and not fixations.empty:
        fixations.to_csv(output_dir / "fixations.csv", index=False)

    dwell_by_target = build_dwell_by_target(df)
    save_csv(dwell_by_target, output_dir / "dwell_by_target.csv")

    save_json(data_quality, output_dir / "data_quality.json")

    activity_order = config.get("activities", {}).get("expected_order")
    activity_summary = build_activity_summary(
        df,
        expected_order=activity_order,
        confusion_episodes=confusion_episodes,
        consultations=consultations,
    )
    save_summary_table(activity_summary, output_dir / "summary_by_activity.csv")

    plot_activity_grid(
        df,
        output_dir / "residual_pupil_by_activity.png",
        activity_order=activity_order,
    )

    session_summary = build_session_summary(
        df,
        config,
        n_confusion_episodes=len(confusion_episodes),
        consultations=consultations,
        fixations=fixations,
    )
    save_csv(session_summary, output_dir / "summary_session.csv")

    windowed = build_windowed_timeseries(df, config)
    save_csv(windowed, output_dir / "timeseries_windowed.csv")

    save_csv(build_metrics_dictionary(), output_dir / "metrics_dictionary.csv")

    activities_root = output_dir / "by_activity"
    seen_activities: set[str] = set()
    for activity, segment in iter_activity_segments(df):
        if activity in seen_activities:
            continue
        seen_activities.add(activity)

        activity_df = df[df["Activity"].astype(str) == activity]
        if activity_df.empty:
            continue

        safe_name = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in activity
        ) or "Sessao"
        activity_dir = activities_root / safe_name
        activity_dir.mkdir(parents=True, exist_ok=True)

        plot_residual_pupil_timeline(
            activity_df,
            activity_dir / "residual_pupil_timeline.png",
            title=f"ResidualPupil — {activity}",
        )

        activity_rescues = activity_df.loc[activity_df["RescueSaccade"]]
        activity_rescues.to_csv(activity_dir / "rescue_saccades.csv", index=False)

    if save_parquet and config.get("output", {}).get("save_parquet", True):
        export_cols = [
            "SessionTime",
            "Phase",
            "Activity",
            "Target",
            "AOI",
            "AvgPupil_raw",
            "AvgPupil",
            "EffectiveLuminance",
            "PredictedPupil",
            "ResidualPupil",
            "VOICategory",
            "GazeEntropy",
            "TargetSwitchRate",
            "RescueSaccade",
            "Confusion",
            "TargetChanged",
            "DwellTime",
        ]
        export_cols = [c for c in export_cols if c in df.columns]
        df[export_cols].to_parquet(output_dir / "processed_data.parquet", index=False)

    print(f"\nConcluído. Saídas em: {output_dir.resolve()}")
    print(f"  - residual_pupil_timeline.png")
    print(f"  - residual_pupil_by_activity.png")
    print(f"  - summary_session.csv (resumo geral da sessão)")
    print(f"  - summary_by_activity.csv ({len(activity_summary)} atividade(s))")
    print(f"  - summary_by_phase.csv")
    print(f"  - timeseries_windowed.csv ({len(windowed)} janela(s))")
    print(f"  - rescue_saccades.csv")
    print(f"  - tutorial_consultations.csv ({len(consultations)} consulta(s): {n_before} antes / {n_after} depois)")
    print(f"  - confusion_episodes.csv ({len(confusion_episodes)} episódio(s))")
    print(f"  - metrics_dictionary.csv (dicionário de todas as colunas)")
    print(f"  - eckert_plr_fit.png + eckert_model.json/csv (filtro de Eckert)")
    print(f"  - fixations.csv (fixações I-DT)")
    print(f"  - dwell_by_target.csv (tempo por máquina/item/painel)")
    print(f"  - data_quality.json (validade de rastreamento/piscadas/lacunas)")
    print(f"  - recovery_metrics.json")
    print(f"  - by_activity/<Atividade>/{{residual_pupil_timeline.png, rescue_saccades.csv}}")
    if save_parquet:
        print(f"  - processed_data.parquet")


def main() -> int:
    args = parse_args()

    if not args.csv_path.exists():
        print(f"Erro: arquivo não encontrado: {args.csv_path}", file=sys.stderr)
        return 1
    if not args.config.exists():
        print(f"Erro: config não encontrada: {args.config}", file=sys.stderr)
        return 1

    try:
        run_pipeline(
            csv_path=args.csv_path,
            config_path=args.config,
            output_dir=args.output,
            calibration_path=args.calibration,
            interp_method=args.interp,
            save_parquet=not args.no_parquet,
        )
    except Exception as exc:
        print(f"Erro durante processamento: {exc}", file=sys.stderr)
        raise

    return 0


if __name__ == "__main__":
    sys.exit(main())
