"""Passo 3: métricas de IHC — VOIs, sacadas de socorro e entropia do olhar."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import entropy


def classify_voi(
    target: str,
    aoi: str,
    config: dict[str, Any],
    target_category: str | None = None,
) -> str:
    """
    Classifica fixação em ``tutorial``, ``machine``, ``item``, ``support`` ou
    ``task``.

    Se o CSV do Unity já traz a coluna ``TargetCategory`` (builds >= 0.9.15),
    ela é usada diretamente (fonte da verdade). Caso contrário (CSVs antigos),
    a categoria é inferida por nome/tag via configuração.

    Prioridade de inferência: tutorial > machine > item > support > task.
    """
    voi_cfg = config["voi"]

    if target_category is not None:
        cat = str(target_category).strip().lower()
        if cat in ("tutorial", "machine", "item", "support", "task"):
            return cat
        if cat == "none":
            return "support"

    target_str = str(target).strip()
    aoi_str = str(aoi).strip()
    target_lower = target_str.lower()

    tutorial_targets = {s.lower() for s in voi_cfg.get("tutorial_targets", [])}
    support_targets = {s.lower() for s in voi_cfg.get("support_targets", [])}
    task_targets = {s.lower() for s in voi_cfg.get("task_targets", [])}
    item_tags = {s.lower() for s in voi_cfg.get("item_tags", [])}
    machine_targets = {s.lower() for s in voi_cfg.get("machine_targets", [])}

    if target_lower in tutorial_targets:
        return "tutorial"
    if target_lower in support_targets:
        return "support"

    tutorial_prefixes = [p.lower() for p in voi_cfg.get("tutorial_name_prefixes", [])]
    if any(target_lower.startswith(p) for p in tutorial_prefixes):
        return "tutorial"

    tutorial_keywords = [k.lower() for k in voi_cfg.get("tutorial_name_keywords", [])]
    if any(kw in target_lower for kw in tutorial_keywords):
        return "tutorial"

    if target_lower in machine_targets or aoi_str.lower() in machine_targets:
        return "machine"
    machine_keywords = [k.lower() for k in voi_cfg.get("machine_name_keywords", [])]
    if any(kw in target_lower for kw in machine_keywords):
        return "machine"

    if target_lower in item_tags or aoi_str.lower() in item_tags:
        return "item"
    item_keywords = [k.lower() for k in voi_cfg.get("item_name_keywords", [])]
    if any(kw in target_lower for kw in item_keywords):
        return "item"

    if target_lower in task_targets:
        return "task"

    keywords = [k.lower() for k in voi_cfg.get("support_keywords", [])]
    if any(kw in target_lower for kw in keywords):
        return "support"

    if voi_cfg.get("use_aoi_barrier_as_support", False) and aoi_str.lower() == "barrier":
        return "support"

    return "task"


def add_voi_category(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Adiciona coluna VOICategory ao DataFrame."""
    out = df.copy()
    has_category = "TargetCategory" in out.columns
    out["VOICategory"] = out.apply(
        lambda row: classify_voi(
            row["Target"],
            row["AOI"],
            config,
            row["TargetCategory"] if has_category else None,
        ),
        axis=1,
    )
    return out


