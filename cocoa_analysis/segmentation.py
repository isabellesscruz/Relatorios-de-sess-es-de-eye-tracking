"""Passo 4a: segmentação por fase/atividade e latência de recuperação."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pandas as pd


def is_phase3(phase: str, config: dict[str, Any]) -> bool:
    """Verifica se a fase corresponde à etapa crítica (Fase 3 / moldes)."""
    phase3_names = {p.lower() for p in config["phases"]["phase3_names"]}
    return str(phase).lower() in phase3_names


def compute_recovery_latency(
    df: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Latência de recuperação na Fase 3:

    intervalo entre o pico máximo de ResidualPupil e a primeira fixação em VOI de suporte.
    """
    phase3_df = df[df["Phase"].apply(lambda p: is_phase3(str(p), config))]

    if phase3_df.empty:
        return {
            "phase3_found": False,
            "recovery_latency_s": None,
            "peak_time_s": None,
            "support_time_s": None,
            "peak_residual_pupil": None,
            "note": "Nenhuma amostra de Fase 3 encontrada.",
        }

    peak_idx = phase3_df["ResidualPupil"].idxmax()
    peak_row = phase3_df.loc[peak_idx]
    t_peak = float(peak_row["SessionTime"])
    peak_value = float(peak_row["ResidualPupil"])

    after_peak = phase3_df[
        (phase3_df["SessionTime"] > t_peak)
        & (phase3_df["VOICategory"] == "support")
    ]

    if after_peak.empty:
        return {
            "phase3_found": True,
            "recovery_latency_s": None,
            "peak_time_s": t_peak,
            "support_time_s": None,
            "peak_residual_pupil": peak_value,
            "note": "Pico detectado, mas sem fixação em suporte subsequente.",
        }

    t_support = float(after_peak["SessionTime"].min())
    return {
        "phase3_found": True,
        "recovery_latency_s": t_support - t_peak,
        "peak_time_s": t_peak,
        "support_time_s": t_support,
        "peak_residual_pupil": peak_value,
        "note": None,
    }


def _support_dwell_seconds(group: pd.DataFrame) -> float:
    """
    Tempo total em VOIs de suporte via delta de SessionTime.

    DwellTime no CSV é cumulativo por fixação; somá-lo entre linhas superestima
    o tempo. Usamos diffs de SessionTime nas amostras classificadas como suporte.
    """
    ordered = group.sort_values("SessionTime")
    dt = ordered["SessionTime"].diff().fillna(0.0)
    support_mask = ordered["VOICategory"] == "support"
    if not support_mask.any():
        return 0.0
    return float(dt[support_mask].sum())


def build_phase_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tabela resumo por Phase/Step. Nomes de coluna incluem a unidade; ver
    ``metrics_dictionary.csv`` para definições.
    """
    rows = []
    for phase, group in df.groupby("Phase", observed=True):
        rows.append(
            {
                "phase": str(phase),
                "duration_s": _activity_duration_seconds(group),
                "n_samples": len(group),
                "mean_residual_pupil_mm": float(group["ResidualPupil"].mean()),
                "mean_gaze_entropy_bits": float(group["GazeEntropy"].mean()),
                "tutorial_dwell_s": _dwell_seconds_for_category(group, "tutorial"),
                "support_dwell_s": _support_dwell_seconds(group),
                "n_rescue_saccades": int(group["RescueSaccade"].sum()),
                "confusion_time_s": _confusion_seconds(group),
            }
        )

    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary = summary.sort_values("phase").reset_index(drop=True)
    return summary


def save_recovery_metrics(metrics: dict[str, Any], output_path: str | Path) -> None:
    """Salva métricas de recuperação em JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2, ensure_ascii=False)


