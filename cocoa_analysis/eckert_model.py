"""
Passo 2: modelo de correção PLR no estilo Eckert et al. (QoMEX 2021 / ACM 2022).

Referências:
- Eckert, M., Habets, E.A.P., Rummukainen, O.S. (2021). Cognitive load estimation
  based on pupillometry in virtual reality with uncontrolled scene lighting.
- Eckert, M., Robotham, T., Habets, E., Rummukainen, O.S. (2022). Pupillary Light
  Reflex Correction for Robust Pupillometry in Virtual Reality.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from scipy import signal
from scipy.optimize import curve_fit


@dataclass
class PLRParams:
    """Parâmetros do mapeamento luminância → diâmetro pupilar."""

    model: str
    baseline: float
    k: float = 0.15
    epsilon: float = 0.01
    poly_coeffs: tuple[float, ...] | None = None
    sigmoid_params: tuple[float, float, float] | None = None

    def predict(self, luminance: np.ndarray) -> np.ndarray:
        l = np.asarray(luminance, dtype=np.float64)
        if self.model == "log":
            return self.baseline - self.k * np.log10(l + self.epsilon)
        if self.model == "poly2" and self.poly_coeffs is not None:
            return np.polyval(self.poly_coeffs, l)
        if self.model == "sigmoid" and self.sigmoid_params is not None:
            a, b, c = self.sigmoid_params
            return a / (1.0 + np.exp(-b * (l - c)))
        return self.baseline - self.k * np.log10(l + self.epsilon)


def _log_model(l: np.ndarray, baseline: float, k: float) -> np.ndarray:
    return baseline - k * np.log10(l + 1e-2)


def _sigmoid_model(l: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
    return a / (1.0 + np.exp(-b * (l - c)))


def load_calibration_params(
    calibration_path: str | Path,
    model: str = "log",
) -> PLRParams:
    """
    Ajusta função luminância→pupila a partir de CSV de calibração Eckert.

    CSV esperado: colunas ``luminance`` e ``pupil_diameter``.
    """
    cal = pd.read_csv(calibration_path)
    if "luminance" not in cal.columns or "pupil_diameter" not in cal.columns:
        raise ValueError(
            "CSV de calibração deve conter colunas 'luminance' e 'pupil_diameter'."
        )

    l = cal["luminance"].to_numpy(dtype=np.float64)
    d = cal["pupil_diameter"].to_numpy(dtype=np.float64)

    if model == "log":
        popt, _ = curve_fit(_log_model, l, d, p0=[float(np.median(d)), 0.15], maxfev=5000)
        return PLRParams(model="log", baseline=float(popt[0]), k=float(popt[1]))

    if model == "poly2":
        coeffs = np.polyfit(l, d, deg=2)
        return PLRParams(
            model="poly2",
            baseline=float(coeffs[-1]),
            poly_coeffs=tuple(float(c) for c in coeffs),
        )

    if model == "sigmoid":
        popt, _ = curve_fit(
            _sigmoid_model,
            l,
            d,
            p0=[float(np.max(d)), 5.0, float(np.median(l))],
            maxfev=10000,
        )
        return PLRParams(
            model="sigmoid",
            baseline=float(popt[0]),
            sigmoid_params=(float(popt[0]), float(popt[1]), float(popt[2])),
        )

    raise ValueError(f"Modelo de calibração desconhecido: {model}")


def resolve_luminance(
    target: str,
    aoi: str,
    luminance_map: dict[str, float],
    default: float = 0.5,
) -> float:
    """Resolve luminância relativa por Target, com fallback para AOI e default."""
    if target in luminance_map:
        return float(luminance_map[target])
    if aoi in luminance_map:
        return float(luminance_map[aoi])
    return float(luminance_map.get("default", default))


def compute_effective_luminance(
    df: pd.DataFrame,
    config: dict[str, Any],
) -> pd.Series:
    """
    L_eff = w_fix * L_target + (1 - w_fix) * L_background (Eckert et al., 2022).
    """
    eckert_cfg = config["eckert"]
    lum_map = config["luminance_map"]
    w_fix = float(eckert_cfg["w_fix"])
    l_bg = float(eckert_cfg["l_background"])

    l_target = df.apply(
        lambda row: resolve_luminance(
            str(row["Target"]),
            str(row["AOI"]),
            lum_map,
        ),
        axis=1,
    )
    return w_fix * l_target + (1.0 - w_fix) * l_bg


def estimate_baseline(
    df: pd.DataFrame,
    baseline_seconds: float,
) -> float:
    """Mediana de AvgPupil nos primeiros N segundos da sessão."""
    t0 = df["SessionTime"].min()
    window = df[df["SessionTime"] <= t0 + baseline_seconds]
    if window.empty:
        return float(df["AvgPupil"].median())
    return float(window["AvgPupil"].median())


def butterworth_lowpass(
    values: np.ndarray,
    fs: float,
    cutoff_hz: float,
) -> np.ndarray:
    """Filtro passa-baixa Butterworth para modelar latência do PLR."""
    if len(values) < 12 or cutoff_hz <= 0:
        return values.copy()

    nyquist = fs / 2.0
    normalized_cutoff = min(cutoff_hz / nyquist, 0.99)
    b, a = signal.butter(2, normalized_cutoff, btype="low")
    return signal.filtfilt(b, a, values)


def apply_eckert_plr(
    df: pd.DataFrame,
    config: dict[str, Any],
    calibration_path: str | Path | None = None,
) -> pd.DataFrame:
    """
    Calcula luminância efetiva, pupila predita (PLR) e ResidualPupil (Δd).

    ResidualPupil = AvgPupil - PredictedPupil
    Isola componente cognitiva após remover reflexo fotomotor.
    """
    out = df.copy()
    eckert_cfg = config["eckert"]
    fs = float(config.get("sampling_rate_hz", 120))

    out["EffectiveLuminance"] = compute_effective_luminance(out, config)

    if calibration_path is not None:
        params = load_calibration_params(
            calibration_path,
            model=eckert_cfg.get("calibration_model", "log"),
        )
    else:
        params = PLRParams(
            model="log",
            baseline=estimate_baseline(out, float(eckert_cfg["baseline_seconds"])),
            k=float(eckert_cfg["plr_k"]),
            epsilon=float(eckert_cfg["plr_epsilon"]),
        )

    l_vals = out["EffectiveLuminance"].to_numpy(dtype=np.float64)
    predicted = params.predict(l_vals)
    predicted = butterworth_lowpass(
        predicted,
        fs=fs,
        cutoff_hz=float(eckert_cfg["plr_lowpass_hz"]),
    )

    out["PredictedPupil"] = predicted.astype(np.float32)
    out["ResidualPupil"] = (out["AvgPupil"] - out["PredictedPupil"]).astype(np.float32)

    observed = out["AvgPupil"].to_numpy(dtype=np.float64)
    fit = observed - predicted
    valid = np.isfinite(observed) & np.isfinite(predicted)
    if valid.sum() >= 2:
        residuals = fit[valid]
        rmse = float(np.sqrt(np.mean(residuals ** 2)))
        ss_res = float(np.sum(residuals ** 2))
        obs_valid = observed[valid]
        ss_tot = float(np.sum((obs_valid - obs_valid.mean()) ** 2))
        r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")
    else:
        rmse = float("nan")
        r2 = float("nan")

    out.attrs["plr_params"] = {
        "model": params.model,
        "baseline": params.baseline,
        "k": params.k,
        "epsilon": params.epsilon,
        "calibrated": calibration_path is not None,
        "w_fix": float(eckert_cfg["w_fix"]),
        "l_background": float(eckert_cfg["l_background"]),
        "plr_lowpass_hz": float(eckert_cfg["plr_lowpass_hz"]),
        "rmse_mm": rmse,
        "r2": r2,
        "n_samples": int(valid.sum()),
    }
    return out