def _merge_tutorial_consultations(
    fixations: pd.DataFrame,
    min_gap_s: float,
) -> list[dict[str, Any]]:
    """
    Agrupa fixações de tutorial contíguas (separadas por lacuna < ``min_gap_s``)
    numa única CONSULTA ao tutorial. Cada consulta representa uma vez em que o
    usuário se voltou para o material de ajuda (base da sacada de socorro).

    Retorna lista de dicts com início/fim/duração da consulta, alvo dominante e
    atividade no início.
    """
    if fixations is None or fixations.empty or "category" not in fixations.columns:
        return []

    tut = fixations[fixations["category"] == "tutorial"].sort_values("start_s")
    if tut.empty:
        return []

    consultations: list[dict[str, Any]] = []
    group: list[pd.Series] = []
    prev_end: float | None = None

    def _flush(g: list[pd.Series]) -> None:
        if not g:
            return
        start_s = float(g[0]["start_s"])
        end_s = float(g[-1]["end_s"])
        # Duração efetivamente fixando o tutorial (soma das fixações do grupo).
        dwell = float(sum(float(f["end_s"]) - float(f["start_s"]) for f in g))
        targets = [str(f["target"]) for f in g]
        dominant = max(set(targets), key=targets.count)
        consultations.append(
            {
                "start_s": start_s,
                "end_s": end_s,
                "duration_s": end_s - start_s,
                "dwell_s": dwell,
                "n_fixations": len(g),
                "target": dominant,
                "activity": str(g[0]["activity"]),
            }
        )

    for _, fix in tut.iterrows():
        if prev_end is not None and (float(fix["start_s"]) - prev_end) >= min_gap_s:
            _flush(group)
            group = []
        group.append(fix)
        prev_end = float(fix["end_s"])
    _flush(group)

    return consultations


