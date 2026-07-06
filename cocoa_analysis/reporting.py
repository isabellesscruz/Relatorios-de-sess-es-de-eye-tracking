"""Passo 5: relatórios claros para validação de pesquisa.

Gera três artefatos complementares:
  - ``summary_session.csv``: uma linha com os totais/médias da sessão.
  - ``timeseries_windowed.csv``: série temporal por janela (entropia, pupila,
    dwell por categoria, confusão) para inspeção e plots.
  - ``metrics_dictionary.csv``: dicionário de todas as colunas exportadas,
    com unidade e definição, para reprodutibilidade.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _dwell_seconds(segment: pd.DataFrame, category: str) -> float:
    if segment.empty or "VOICategory" not in segment.columns:
        return 0.0
    ordered = segment.sort_values("SessionTime")
    dt = ordered["SessionTime"].diff().fillna(0.0)
    mask = ordered["VOICategory"] == category
    return float(dt[mask].sum()) if mask.any() else 0.0


def _confusion_seconds(segment: pd.DataFrame) -> float:
    if segment.empty or "Confusion" not in segment.columns:
        return 0.0
    ordered = segment.sort_values("SessionTime")
    dt = ordered["SessionTime"].diff().fillna(0.0)
    mask = ordered["Confusion"].fillna(False).astype(bool)
    return float(dt[mask].sum()) if mask.any() else 0.0


def build_session_summary(
    df: pd.DataFrame,
    config: dict[str, Any],
    n_confusion_episodes: int = 0,
    consultations: pd.DataFrame | None = None,
    fixations: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Resumo geral da sessão em uma única linha."""
    if df.empty:
        return pd.DataFrame()

    t = df["SessionTime"].astype(float)
    duration = float(t.max() - t.min())
    fs = float(config.get("sampling_rate_hz", 120))

    n_activities = (
        int(df["Activity"].astype(str).nunique()) if "Activity" in df.columns else 0
    )
    blink_count = int(df["IsBlink"].sum()) if "IsBlink" in df.columns else 0
    plr = df.attrs.get("plr_params", {})

    from .gaze_metrics import tutorial_fixation_stats, tutorial_timing_aggregates

    timing = tutorial_timing_aggregates(consultations)
    tut_stats = tutorial_fixation_stats(fixations)

    row = {
        "session_duration_s": duration,
        "n_samples": len(df),
        "sampling_rate_hz": fs,
        "n_activities": n_activities,
        "mean_residual_pupil_mm": float(df["ResidualPupil"].mean())
        if "ResidualPupil" in df.columns
        else np.nan,
        "mean_raw_pupil_mm": float(df["AvgPupil"].mean())
        if "AvgPupil" in df.columns
        else np.nan,
        "mean_gaze_entropy_bits": float(df["GazeEntropy"].mean())
        if "GazeEntropy" in df.columns
        else np.nan,
        "task_dwell_s": _dwell_seconds(df, "task"),
        "item_dwell_s": _dwell_seconds(df, "item"),
        "machine_dwell_s": _dwell_seconds(df, "machine"),
        "tutorial_dwell_s": _dwell_seconds(df, "tutorial"),
        "support_dwell_s": _dwell_seconds(df, "support"),
        "tutorial_dwell_pct": 100.0 * _dwell_seconds(df, "tutorial") / duration
        if duration > 0
        else 0.0,
        "n_tutorial_fixations": tut_stats["n_tutorial_fixations"],
        "mean_tutorial_fixation_s": tut_stats["mean_tutorial_fixation_s"],
        "max_tutorial_fixation_s": tut_stats["max_tutorial_fixation_s"],
        "tutorial_before_task_s": timing["tutorial_before_task_s"],
        "tutorial_after_task_s": timing["tutorial_after_task_s"],
        "n_consult_before": timing["n_consult_before"],
        "n_consult_after": timing["n_consult_after"],
        "n_rescue_saccades": int(df["RescueSaccade"].sum())
        if "RescueSaccade" in df.columns
        else 0,
        "gaze_transition_entropy_bits": float(df.attrs.get("stationary_gaze_entropy", np.nan)),
        "transition_entropy_bits": float(df.attrs.get("transition_gaze_entropy", np.nan)),
        "mean_k_coefficient": float(df["KCoefficient"].mean())
        if "KCoefficient" in df.columns
        else np.nan,
        "confusion_time_s": _confusion_seconds(df),
        "confusion_pct": 100.0 * _confusion_seconds(df) / duration
        if duration > 0
        else 0.0,
        "n_confusion_episodes": int(n_confusion_episodes),
        "blink_count": blink_count,
        "plr_model": plr.get("model", ""),
        "plr_baseline_mm": float(plr.get("baseline", np.nan)),
        "plr_k": float(plr.get("k", np.nan)),
        "plr_rmse_mm": float(plr.get("rmse_mm", np.nan)),
        "plr_r2": float(plr.get("r2", np.nan)),
        "plr_calibrated": bool(plr.get("calibrated", False)),
    }
    return pd.DataFrame([row])


