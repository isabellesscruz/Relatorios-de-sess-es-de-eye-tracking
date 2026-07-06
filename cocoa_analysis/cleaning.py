"""Passo 1: limpeza de dados e tratamento de piscadas."""

from __future__ import annotations

import pandas as pd


def clean_blinks_and_tracking(
    df: pd.DataFrame,
    interp_method: str = "linear",
) -> pd.DataFrame:
    """
    Filtra amostras inválidas, marca piscadas e interpola AvgPupil.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame bruto carregado do CSV.
    interp_method : str
        ``linear`` ou ``spline`` (ordem 3).

    Returns
    -------
    pd.DataFrame
        Cópia filtrada com ``AvgPupil_raw`` e ``AvgPupil`` interpolado.
    """
    out = df.copy()
    n_before = len(out)

    valid_mask = (
        out["IsTracking"]
        & out["LeftPupilValid"]
        & out["RightPupilValid"]
    )
    out = out.loc[valid_mask].reset_index(drop=True)

    out["AvgPupil_raw"] = out["AvgPupil"].copy()
    out.loc[out["IsBlink"], "AvgPupil"] = pd.NA

    if interp_method == "spline":
        out["AvgPupil"] = out["AvgPupil"].interpolate(
            method="spline",
            order=3,
            limit_direction="both",
        )
    else:
        out["AvgPupil"] = out["AvgPupil"].interpolate(
            method="linear",
            limit_direction="both",
        )

    out.attrs["cleaning_stats"] = {
        "rows_before": n_before,
        "rows_after": len(out),
        "rows_removed": n_before - len(out),
        "blinks_masked": int(out["IsBlink"].sum()),
    }
    return out