def iter_activity_segments(
    df: pd.DataFrame,
) -> Iterator[tuple[str, pd.DataFrame]]:
    """
    Itera sobre runs contíguos da coluna ``Activity``.

    Cada rótulo pode reaparecer (usuário volta a uma atividade); yieldamos
    todos os trechos na ordem cronológica.
    """
    if "Activity" not in df.columns or df.empty:
        return

    activity_series = df["Activity"].astype(str)
    run_id = activity_series.ne(activity_series.shift()).cumsum()

    for _, segment in df.groupby(run_id, sort=False):
        yield str(segment["Activity"].iloc[0]), segment


def _activity_duration_seconds(segment: pd.DataFrame) -> float:
    if segment.empty:
        return 0.0
    t = segment["SessionTime"].to_numpy(dtype=float)
    return float(t.max() - t.min())


def _dwell_seconds_for_category(segment: pd.DataFrame, category: str) -> float:
    if segment.empty or "VOICategory" not in segment.columns:
        return 0.0
    ordered = segment.sort_values("SessionTime")
    dt = ordered["SessionTime"].diff().fillna(0.0)
    mask = ordered["VOICategory"] == category
    if not mask.any():
        return 0.0
    return float(dt[mask].sum())


def _confusion_seconds(segment: pd.DataFrame) -> float:
    """Tempo total em estado de confusão via delta de SessionTime."""
    if segment.empty or "Confusion" not in segment.columns:
        return 0.0
    ordered = segment.sort_values("SessionTime")
    dt = ordered["SessionTime"].diff().fillna(0.0)
    mask = ordered["Confusion"].fillna(False).astype(bool)
    if not mask.any():
        return 0.0
    return float(dt[mask].sum())