def detect_rescue_saccades(
    df: pd.DataFrame,
    fixations: pd.DataFrame | None = None,
    config: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """
    Sacada de socorro = toda vez que o usuário BUSCA o tutorial.

    Nova definição (não depende mais de mapear ``task``): cada CONSULTA ao
    tutorial — grupo de fixações de tutorial consolidado por ``rescue.min_gap_s``
    — conta como uma sacada de socorro. Paredes/quadros genéricos não são mais
    exigidos como origem, pois o olhar de tarefa raramente cai num VOI mapeável.

    Marca ``RescueSaccade=True`` no primeiro frame de cada consulta consolidada.
    """
    out = df.copy()
    out["RescueSaccade"] = False

    if fixations is None or fixations.empty:
        # Fallback legado: entrada em tutorial vinda de fora de tutorial.
        if "VOICategory" in out.columns:
            prev_category = out["VOICategory"].shift(1)
            out["RescueSaccade"] = (
                out.get("TargetChanged", False)
                & (prev_category != "tutorial")
                & (out["VOICategory"] == "tutorial")
            )
        return out

    min_gap_s = float((config or {}).get("rescue", {}).get("min_gap_s", 0.3))
    consultations = _merge_tutorial_consultations(fixations, min_gap_s)
    if not consultations:
        return out

    times = out["SessionTime"].to_numpy(dtype=np.float64)
    for c in consultations:
        idx = int(np.searchsorted(times, c["start_s"], side="left"))
        idx = min(max(idx, 0), len(out) - 1)
        out.iloc[idx, out.columns.get_loc("RescueSaccade")] = True

    out.attrs["tutorial_consultations"] = consultations
    return out


def build_rescue_events_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tabela de eventos de sacada de socorro (uma linha por evento).

    Nomes de coluna incluem a unidade; ver ``metrics_dictionary.csv``.
    """
    cols = [
        "session_time_s",
        "phase",
        "activity",
        "from_target",
        "from_aoi",
        "to_target",
        "to_aoi",
        "gaze_entropy_bits",
    ]
    events = df.loc[df["RescueSaccade"]].copy()
    if events.empty:
        return pd.DataFrame(columns=cols)

    prev_targets = df["Target"].shift(1).loc[events.index]
    prev_aois = df["AOI"].shift(1).loc[events.index]

    return pd.DataFrame(
        {
            "session_time_s": events["SessionTime"].values,
            "phase": events["Phase"].astype(str).values,
            "activity": events["Activity"].astype(str).values
            if "Activity" in events.columns
            else "",
            "from_target": prev_targets.astype(str).values,
            "from_aoi": prev_aois.astype(str).values,
            "to_target": events["Target"].astype(str).values,
            "to_aoi": events["AOI"].astype(str).values,
            "gaze_entropy_bits": events["GazeEntropy"].values
            if "GazeEntropy" in events.columns
            else np.nan,
        }
    )


def _activity_start_times(df: pd.DataFrame) -> list[tuple[float, str]]:
    """Instantes em que a coluna ``Activity`` muda (início de cada tarefa)."""
    if "Activity" not in df.columns or df.empty:
        return []
    ordered = df.sort_values("SessionTime")
    act = ordered["Activity"].astype(str)
    changed = act.ne(act.shift())
    starts = ordered.loc[changed, ["SessionTime", "Activity"]]
    return [
        (float(r["SessionTime"]), str(r["Activity"]))
        for _, r in starts.iterrows()
    ]


def build_tutorial_consultations(
    df: pd.DataFrame,
    fixations: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    """
    Consultas ao tutorial classificadas como ANTES ou DEPOIS do início da tarefa.

    Cada consulta (grupo de fixações de tutorial consolidado por
    ``rescue.min_gap_s``) é comparada ao início de atividade mais próximo
    (mudança da coluna ``Activity``). ``offset_s`` negativo = consulta
    antecipatória (olhou o tutorial ANTES de disparar a ação); positivo =
    consulta reativa (olhou DEPOIS de iniciar). ``timing`` só é preenchido se o
    evento cai dentro de ``rescue.window_s`` do marco.
    """
    cols = [
        "consultation_start_s",
        "consultation_end_s",
        "dwell_s",
        "n_fixations",
        "target",
        "activity",
        "nearest_activity",
        "nearest_activity_start_s",
        "offset_s",
        "timing",
    ]

    rescue_cfg = config.get("rescue", {})
    min_gap_s = float(rescue_cfg.get("min_gap_s", 0.3))
    window_s = float(rescue_cfg.get("window_s", 8.0))

    consultations = _merge_tutorial_consultations(fixations, min_gap_s)
    if not consultations:
        return pd.DataFrame(columns=cols)

    starts = _activity_start_times(df)

    rows = []
    for c in consultations:
        t0 = c["start_s"]
        nearest_act = ""
        nearest_t = np.nan
        offset = np.nan
        timing = "fora_janela"

        if starts:
            diffs = [(t0 - st, st, name) for st, name in starts]
            # Marco mais próximo em tempo absoluto.
            offset, nearest_t, nearest_act = min(diffs, key=lambda d: abs(d[0]))
            if abs(offset) <= window_s:
                timing = "depois" if offset >= 0 else "antes"

        rows.append(
            {
                "consultation_start_s": t0,
                "consultation_end_s": c["end_s"],
                "dwell_s": c["dwell_s"],
                "n_fixations": c["n_fixations"],
                "target": c["target"],
                "activity": c["activity"],
                "nearest_activity": nearest_act,
                "nearest_activity_start_s": nearest_t,
                "offset_s": offset,
                "timing": timing,
            }
        )

    return pd.DataFrame(rows, columns=cols)


def tutorial_fixation_stats(fixations: pd.DataFrame) -> dict[str, float]:
    """
    Estatísticas de fixação sustentada em tutorial (consolidando frames soltos
    em eventos de fixação I-DT).
    """
    empty = {
        "n_tutorial_fixations": 0,
        "mean_tutorial_fixation_s": 0.0,
        "max_tutorial_fixation_s": 0.0,
    }
    if fixations is None or fixations.empty or "category" not in fixations.columns:
        return empty
    tut = fixations[fixations["category"] == "tutorial"]
    if tut.empty:
        return empty
    dur = tut["duration_s"].to_numpy(dtype=np.float64)
    return {
        "n_tutorial_fixations": int(len(tut)),
        "mean_tutorial_fixation_s": float(dur.mean()),
        "max_tutorial_fixation_s": float(dur.max()),
    }


def tutorial_timing_aggregates(consultations: pd.DataFrame) -> dict[str, float]:
    """Agrega dwell e contagem de consultas ao tutorial antes/depois da tarefa."""
    res = {
        "tutorial_before_task_s": 0.0,
        "tutorial_after_task_s": 0.0,
        "n_consult_before": 0,
        "n_consult_after": 0,
    }
    if consultations is None or consultations.empty or "timing" not in consultations.columns:
        return res
    before = consultations[consultations["timing"] == "antes"]
    after = consultations[consultations["timing"] == "depois"]
    res["tutorial_before_task_s"] = float(before["dwell_s"].sum())
    res["tutorial_after_task_s"] = float(after["dwell_s"].sum())
    res["n_consult_before"] = int(len(before))
    res["n_consult_after"] = int(len(after))
    return res


def _window_entropy(
    hit_x: np.ndarray,
    hit_y: np.ndarray,
    hit_z: np.ndarray,
    n_bins: int,
) -> float:
    """Entropia de Shannon sobre histograma 3D discretizado de posições de fixação."""
    if len(hit_x) < 2:
        return 0.0

    edges_x = np.linspace(hit_x.min(), hit_x.max(), n_bins + 1)
    edges_y = np.linspace(hit_y.min(), hit_y.max(), n_bins + 1)
    edges_z = np.linspace(hit_z.min(), hit_z.max(), n_bins + 1)

    if np.any(edges_x[1:] == edges_x[:-1]):
        edges_x = np.linspace(hit_x.min(), hit_x.max() + 1e-6, n_bins + 1)
    if np.any(edges_y[1:] == edges_y[:-1]):
        edges_y = np.linspace(hit_y.min(), hit_y.max() + 1e-6, n_bins + 1)
    if np.any(edges_z[1:] == edges_z[:-1]):
        edges_z = np.linspace(hit_z.min(), hit_z.max() + 1e-6, n_bins + 1)

    hist, _ = np.histogramdd(
        sample=(hit_x, hit_y, hit_z),
        bins=(edges_x, edges_y, edges_z),
    )
    flat = hist.ravel()
    total = flat.sum()
    if total == 0:
        return 0.0
    probs = flat / total
    probs = probs[probs > 0]
    return float(entropy(probs, base=2))


def compute_gaze_entropy(
    df: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    """
    Calcula entropia espacial do olhar em janela móvel sobre HitX, HitY, HitZ.

    Valores altos indicam varredura visual errática (possível confusão).
    """
    out = df.copy()
    entropy_cfg = config["gaze_entropy"]
    fs = float(config.get("sampling_rate_hz", 120))

    window_samples = max(2, int(entropy_cfg["window_seconds"] * fs))
    step_samples = max(1, int(entropy_cfg["step_seconds"] * fs))
    n_bins = int(entropy_cfg["n_bins"])

    n = len(out)
    gaze_entropy = np.full(n, np.nan, dtype=np.float64)

    hit_x = out["HitX"].to_numpy(dtype=np.float64)
    hit_y = out["HitY"].to_numpy(dtype=np.float64)
    hit_z = out["HitZ"].to_numpy(dtype=np.float64)

    for start in range(0, n - window_samples + 1, step_samples):
        end = start + window_samples
        h = _window_entropy(
            hit_x[start:end],
            hit_y[start:end],
            hit_z[start:end],
            n_bins=n_bins,
        )
        gaze_entropy[start:end] = h

    out["GazeEntropy"] = gaze_entropy.astype(np.float32)
    return out


def entropy_before_rescue(
    df: pd.DataFrame,
    rescue_events: pd.DataFrame,
    window_seconds: float = 2.0,
    fs: float = 120.0,
) -> pd.DataFrame:
    """
    Entropia média na janela pré-sacada para cada evento de socorro.

    Útil para correlacionar confusão visual antes de olhar para tutoriais.
    """
    if rescue_events.empty:
        rescue_events = rescue_events.copy()
        rescue_events["pre_rescue_entropy_bits"] = []
        return rescue_events

    window_samples = max(1, int(window_seconds * fs))
    enriched = rescue_events.copy()
    means = []

    time_col = "session_time_s" if "session_time_s" in rescue_events.columns else "SessionTime"
    for _, event in rescue_events.iterrows():
        t = event[time_col]
        prior = df[df["SessionTime"] < t].tail(window_samples)
        if prior.empty or "GazeEntropy" not in prior.columns:
            means.append(np.nan)
        else:
            means.append(float(prior["GazeEntropy"].mean()))

    enriched["pre_rescue_entropy_bits"] = means
    return enriched


def compute_target_switch_rate(
    df: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    """
    Taxa de troca de alvo (TargetChanged por segundo) em janela móvel.

    Valores altos indicam varredura errática entre objetos (busca/confusão),
    em oposição a leitura calma de um único painel.
    """
    out = df.copy()
    fs = float(config.get("sampling_rate_hz", 120))
    conf_cfg = config.get("confusion", {})
    window_s = float(conf_cfg.get("switch_window_seconds", 2.0))
    window_samples = max(2, int(window_s * fs))

    if "TargetChanged" not in out.columns:
        out["TargetSwitchRate"] = 0.0
        return out

    changed = out["TargetChanged"].fillna(0).astype(float).to_numpy()
    kernel = np.ones(window_samples, dtype=float)
    counts = np.convolve(changed, kernel, mode="same")
    out["TargetSwitchRate"] = (counts / window_s).astype(np.float32)
    return out


def _angular_dispersion(dirs: np.ndarray) -> float:
    """Dispersão angular (graus) de um conjunto de direções de olhar unitárias."""
    if len(dirs) < 2:
        return 0.0
    mean = dirs.mean(axis=0)
    norm = np.linalg.norm(mean)
    if norm < 1e-9:
        return 180.0
    mean = mean / norm
    dots = np.clip(dirs @ mean, -1.0, 1.0)
    return float(np.degrees(np.arccos(dots)).max())


def _angle_between(a: np.ndarray, b: np.ndarray) -> float:
    """Ângulo (graus) entre dois vetores."""
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    dot = np.clip(np.dot(a, b) / (na * nb), -1.0, 1.0)
    return float(np.degrees(np.arccos(dot)))


def detect_fixations(
    df: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Detector de fixações I-DT (Salvucci & Goldberg, 2000) sobre a direção do
    olhar, com dispersão medida em graus.

    Retorna ``(df_com_FixationId, tabela_de_fixacoes)``. A tabela inclui a
    amplitude da sacada até a fixação seguinte, base para o coeficiente K.
    """
    fix_cfg = config.get("fixation", {})
    disp_thr = float(fix_cfg.get("dispersion_deg", 1.5))
    min_dur = float(fix_cfg.get("min_duration_s", 0.1))

    cols = [
        "start_s",
        "end_s",
        "duration_s",
        "dispersion_deg",
        "target",
        "category",
        "activity",
        "saccade_amplitude_deg",
        "mean_dir_x",
        "mean_dir_y",
        "mean_dir_z",
    ]

    out = df.sort_values("SessionTime").reset_index(drop=True)
    n = len(out)
    out["FixationId"] = -1
    if n == 0 or not {"DirX", "DirY", "DirZ"}.issubset(out.columns):
        return out, pd.DataFrame(columns=cols)

    t = out["SessionTime"].to_numpy(dtype=np.float64)
    dirs = out[["DirX", "DirY", "DirZ"]].to_numpy(dtype=np.float64)
    norms = np.linalg.norm(dirs, axis=1, keepdims=True)
    norms[norms < 1e-9] = 1.0
    dirs = dirs / norms

    fixations: list[dict[str, Any]] = []
    fix_id = 0
    start = 0
    while start < n:
        end = start
        while end < n and (t[end] - t[start]) < min_dur:
            end += 1
        if end >= n:
            break

        if _angular_dispersion(dirs[start : end + 1]) <= disp_thr:
            while end + 1 < n and _angular_dispersion(dirs[start : end + 2]) <= disp_thr:
                end += 1

            block = out.iloc[start : end + 1]
            out.loc[block.index, "FixationId"] = fix_id
            mean_dir = dirs[start : end + 1].mean(axis=0)
            target = (
                block["Target"].astype(str).mode().iloc[0]
                if not block["Target"].empty
                else ""
            )
            category = (
                block["VOICategory"].astype(str).mode().iloc[0]
                if "VOICategory" in block.columns and not block["VOICategory"].empty
                else ""
            )
            activity = (
                block["Activity"].astype(str).mode().iloc[0]
                if "Activity" in block.columns and not block["Activity"].empty
                else ""
            )
            fixations.append(
                {
                    "start_s": float(t[start]),
                    "end_s": float(t[end]),
                    "duration_s": float(t[end] - t[start]),
                    "dispersion_deg": _angular_dispersion(dirs[start : end + 1]),
                    "target": target,
                    "category": category,
                    "activity": activity,
                    "saccade_amplitude_deg": np.nan,
                    "mean_dir_x": float(mean_dir[0]),
                    "mean_dir_y": float(mean_dir[1]),
                    "mean_dir_z": float(mean_dir[2]),
                }
            )
            fix_id += 1
            start = end + 1
        else:
            start += 1

    table = pd.DataFrame(fixations, columns=cols)
    for i in range(len(table) - 1):
        a = table.loc[i, ["mean_dir_x", "mean_dir_y", "mean_dir_z"]].to_numpy(dtype=float)
        b = table.loc[i + 1, ["mean_dir_x", "mean_dir_y", "mean_dir_z"]].to_numpy(dtype=float)
        table.loc[i, "saccade_amplitude_deg"] = _angle_between(a, b)

    return out, table


def compute_k_coefficient(
    df: pd.DataFrame,
    fixations: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Coeficiente K de atenção ambiente/focal (Krejtz et al., 2016).

    Para cada fixação i: K_i = z(duração_i) - z(amplitude_sacada_{i+1}).
    K > 0 indica atenção focal (fixações longas, sacadas curtas — leitura/foco);
    K < 0 indica atenção ambiente (fixações curtas, sacadas amplas — busca).

    Adiciona ``KCoefficient`` por amostra (herdado da fixação a que pertence) e
    ``k_coefficient`` por fixação; guarda a média da sessão em ``df.attrs``.
    """
    out = df.copy()
    out["KCoefficient"] = np.nan
    fx = fixations.copy()
    if fx.empty:
        out.attrs["mean_k_coefficient"] = float("nan")
        fx["k_coefficient"] = []
        return out, fx

    dur = fx["duration_s"].to_numpy(dtype=np.float64)
    amp = fx["saccade_amplitude_deg"].to_numpy(dtype=np.float64)

    def _z(x: np.ndarray) -> np.ndarray:
        mask = np.isfinite(x)
        if mask.sum() < 2:
            return np.full_like(x, np.nan, dtype=np.float64)
        mu = np.nanmean(x[mask])
        sd = np.nanstd(x[mask])
        if sd < 1e-9:
            return np.zeros_like(x, dtype=np.float64)
        return (x - mu) / sd

    k = _z(dur) - _z(amp)
    fx["k_coefficient"] = k
    out.attrs["mean_k_coefficient"] = float(np.nanmean(k)) if np.isfinite(k).any() else float("nan")

    if "FixationId" in out.columns:
        k_by_id = {i: k[i] for i in range(len(k)) if np.isfinite(k[i])}
        out["KCoefficient"] = out["FixationId"].map(k_by_id).astype(np.float32)

    return out, fx


def compute_gaze_transition_entropy(
    df: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    """
    Entropia de fixação estacionária (Hs) e de transição (Ht) entre AOIs,
    conforme Krejtz et al. (2015), "Gaze transition entropy".

    - Hs = -Σ p_i log2 p_i  (dispersão da atenção entre AOIs; absoluta em bits).
    - Ht = Σ p_i · (-Σ_j P(j|i) log2 P(j|i))  (imprevisibilidade das transições).

    Métricas de sessão comparáveis entre builds; guardadas em ``df.attrs``.
    """
    out = df.copy()
    if "Target" not in out.columns or out.empty:
        out.attrs["stationary_gaze_entropy"] = float("nan")
        out.attrs["transition_gaze_entropy"] = float("nan")
        return out

    seq = out.sort_values("SessionTime")["Target"].astype(str)
    collapsed = seq[seq != seq.shift()].tolist()

    states = sorted(set(collapsed))
    if len(states) < 2 or len(collapsed) < 2:
        out.attrs["stationary_gaze_entropy"] = 0.0
        out.attrs["transition_gaze_entropy"] = 0.0
        return out

    index = {s: i for i, s in enumerate(states)}
    m = len(states)
    trans = np.zeros((m, m), dtype=np.float64)
    for a, b in zip(collapsed[:-1], collapsed[1:]):
        trans[index[a], index[b]] += 1.0

    row_sums = trans.sum(axis=1)
    p_stationary = row_sums / row_sums.sum() if row_sums.sum() > 0 else row_sums

    hs = float(entropy(p_stationary[p_stationary > 0], base=2))

    ht = 0.0
    for i in range(m):
        if row_sums[i] == 0:
            continue
        cond = trans[i] / row_sums[i]
        cond = cond[cond > 0]
        if cond.size:
            ht += p_stationary[i] * float(entropy(cond, base=2))

    out.attrs["stationary_gaze_entropy"] = hs
    out.attrs["transition_gaze_entropy"] = float(ht)
    return out


def detect_confusion(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """
    CONFUSÃO/BUSCA visual com score contínuo (0-1) e LIMIARES ABSOLUTOS.

    Diferente da versão anterior (percentil relativo à sessão, não comparável),
    o score combina três evidências independentes com cortes fixos, permitindo
    comparação entre builds e validação:
      - entropia espacial do olhar alta (varredura ampla);
      - taxa de troca de alvo alta (não fixa);
      - coeficiente K negativo (atenção ambiente/busca, Krejtz 2016).

    Cria ``ConfusionScore`` (0-1) e ``Confusion`` (bool, score >= limiar).
    """
    out = df.copy()
    conf_cfg = config.get("confusion", {})
    abs_cfg = conf_cfg.get("absolute", {})

    if "GazeEntropy" not in out.columns or "TargetSwitchRate" not in out.columns:
        out["ConfusionScore"] = 0.0
        out["Confusion"] = False
        return out

    e_lo = float(abs_cfg.get("entropy_bits_lo", 3.5))
    e_hi = float(abs_cfg.get("entropy_bits_hi", 5.5))
    s_lo = float(abs_cfg.get("switch_rate_lo_hz", 0.8))
    s_hi = float(abs_cfg.get("switch_rate_hi_hz", 3.0))
    k_scale = float(abs_cfg.get("k_ambient_scale", 1.0))
    score_thr = float(abs_cfg.get("score_threshold", 0.5))
    w_ent = float(abs_cfg.get("weight_entropy", 0.4))
    w_switch = float(abs_cfg.get("weight_switch", 0.4))
    w_k = float(abs_cfg.get("weight_k", 0.2))

    def _clip01(x: np.ndarray) -> np.ndarray:
        return np.clip(x, 0.0, 1.0)

    entropy_comp = _clip01(
        (out["GazeEntropy"].fillna(e_lo).to_numpy() - e_lo) / max(e_hi - e_lo, 1e-6)
    )
    switch_comp = _clip01(
        (out["TargetSwitchRate"].fillna(0.0).to_numpy() - s_lo) / max(s_hi - s_lo, 1e-6)
    )
    if "KCoefficient" in out.columns:
        k_vals = out["KCoefficient"].to_numpy(dtype=np.float64)
        ambient_comp = _clip01(np.nan_to_num(-k_vals, nan=0.0) / max(k_scale, 1e-6))
    else:
        ambient_comp = np.zeros(len(out), dtype=np.float64)

    total_w = max(w_ent + w_switch + w_k, 1e-6)
    score = (w_ent * entropy_comp + w_switch * switch_comp + w_k * ambient_comp) / total_w

    out["ConfusionScore"] = score.astype(np.float32)
    out["Confusion"] = (score >= score_thr)

    out.attrs["confusion_score_threshold"] = score_thr
    return out


def build_confusion_episodes(
    df: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    """
    Agrupa amostras ``Confusion`` em episódios contíguos.

    Une lacunas curtas (``merge_gap_seconds``) e descarta episódios menores
    que ``min_episode_seconds``. Retorna início, fim, duração, atividade,
    entropia média e nº de alvos distintos varridos no episódio.
    """
    cols = [
        "start_s",
        "end_s",
        "duration_s",
        "activity",
        "mean_gaze_entropy_bits",
        "mean_transition_entropy_bits",
        "mean_k_coefficient",
        "mean_confusion_score",
        "n_targets_scanned",
        "targets",
    ]
    if df.empty or "Confusion" not in df.columns or not df["Confusion"].any():
        return pd.DataFrame(columns=cols)

    conf_cfg = config.get("confusion", {})
    merge_gap = float(conf_cfg.get("merge_gap_seconds", 0.6))
    min_episode = float(conf_cfg.get("min_episode_seconds", 1.5))

    ordered = df.sort_values("SessionTime").reset_index(drop=True)
    times = ordered["SessionTime"].to_numpy(dtype=float)
    mask = ordered["Confusion"].to_numpy(dtype=bool)

    raw: list[tuple[int, int]] = []
    start_idx = None
    for i, flag in enumerate(mask):
        if flag and start_idx is None:
            start_idx = i
        elif not flag and start_idx is not None:
            raw.append((start_idx, i - 1))
            start_idx = None
    if start_idx is not None:
        raw.append((start_idx, len(mask) - 1))

    if not raw:
        return pd.DataFrame(columns=cols)

    merged: list[tuple[int, int]] = [raw[0]]
    for s, e in raw[1:]:
        prev_s, prev_e = merged[-1]
        if times[s] - times[prev_e] <= merge_gap:
            merged[-1] = (prev_s, e)
        else:
            merged.append((s, e))

    rows = []
    for s, e in merged:
        duration = float(times[e] - times[s])
        if duration < min_episode:
            continue
        block = ordered.iloc[s : e + 1]
        targets = [
            t for t in block["Target"].astype(str).unique().tolist()
            if t not in ("None", "nan")
        ]
        activity = (
            block["Activity"].astype(str).mode().iloc[0]
            if "Activity" in block.columns and not block["Activity"].empty
            else ""
        )
        mean_entropy = (
            float(block["GazeEntropy"].mean())
            if "GazeEntropy" in block.columns
            else float("nan")
        )
        mean_k = (
            float(block["KCoefficient"].mean())
            if "KCoefficient" in block.columns
            else float("nan")
        )
        mean_score = (
            float(block["ConfusionScore"].mean())
            if "ConfusionScore" in block.columns
            else float("nan")
        )
        rows.append(
            {
                "start_s": float(times[s]),
                "end_s": float(times[e]),
                "duration_s": duration,
                "activity": activity,
                "mean_gaze_entropy_bits": mean_entropy,
                "mean_transition_entropy_bits": float(
                    df.attrs.get("transition_gaze_entropy", float("nan"))
                ),
                "mean_k_coefficient": mean_k,
                "mean_confusion_score": mean_score,
                "n_targets_scanned": len(targets),
                "targets": "|".join(targets),
            }
        )

    return pd.DataFrame(rows, columns=cols)


def compute_gaze_metrics(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Pipeline completo do Passo 3."""
    out = add_voi_category(df, config)
    out = compute_gaze_entropy(out, config)
    out = compute_target_switch_rate(out, config)

    out, fixations = detect_fixations(out, config)
    out, fixations = compute_k_coefficient(out, fixations)
    out = compute_gaze_transition_entropy(out, config)
    out.attrs["fixations_table"] = fixations

    # Sacada de socorro agora depende das fixações (consulta ao tutorial).
    out = detect_rescue_saccades(out, fixations, config)
    out = detect_confusion(out, config)
    return out