def build_eckert_report(df: pd.DataFrame) -> dict[str, Any]:
    """Extrai os parametros e a qualidade do ajuste do filtro de Eckert (PLR)."""
    plr = dict(df.attrs.get("plr_params", {}))
    plr.setdefault("model", "log")
    return plr


def build_dwell_by_target(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tempo de fixação acumulado por alvo (máquina, item, tutorial, parede).

    Uma linha por Target, com categoria, dwell total, número de visitas
    (runs contíguos) e percentual da sessão.
    """
    cols = ["target", "category", "dwell_s", "n_visits", "dwell_pct"]
    if df.empty or "Target" not in df.columns:
        return pd.DataFrame(columns=cols)

    ordered = df.sort_values("SessionTime").reset_index(drop=True)
    dt = ordered["SessionTime"].diff().fillna(0.0)
    duration = float(ordered["SessionTime"].max() - ordered["SessionTime"].min())

    target = ordered["Target"].astype(str)
    run_id = target.ne(target.shift()).cumsum()
    visits_per_target = (
        pd.DataFrame({"target": target, "run": run_id})
        .drop_duplicates()
        .groupby("target")
        .size()
    )

    category = (
        ordered["VOICategory"].astype(str)
        if "VOICategory" in ordered.columns
        else pd.Series([""] * len(ordered))
    )

    rows = []
    for tgt, idx in ordered.groupby(target).groups.items():
        if tgt in ("None", "nan"):
            continue
        dwell = float(dt.loc[idx].sum())
        cat = category.loc[idx].mode().iloc[0] if not category.loc[idx].empty else ""
        rows.append(
            {
                "target": tgt,
                "category": cat,
                "dwell_s": dwell,
                "n_visits": int(visits_per_target.get(tgt, 0)),
                "dwell_pct": 100.0 * dwell / duration if duration > 0 else 0.0,
            }
        )

    result = pd.DataFrame(rows, columns=cols)
    if not result.empty:
        result = result.sort_values("dwell_s", ascending=False).reset_index(drop=True)
    return result


def build_data_quality(raw_df: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    """
    Relatório de qualidade de dados a partir do CSV BRUTO (antes da limpeza).

    Avalia validade de rastreamento, piscadas e lacunas — essencial para
    julgar a confiabilidade das métricas pupilares e de olhar.
    """
    if raw_df.empty:
        return {}

    n = len(raw_df)
    fs = float(config.get("sampling_rate_hz", 120))
    t = raw_df["SessionTime"].astype(float).to_numpy()

    tracking = (
        raw_df["IsTracking"].astype(bool).to_numpy()
        if "IsTracking" in raw_df.columns
        else np.ones(n, dtype=bool)
    )
    blink = (
        raw_df["IsBlink"].astype(bool).to_numpy()
        if "IsBlink" in raw_df.columns
        else np.zeros(n, dtype=bool)
    )
    if {"LeftPupilValid", "RightPupilValid"}.issubset(raw_df.columns):
        pupil_valid = (
            raw_df["LeftPupilValid"].astype(bool) & raw_df["RightPupilValid"].astype(bool)
        ).to_numpy()
    else:
        pupil_valid = np.zeros(n, dtype=bool)

    invalid = ~tracking
    gaps = 0
    gap_lengths_s: list[float] = []
    i = 0
    while i < n:
        if invalid[i]:
            j = i
            while j < n and invalid[j]:
                j += 1
            gaps += 1
            start_t = t[i]
            end_t = t[j - 1] if j - 1 < n else t[-1]
            gap_lengths_s.append(float(end_t - start_t))
            i = j
        else:
            i += 1

    return {
        "n_samples": n,
        "sampling_rate_hz": fs,
        "valid_gaze_pct": float(100.0 * tracking.mean()),
        "blink_pct": float(100.0 * blink.mean()),
        "valid_pupil_pct": float(100.0 * pupil_valid.mean()),
        "n_tracking_gaps": int(gaps),
        "max_gap_s": float(max(gap_lengths_s)) if gap_lengths_s else 0.0,
        "total_gap_s": float(sum(gap_lengths_s)),
    }


def save_json(data: dict[str, Any], output_path: str | Path) -> None:
    """Salva um dicionario como JSON legivel."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def build_windowed_timeseries(
    df: pd.DataFrame,
    config: dict[str, Any],
    window_seconds: float | None = None,
) -> pd.DataFrame:
    """
    Série temporal agregada em janelas fixas (bins) de ``window_seconds``.

    Uma linha por janela, com médias/somas úteis para plotar e validar a
    evolução de entropia, pupila e dwell ao longo do tempo.
    """
    cols = [
        "window_start_s",
        "window_end_s",
        "dominant_activity",
        "n_samples",
        "mean_residual_pupil_mm",
        "mean_raw_pupil_mm",
        "mean_gaze_entropy_bits",
        "mean_target_switch_rate_hz",
        "task_dwell_s",
        "tutorial_dwell_s",
        "support_dwell_s",
        "confusion_frac",
        "n_rescue_saccades",
    ]
    if df.empty:
        return pd.DataFrame(columns=cols)

    if window_seconds is None:
        window_seconds = float(config.get("gaze_entropy", {}).get("window_seconds", 2.0))
    window_seconds = max(0.5, float(window_seconds))

    ordered = df.sort_values("SessionTime").reset_index(drop=True)
    t0 = float(ordered["SessionTime"].iloc[0])
    rel = ordered["SessionTime"].astype(float) - t0
    bin_idx = (rel // window_seconds).astype(int)

    rows = []
    for b, group in ordered.groupby(bin_idx):
        start = t0 + b * window_seconds
        end = start + window_seconds
        activity = (
            group["Activity"].astype(str).mode().iloc[0]
            if "Activity" in group.columns and not group["Activity"].empty
            else ""
        )
        confusion_frac = (
            float(group["Confusion"].fillna(False).astype(bool).mean())
            if "Confusion" in group.columns
            else 0.0
        )
        rows.append(
            {
                "window_start_s": float(start),
                "window_end_s": float(end),
                "dominant_activity": activity,
                "n_samples": len(group),
                "mean_residual_pupil_mm": float(group["ResidualPupil"].mean())
                if "ResidualPupil" in group.columns
                else np.nan,
                "mean_raw_pupil_mm": float(group["AvgPupil"].mean())
                if "AvgPupil" in group.columns
                else np.nan,
                "mean_gaze_entropy_bits": float(group["GazeEntropy"].mean())
                if "GazeEntropy" in group.columns
                else np.nan,
                "mean_target_switch_rate_hz": float(group["TargetSwitchRate"].mean())
                if "TargetSwitchRate" in group.columns
                else np.nan,
                "task_dwell_s": _dwell_seconds(group, "task"),
                "tutorial_dwell_s": _dwell_seconds(group, "tutorial"),
                "support_dwell_s": _dwell_seconds(group, "support"),
                "confusion_frac": confusion_frac,
                "n_rescue_saccades": int(group["RescueSaccade"].sum())
                if "RescueSaccade" in group.columns
                else 0,
            }
        )

    return pd.DataFrame(rows, columns=cols)


# Dicionário de métricas: (arquivo, coluna, unidade, descrição).
_METRICS_DICTIONARY: list[tuple[str, str, str, str]] = [
    # summary_session.csv
    ("summary_session.csv", "session_duration_s", "s", "Duração total da sessão (max-min de SessionTime)."),
    ("summary_session.csv", "n_samples", "contagem", "Número de amostras (frames) de eye-tracking."),
    ("summary_session.csv", "sampling_rate_hz", "Hz", "Taxa de amostragem configurada."),
    ("summary_session.csv", "n_activities", "contagem", "Número de atividades distintas registradas."),
    ("summary_session.csv", "mean_residual_pupil_mm", "mm", "Média da pupila residual (diâmetro observado menos previsto pelo modelo Eckert/PLR)."),
    ("summary_session.csv", "mean_raw_pupil_mm", "mm", "Média do diâmetro pupilar bruto (AvgPupil, sem correção)."),
    ("summary_session.csv", "mean_gaze_entropy_bits", "bits", "Média da entropia espacial do olhar (Shannon, base 2) em janela móvel."),
    ("summary_session.csv", "task_dwell_s", "s", "Tempo total olhando VOIs de tarefa (área de trabalho genérica)."),
    ("summary_session.csv", "item_dwell_s", "s", "Tempo total olhando itens interativos (cacau, faca, semente, panela, manteiga, leite, açúcar...)."),
    ("summary_session.csv", "machine_dwell_s", "s", "Tempo total olhando máquinas (Grinder, Mixer, Dehumidifier, Toaster, Peeler...)."),
    ("summary_session.csv", "tutorial_dwell_s", "s", "Tempo total olhando painéis de tutorial (Paper_*/Writebook_*)."),
    ("summary_session.csv", "support_dwell_s", "s", "Tempo total olhando áreas de suporte genérico (parede/quadro/chão)."),
    ("summary_session.csv", "tutorial_dwell_pct", "%", "tutorial_dwell_s como porcentagem da duração da sessão."),
    ("summary_session.csv", "n_tutorial_fixations", "contagem", "Número de fixações I-DT em painéis de tutorial (olhar sustentado)."),
    ("summary_session.csv", "mean_tutorial_fixation_s", "s", "Duração média das fixações em tutorial."),
    ("summary_session.csv", "max_tutorial_fixation_s", "s", "Duração da maior fixação em tutorial."),
    ("summary_session.csv", "tutorial_before_task_s", "s", "Tempo consultando o tutorial ANTES de iniciar a tarefa (consulta antecipatória)."),
    ("summary_session.csv", "tutorial_after_task_s", "s", "Tempo consultando o tutorial DEPOIS de iniciar a tarefa (consulta reativa)."),
    ("summary_session.csv", "n_consult_before", "contagem", "Número de consultas ao tutorial antes do início da tarefa."),
    ("summary_session.csv", "n_consult_after", "contagem", "Número de consultas ao tutorial depois do início da tarefa."),
    ("summary_session.csv", "n_rescue_saccades", "contagem", "Número de sacadas de socorro = consultas consolidadas ao tutorial (cada busca pelo material de ajuda)."),
    ("summary_session.csv", "gaze_transition_entropy_bits", "bits", "Entropia estacionária de fixação Hs (Krejtz et al., 2015): dispersão da atenção entre AOIs. Absoluta, comparável entre sessões."),
    ("summary_session.csv", "transition_entropy_bits", "bits", "Entropia de transição Ht (Krejtz et al., 2015): imprevisibilidade das transições entre AOIs. Valores altos = busca errática."),
    ("summary_session.csv", "mean_k_coefficient", "z-score", "Coeficiente K médio ambient/focal (Krejtz et al., 2016). K>0 = atenção focal (leitura/foco); K<0 = atenção ambiente (busca/exploração)."),
    ("summary_session.csv", "confusion_time_s", "s", "Tempo total em episódios de confusão/busca visual."),
    ("summary_session.csv", "confusion_pct", "%", "confusion_time_s como porcentagem da duração da sessão."),
    ("summary_session.csv", "n_confusion_episodes", "contagem", "Número de episódios de confusão detectados."),
    ("summary_session.csv", "blink_count", "contagem", "Número de amostras marcadas como piscada."),
    ("summary_session.csv", "plr_model", "texto", "Modelo de mapeamento luminância->pupila do filtro de Eckert (log/poly2/sigmoid)."),
    ("summary_session.csv", "plr_baseline_mm", "mm", "Diâmetro pupilar de base estimado pelo modelo Eckert."),
    ("summary_session.csv", "plr_k", "adimensional", "Ganho k do reflexo fotomotor (quanto a pupila contrai por década de luminância)."),
    ("summary_session.csv", "plr_rmse_mm", "mm", "Erro RMS entre pupila observada e predita pelo PLR (qualidade do ajuste)."),
    ("summary_session.csv", "plr_r2", "adimensional", "R² do ajuste do modelo Eckert (fração da variância pupilar explicada pela luminância)."),
    ("summary_session.csv", "plr_calibrated", "booleano", "Se o modelo usou CSV de calibração por participante (True) ou parâmetros padrão (False)."),
    # summary_by_activity.csv
    ("summary_by_activity.csv", "activity", "texto", "Rótulo da atividade (CortarCacau, SecarSemente, ...)."),
    ("summary_by_activity.csv", "duration_s", "s", "Duração acumulada de todos os trechos da atividade."),
    ("summary_by_activity.csv", "n_samples", "contagem", "Número de amostras na atividade."),
    ("summary_by_activity.csv", "mean_residual_pupil_mm", "mm", "Média da pupila residual na atividade."),
    ("summary_by_activity.csv", "mean_gaze_entropy_bits", "bits", "Média da entropia espacial do olhar na atividade."),
    ("summary_by_activity.csv", "task_dwell_s", "s", "Tempo olhando VOIs de tarefa na atividade."),
    ("summary_by_activity.csv", "tutorial_dwell_s", "s", "Tempo olhando tutoriais na atividade."),
    ("summary_by_activity.csv", "support_dwell_s", "s", "Tempo olhando suporte genérico na atividade."),
    ("summary_by_activity.csv", "tutorial_dwell_pct", "%", "tutorial_dwell_s como % da duração da atividade."),
    ("summary_by_activity.csv", "tutorial_before_task_s", "s", "Tempo consultando o tutorial antes do início da atividade."),
    ("summary_by_activity.csv", "tutorial_after_task_s", "s", "Tempo consultando o tutorial depois do início da atividade."),
    ("summary_by_activity.csv", "n_consult_before", "contagem", "Consultas ao tutorial antes do início da atividade."),
    ("summary_by_activity.csv", "n_consult_after", "contagem", "Consultas ao tutorial depois do início da atividade."),
    ("summary_by_activity.csv", "n_rescue_saccades", "contagem", "Sacadas de socorro (consultas ao tutorial) na atividade."),
    ("summary_by_activity.csv", "confusion_time_s", "s", "Tempo em confusão na atividade."),
    ("summary_by_activity.csv", "confusion_pct", "%", "confusion_time_s como % da duração da atividade."),
    ("summary_by_activity.csv", "n_confusion_episodes", "contagem", "Episódios de confusão na atividade."),
    # summary_by_phase.csv
    ("summary_by_phase.csv", "phase", "texto", "Nome da fase/etapa registrada no Unity."),
    ("summary_by_phase.csv", "duration_s", "s", "Duração da fase."),
    ("summary_by_phase.csv", "n_samples", "contagem", "Número de amostras na fase."),
    ("summary_by_phase.csv", "mean_residual_pupil_mm", "mm", "Média da pupila residual na fase."),
    ("summary_by_phase.csv", "mean_gaze_entropy_bits", "bits", "Média da entropia do olhar na fase."),
    ("summary_by_phase.csv", "tutorial_dwell_s", "s", "Tempo olhando tutoriais na fase."),
    ("summary_by_phase.csv", "support_dwell_s", "s", "Tempo olhando suporte genérico na fase."),
    ("summary_by_phase.csv", "n_rescue_saccades", "contagem", "Sacadas de socorro na fase."),
    ("summary_by_phase.csv", "confusion_time_s", "s", "Tempo em confusão na fase."),
    # rescue_saccades.csv (agora = consultas consolidadas ao tutorial)
    ("rescue_saccades.csv", "session_time_s", "s", "Instante do início da consulta ao tutorial (SessionTime)."),
    ("rescue_saccades.csv", "phase", "texto", "Fase no momento do evento."),
    ("rescue_saccades.csv", "activity", "texto", "Atividade no momento do evento."),
    ("rescue_saccades.csv", "from_target", "texto", "Alvo olhado imediatamente antes (origem da sacada)."),
    ("rescue_saccades.csv", "from_aoi", "texto", "AOI de origem."),
    ("rescue_saccades.csv", "to_target", "texto", "Alvo de tutorial olhado (destino da sacada)."),
    ("rescue_saccades.csv", "to_aoi", "texto", "AOI de destino."),
    ("rescue_saccades.csv", "gaze_entropy_bits", "bits", "Entropia do olhar no instante do evento."),
    ("rescue_saccades.csv", "pre_rescue_entropy_bits", "bits", "Entropia média na janela imediatamente anterior ao evento."),
    # confusion_episodes.csv
    ("confusion_episodes.csv", "start_s", "s", "Início do episódio de confusão."),
    ("confusion_episodes.csv", "end_s", "s", "Fim do episódio de confusão."),
    ("confusion_episodes.csv", "duration_s", "s", "Duração do episódio."),
    ("confusion_episodes.csv", "activity", "texto", "Atividade predominante no episódio."),
    ("confusion_episodes.csv", "mean_gaze_entropy_bits", "bits", "Entropia média do olhar no episódio."),
    ("confusion_episodes.csv", "n_targets_scanned", "contagem", "Número de alvos distintos varridos no episódio."),
    ("confusion_episodes.csv", "targets", "texto", "Lista de alvos varridos (separados por |)."),
    # timeseries_windowed.csv
    ("timeseries_windowed.csv", "window_start_s", "s", "Início da janela temporal."),
    ("timeseries_windowed.csv", "window_end_s", "s", "Fim da janela temporal."),
    ("timeseries_windowed.csv", "dominant_activity", "texto", "Atividade predominante na janela."),
    ("timeseries_windowed.csv", "n_samples", "contagem", "Amostras na janela."),
    ("timeseries_windowed.csv", "mean_residual_pupil_mm", "mm", "Média da pupila residual na janela."),
    ("timeseries_windowed.csv", "mean_raw_pupil_mm", "mm", "Média da pupila bruta na janela."),
    ("timeseries_windowed.csv", "mean_gaze_entropy_bits", "bits", "Média da entropia do olhar na janela."),
    ("timeseries_windowed.csv", "mean_target_switch_rate_hz", "Hz", "Média da taxa de troca de alvo na janela."),
    ("timeseries_windowed.csv", "task_dwell_s", "s", "Tempo em VOI de tarefa na janela."),
    ("timeseries_windowed.csv", "tutorial_dwell_s", "s", "Tempo em tutorial na janela."),
    ("timeseries_windowed.csv", "support_dwell_s", "s", "Tempo em suporte genérico na janela."),
    ("timeseries_windowed.csv", "confusion_frac", "fração 0-1", "Fração da janela marcada como confusão."),
    ("timeseries_windowed.csv", "n_rescue_saccades", "contagem", "Sacadas de socorro iniciadas na janela."),
    # summary_by_activity.csv — novas colunas
    ("summary_by_activity.csv", "item_dwell_s", "s", "Tempo olhando itens interativos na atividade."),
    ("summary_by_activity.csv", "machine_dwell_s", "s", "Tempo olhando máquinas na atividade."),
    # eckert_model.json / eckert_model.csv
    ("eckert_model.json", "model", "texto", "Modelo de mapeamento luminância->pupila (log/poly2/sigmoid)."),
    ("eckert_model.json", "baseline", "mm", "Diâmetro pupilar de base do modelo Eckert."),
    ("eckert_model.json", "k", "adimensional", "Ganho k do reflexo fotomotor."),
    ("eckert_model.json", "epsilon", "adimensional", "Termo de regularização do log (evita log(0))."),
    ("eckert_model.json", "w_fix", "adimensional", "Peso da luminância do alvo fixado vs. fundo (Eckert et al., 2022)."),
    ("eckert_model.json", "l_background", "rel.", "Luminância de fundo assumida."),
    ("eckert_model.json", "plr_lowpass_hz", "Hz", "Corte do passa-baixa que modela a latência do PLR."),
    ("eckert_model.json", "rmse_mm", "mm", "Erro RMS do ajuste (observado vs predito)."),
    ("eckert_model.json", "r2", "adimensional", "R² do ajuste do modelo."),
    ("eckert_model.json", "calibrated", "booleano", "Se usou calibração por participante."),
    # fixations.csv
    ("fixations.csv", "start_s", "s", "Início da fixação (algoritmo I-DT sobre a direção do olhar)."),
    ("fixations.csv", "end_s", "s", "Fim da fixação."),
    ("fixations.csv", "duration_s", "s", "Duração da fixação."),
    ("fixations.csv", "dispersion_deg", "graus", "Dispersão angular da fixação (amplitude do olhar dentro da janela)."),
    ("fixations.csv", "target", "texto", "Alvo/AOI predominante durante a fixação."),
    ("fixations.csv", "category", "texto", "Categoria do alvo predominante (tutorial/machine/item/support/task)."),
    ("fixations.csv", "activity", "texto", "Atividade durante a fixação."),
    ("fixations.csv", "saccade_amplitude_deg", "graus", "Amplitude angular da sacada até a fixação seguinte."),
    # tutorial_consultations.csv
    ("tutorial_consultations.csv", "consultation_start_s", "s", "Início da consulta ao tutorial (grupo de fixações consolidado por rescue.min_gap_s)."),
    ("tutorial_consultations.csv", "consultation_end_s", "s", "Fim da consulta ao tutorial."),
    ("tutorial_consultations.csv", "dwell_s", "s", "Tempo efetivo fixando o tutorial na consulta (soma das fixações)."),
    ("tutorial_consultations.csv", "n_fixations", "contagem", "Número de fixações de tutorial que compõem a consulta."),
    ("tutorial_consultations.csv", "target", "texto", "Painel de tutorial dominante na consulta (Paper_*/Writebook_*)."),
    ("tutorial_consultations.csv", "activity", "texto", "Atividade corrente no início da consulta."),
    ("tutorial_consultations.csv", "nearest_activity", "texto", "Atividade cujo início está mais próximo da consulta."),
    ("tutorial_consultations.csv", "nearest_activity_start_s", "s", "Instante do início de atividade mais próximo (âncora)."),
    ("tutorial_consultations.csv", "offset_s", "s", "Consulta - início da tarefa. Negativo = antes (antecipatória); positivo = depois (reativa)."),
    ("tutorial_consultations.csv", "timing", "texto", "Classificação: 'antes', 'depois' ou 'fora_janela' (além de rescue.window_s do marco)."),
    # dwell_by_target.csv
    ("dwell_by_target.csv", "target", "texto", "Nome do alvo (máquina, item ou painel)."),
    ("dwell_by_target.csv", "category", "texto", "Categoria do alvo (tutorial/machine/item/support/task)."),
    ("dwell_by_target.csv", "dwell_s", "s", "Tempo total de fixação acumulado no alvo."),
    ("dwell_by_target.csv", "n_visits", "contagem", "Número de visitas distintas ao alvo."),
    ("dwell_by_target.csv", "dwell_pct", "%", "dwell_s como % da duração da sessão."),
    # confusion_episodes.csv — novas colunas da literatura
    ("confusion_episodes.csv", "mean_transition_entropy_bits", "bits", "Entropia de transição média no episódio (Krejtz 2015)."),
    ("confusion_episodes.csv", "mean_k_coefficient", "z-score", "Coeficiente K médio no episódio (negativo = busca ambiente)."),
    ("confusion_episodes.csv", "mean_confusion_score", "0-1", "Score contínuo médio de confusão no episódio."),
    # data_quality.json
    ("data_quality.json", "valid_gaze_pct", "%", "Percentual de frames com gaze válido (IsTracking)."),
    ("data_quality.json", "blink_pct", "%", "Percentual de frames marcados como piscada."),
    ("data_quality.json", "valid_pupil_pct", "%", "Percentual de frames com ambos os diâmetros pupilares válidos."),
    ("data_quality.json", "n_tracking_gaps", "contagem", "Número de lacunas de rastreamento (sequências inválidas)."),
    ("data_quality.json", "max_gap_s", "s", "Maior lacuna contínua de rastreamento."),
    ("data_quality.json", "total_gap_s", "s", "Tempo total sem rastreamento válido."),
]


def build_metrics_dictionary() -> pd.DataFrame:
    """Dicionário de dados de todas as colunas exportadas."""
    return pd.DataFrame(
        _METRICS_DICTIONARY,
        columns=["output_file", "column", "unit", "description"],
    )


def save_csv(df: pd.DataFrame, output_path: str | Path) -> None:
    """Salva DataFrame como CSV com 4 casas decimais."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, float_format="%.4f")
