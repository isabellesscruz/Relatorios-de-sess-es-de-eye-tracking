"""Passo 4b/4c: visualizações e exportação de gráficos."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def _category_intervals(
    df: pd.DataFrame, category: str
) -> list[tuple[float, float]]:
    """Intervalos contínuos em que ``VOICategory`` == ``category``."""
    if df.empty or "VOICategory" not in df.columns:
        return []

    intervals: list[tuple[float, float]] = []
    in_run = False
    start = 0.0

    for _, row in df.iterrows():
        is_match = row["VOICategory"] == category
        t = float(row["SessionTime"])

        if is_match and not in_run:
            start = t
            in_run = True
        elif not is_match and in_run:
            intervals.append((start, t))
            in_run = False

    if in_run:
        intervals.append((start, float(df["SessionTime"].iloc[-1])))

    return intervals


def _confusion_intervals(df: pd.DataFrame) -> list[tuple[float, float]]:
    """Intervalos contínuos em que ``Confusion`` é verdadeiro."""
    if df.empty or "Confusion" not in df.columns:
        return []

    intervals: list[tuple[float, float]] = []
    in_run = False
    start = 0.0

    for _, row in df.iterrows():
        is_match = bool(row["Confusion"])
        t = float(row["SessionTime"])

        if is_match and not in_run:
            start = t
            in_run = True
        elif not is_match and in_run:
            intervals.append((start, t))
            in_run = False

    if in_run:
        intervals.append((start, float(df["SessionTime"].iloc[-1])))

    return intervals


def plot_residual_pupil_timeline(
    df: pd.DataFrame,
    output_path: str | Path,
    title: str = "ResidualPupil — Sessão Eye-Tracking (Cocoa Fabric)",
) -> None:
    """
    Gráfico temporal de ResidualPupil com faixas de fixação em tutoriais.

    - Faixas azuis: fixação em painéis de tutorial (categoria ``tutorial``).
    - Faixas cinza claro: fixação em áreas de suporte genérico (categoria ``support``).
    - Linhas verticais tracejadas: sacadas de socorro (consultas consolidadas ao
      tutorial — cada busca pelo material de ajuda, uma linha por consulta).
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    sns.set_theme(style="whitegrid", context="talk")

    fig, ax = plt.subplots(figsize=(14, 5))

    for start, end in _category_intervals(df, "support"):
        ax.axvspan(start, end, color="#8C8C8C", alpha=0.10, label="_nolegend_")
    for start, end in _category_intervals(df, "tutorial"):
        ax.axvspan(start, end, color="#4C72B0", alpha=0.20, label="_nolegend_")
    for start, end in _confusion_intervals(df):
        ax.axvspan(start, end, color="#DD8452", alpha=0.28, label="_nolegend_")

    ax.plot(
        df["SessionTime"],
        df["ResidualPupil"],
        color="#C44E52",
        linewidth=1.2,
        label="ResidualPupil (Δd)",
    )

    rescue_times = df.loc[df["RescueSaccade"], "SessionTime"]
    for i, t in enumerate(rescue_times):
        ax.axvline(
            t,
            color="#55A868",
            linestyle="--",
            linewidth=1.0,
            alpha=0.8,
            label="Sacada de socorro" if i == 0 else "_nolegend_",
        )

    ax.set_xlabel("Tempo de sessão (s)")
    ax.set_ylabel("Pupila residual (mm)")
    ax.set_title(title)

    from matplotlib.patches import Patch

    legend_handles = [
        Patch(facecolor="#4C72B0", alpha=0.3, label="Fixação em tutorial"),
        Patch(facecolor="#8C8C8C", alpha=0.2, label="Fixação em suporte genérico"),
        Patch(facecolor="#DD8452", alpha=0.35, label="Confusão / busca"),
        plt.Line2D([0], [0], color="#C44E52", label="ResidualPupil"),
    ]
    if not rescue_times.empty:
        legend_handles.append(
            plt.Line2D([0], [0], color="#55A868", linestyle="--", label="Sacada de socorro")
        )
    ax.legend(handles=legend_handles, loc="upper right")

    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_activity_grid(
    df: pd.DataFrame,
    output_path: str | Path,
    activity_order: list[str] | None = None,
    title: str = "ResidualPupil por atividade — Cocoa Fabric",
) -> None:
    """
    Grid de subplots (um por atividade) com timeline de ResidualPupil,
    faixas de tutorial e sacadas de socorro. Cada subplot tem eixo X próprio
    zerado no início da atividade para facilitar comparação entre etapas.
    """
    from matplotlib.patches import Patch

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if "Activity" not in df.columns or df.empty:
        return

    activities: list[str] = []
    seen: set[str] = set()
    if activity_order:
        for name in activity_order:
            if name not in seen and (df["Activity"].astype(str) == name).any():
                activities.append(name)
                seen.add(name)
    for name in df["Activity"].astype(str).unique().tolist():
        if name not in seen:
            activities.append(name)
            seen.add(name)

    if not activities:
        return

    sns.set_theme(style="whitegrid", context="talk")

    n = len(activities)
    fig, axes = plt.subplots(n, 1, figsize=(14, 2.6 * n + 1), sharey=True)
    if n == 1:
        axes = [axes]

    for ax, activity in zip(axes, activities):
        segment = df[df["Activity"].astype(str) == activity].copy()
        if segment.empty:
            ax.set_visible(False)
            continue

        t0 = float(segment["SessionTime"].min())
        segment["RelTime"] = segment["SessionTime"].astype(float) - t0

        for start, end in _category_intervals(segment, "support"):
            ax.axvspan(start - t0, end - t0, color="#8C8C8C", alpha=0.10)
        for start, end in _category_intervals(segment, "tutorial"):
            ax.axvspan(start - t0, end - t0, color="#4C72B0", alpha=0.20)
        for start, end in _confusion_intervals(segment):
            ax.axvspan(start - t0, end - t0, color="#DD8452", alpha=0.28)

        ax.plot(
            segment["RelTime"],
            segment["ResidualPupil"],
            color="#C44E52",
            linewidth=1.0,
        )

        rescue_times = segment.loc[segment["RescueSaccade"], "SessionTime"]
        for t in rescue_times:
            ax.axvline(
                float(t) - t0,
                color="#55A868",
                linestyle="--",
                linewidth=1.0,
                alpha=0.8,
            )

        duration = float(segment["SessionTime"].max() - t0)
        n_rescue = int(rescue_times.shape[0])
        ax.set_title(
            f"{activity}  ·  {duration:.1f}s  ·  {n_rescue} sacada(s) de socorro",
            fontsize=12,
        )
        ax.set_xlabel("Tempo desde início da atividade (s)")
        ax.set_ylabel("ResidualPupil (mm)")

    legend_handles = [
        Patch(facecolor="#4C72B0", alpha=0.3, label="Fixação em tutorial"),
        Patch(facecolor="#8C8C8C", alpha=0.2, label="Suporte genérico"),
        Patch(facecolor="#DD8452", alpha=0.35, label="Confusão / busca"),
        plt.Line2D([0], [0], color="#C44E52", label="ResidualPupil"),
        plt.Line2D([0], [0], color="#55A868", linestyle="--", label="Sacada de socorro"),
    ]
    fig.suptitle(title, fontsize=14)
    fig.legend(handles=legend_handles, loc="upper right", bbox_to_anchor=(0.99, 0.995))
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_summary_table(summary: pd.DataFrame, output_path: str | Path) -> None:
    """Exporta tabela resumo por fase."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(path, index=False, float_format="%.4f")


def _predict_plr_curve(
    luminance: np.ndarray,
    plr_params: dict,
) -> np.ndarray:
    """Reconstroi a curva luminancia->pupila a partir dos parametros salvos."""
    model = plr_params.get("model", "log")
    baseline = float(plr_params.get("baseline", 0.0))
    k = float(plr_params.get("k", 0.15))
    epsilon = float(plr_params.get("epsilon", 0.01))
    l = np.asarray(luminance, dtype=np.float64)
    if model == "log":
        return baseline - k * np.log10(l + epsilon)
    # Para poly2/sigmoid a curva exata depende de coeficientes nao exportados;
    # o modelo log e o default do pipeline sem calibracao.
    return baseline - k * np.log10(l + epsilon)


def plot_eckert_plr(
    df: pd.DataFrame,
    output_path: str | Path,
    plr_params: dict | None = None,
    title: str = "Filtro de Eckert (PLR) — correcao do reflexo fotomotor",
) -> None:
    """
    Relatorio visual dedicado ao filtro de Eckert (pilar da correcao PLR).

    Tres paineis:
      1. Timeline: pupila bruta, pupila limpa e pupila predita pelo modelo PLR.
      2. Timeline: pupila residual (componente cognitiva) e luminancia efetiva.
      3. Dispersao luminancia efetiva vs pupila observada, com a curva ajustada.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    sns.set_theme(style="whitegrid", context="talk")
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    ax_top, ax_mid, ax_bot = axes

    t = df["SessionTime"]

    if "AvgPupil_raw" in df.columns:
        ax_top.plot(
            t, df["AvgPupil_raw"],
            color="#B0B0B0", linewidth=0.8, alpha=0.6, label="Pupila bruta (AvgPupil_raw)",
        )
    ax_top.plot(
        t, df["AvgPupil"],
        color="#4C72B0", linewidth=1.1, label="Pupila limpa (interpolada)",
    )
    ax_top.plot(
        t, df["PredictedPupil"],
        color="#DD8452", linewidth=1.4, label="Pupila predita (PLR / Eckert)",
    )
    ax_top.set_ylabel("Diametro (mm)")
    ax_top.set_title("Pupila observada vs predita pelo modelo PLR")
    ax_top.legend(loc="upper right", fontsize=10)

    ax_mid.axhline(0.0, color="#555555", linewidth=0.8, linestyle=":")
    ax_mid.plot(
        t, df["ResidualPupil"],
        color="#C44E52", linewidth=1.1, label="Pupila residual (cognitiva)",
    )
    ax_mid.set_ylabel("Residual (mm)")
    ax_mid.set_xlabel("Tempo de sessao (s)")
    ax_mid.set_title("Pupila residual (AvgPupil - PredictedPupil)")
    if "EffectiveLuminance" in df.columns:
        ax_lum = ax_mid.twinx()
        ax_lum.plot(
            t, df["EffectiveLuminance"],
            color="#8172B3", linewidth=0.9, alpha=0.6, label="Luminancia efetiva",
        )
        ax_lum.set_ylabel("Luminancia efetiva (rel.)")
        ax_lum.grid(False)
    ax_mid.legend(loc="upper right", fontsize=10)

    if "EffectiveLuminance" in df.columns:
        lum = df["EffectiveLuminance"].to_numpy(dtype=float)
        pupil = df["AvgPupil"].to_numpy(dtype=float)
        ax_bot.scatter(
            lum, pupil, s=6, color="#4C72B0", alpha=0.25, label="Amostras",
        )
        if plr_params is not None and len(lum) > 0:
            grid = np.linspace(np.nanmin(lum), np.nanmax(lum), 100)
            curve = _predict_plr_curve(grid, plr_params)
            ax_bot.plot(
                grid, curve,
                color="#DD8452", linewidth=2.2, label="Curva PLR ajustada",
            )
    ax_bot.set_xlabel("Luminancia efetiva (relativa)")
    ax_bot.set_ylabel("Pupila observada (mm)")
    ax_bot.set_title("Ajuste luminancia -> pupila (modelo de Eckert)")
    ax_bot.legend(loc="upper right", fontsize=10)

    if plr_params is not None:
        subtitle = (
            f"modelo={plr_params.get('model', '?')}  ·  "
            f"baseline={plr_params.get('baseline', float('nan')):.3f} mm  ·  "
            f"k={plr_params.get('k', float('nan')):.3f}  ·  "
            f"RMSE={plr_params.get('rmse_mm', float('nan')):.3f} mm  ·  "
            f"R2={plr_params.get('r2', float('nan')):.3f}  ·  "
            f"calibrado={plr_params.get('calibrated', False)}"
        )
        fig.suptitle(f"{title}\n{subtitle}", fontsize=13)
    else:
        fig.suptitle(title, fontsize=14)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