def build_activity_summary(
    df: pd.DataFrame,
    expected_order: list[str] | None = None,
    confusion_episodes: pd.DataFrame | None = None,
    consultations: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Uma linha por rótulo de atividade agregando todos os seus runs.

    Nomes de coluna incluem a unidade (``_s`` segundos, ``_mm`` milímetros,
    ``_bits`` bits de entropia de Shannon, ``_pct`` porcentagem). Ver
    ``metrics_dictionary.csv`` para a definição de cada métrica.
    """
    empty_cols = [
        "activity",
        "duration_s",
        "n_samples",
        "mean_residual_pupil_mm",
        "mean_gaze_entropy_bits",
        "task_dwell_s",
        "item_dwell_s",
        "machine_dwell_s",
        "tutorial_dwell_s",
        "support_dwell_s",
        "tutorial_dwell_pct",
        "tutorial_before_task_s",
        "tutorial_after_task_s",
        "n_consult_before",
        "n_consult_after",
        "n_rescue_saccades",
        "confusion_time_s",
        "confusion_pct",
        "n_confusion_episodes",
    ]
    if "Activity" not in df.columns or df.empty:
        return pd.DataFrame(columns=empty_cols)

    episode_counts: dict[str, int] = {}
    if confusion_episodes is not None and not confusion_episodes.empty:
        episode_counts = (
            confusion_episodes["activity"].astype(str).value_counts().to_dict()
        )

    # Consultas ao tutorial classificadas por atividade e timing (antes/depois).
    before_s: dict[str, float] = {}
    after_s: dict[str, float] = {}
    before_n: dict[str, int] = {}
    after_n: dict[str, int] = {}
    if consultations is not None and not consultations.empty:
        for _, c in consultations.iterrows():
            act = str(c.get("activity", ""))
            if c.get("timing") == "antes":
                before_s[act] = before_s.get(act, 0.0) + float(c["dwell_s"])
                before_n[act] = before_n.get(act, 0) + 1
            elif c.get("timing") == "depois":
                after_s[act] = after_s.get(act, 0.0) + float(c["dwell_s"])
                after_n[act] = after_n.get(act, 0) + 1

    per_run: dict[str, dict[str, float]] = {}

    for activity, segment in iter_activity_segments(df):
        acc = per_run.setdefault(
            activity,
            {
                "duration_s": 0.0,
                "residual_sum": 0.0,
                "entropy_sum": 0.0,
                "residual_count": 0,
                "entropy_count": 0,
                "task_dwell_s": 0.0,
                "item_dwell_s": 0.0,
                "machine_dwell_s": 0.0,
                "tutorial_dwell_s": 0.0,
                "support_dwell_s": 0.0,
                "n_rescue_saccades": 0,
                "confusion_time_s": 0.0,
                "n_samples": 0,
            },
        )
        acc["duration_s"] += _activity_duration_seconds(segment)
        acc["task_dwell_s"] += _dwell_seconds_for_category(segment, "task")
        acc["item_dwell_s"] += _dwell_seconds_for_category(segment, "item")
        acc["machine_dwell_s"] += _dwell_seconds_for_category(segment, "machine")
        acc["tutorial_dwell_s"] += _dwell_seconds_for_category(segment, "tutorial")
        acc["support_dwell_s"] += _dwell_seconds_for_category(segment, "support")
        acc["confusion_time_s"] += _confusion_seconds(segment)

        if "ResidualPupil" in segment.columns:
            residual = segment["ResidualPupil"].dropna()
            acc["residual_sum"] += float(residual.sum())
            acc["residual_count"] += int(residual.count())
        if "GazeEntropy" in segment.columns:
            gentropy = segment["GazeEntropy"].dropna()
            acc["entropy_sum"] += float(gentropy.sum())
            acc["entropy_count"] += int(gentropy.count())
        if "RescueSaccade" in segment.columns:
            acc["n_rescue_saccades"] += int(segment["RescueSaccade"].sum())
        acc["n_samples"] += len(segment)

    rows = []
    for activity, acc in per_run.items():
        residual_mean = (
            acc["residual_sum"] / acc["residual_count"]
            if acc["residual_count"] > 0
            else float("nan")
        )
        entropy_mean = (
            acc["entropy_sum"] / acc["entropy_count"]
            if acc["entropy_count"] > 0
            else float("nan")
        )
        duration = acc["duration_s"]
        tutorial_pct = (
            100.0 * acc["tutorial_dwell_s"] / duration if duration > 0 else 0.0
        )
        confusion_pct = (
            100.0 * acc["confusion_time_s"] / duration if duration > 0 else 0.0
        )
        rows.append(
            {
                "activity": activity,
                "duration_s": duration,
                "n_samples": acc["n_samples"],
                "mean_residual_pupil_mm": residual_mean,
                "mean_gaze_entropy_bits": entropy_mean,
                "task_dwell_s": acc["task_dwell_s"],
                "item_dwell_s": acc["item_dwell_s"],
                "machine_dwell_s": acc["machine_dwell_s"],
                "tutorial_dwell_s": acc["tutorial_dwell_s"],
                "support_dwell_s": acc["support_dwell_s"],
                "tutorial_dwell_pct": tutorial_pct,
                "tutorial_before_task_s": before_s.get(activity, 0.0),
                "tutorial_after_task_s": after_s.get(activity, 0.0),
                "n_consult_before": before_n.get(activity, 0),
                "n_consult_after": after_n.get(activity, 0),
                "n_rescue_saccades": acc["n_rescue_saccades"],
                "confusion_time_s": acc["confusion_time_s"],
                "confusion_pct": confusion_pct,
                "n_confusion_episodes": int(episode_counts.get(activity, 0)),
            }
        )

    summary = pd.DataFrame(rows)
    if summary.empty:
        return summary

    if expected_order:
        order_map = {name: idx for idx, name in enumerate(expected_order)}
        summary["_order"] = summary["activity"].map(
            lambda a: order_map.get(a, len(order_map) + hash(a) % 1000)
        )
        summary = summary.sort_values("_order").drop(columns="_order").reset_index(drop=True)
    else:
        summary = summary.sort_values("activity").reset_index(drop=True)

    return summary
