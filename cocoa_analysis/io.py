"""Leitura, validação e carregamento de configuração."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

REQUIRED_COLUMNS = [
    "SessionTime",
    "Phase",
    "Activity",
    "Target",
    "TargetInstanceId",
    "AOI",
    "HitX",
    "HitY",
    "HitZ",
    "HitNormalX",
    "HitNormalY",
    "HitNormalZ",
    "Distance",
    "OriginX",
    "OriginY",
    "OriginZ",
    "DirX",
    "DirY",
    "DirZ",
    "LeftOpenness",
    "RightOpenness",
    "IsBlink",
    "LeftPupil",
    "RightPupil",
    "AvgPupil",
    "LeftPupilValid",
    "RightPupilValid",
    "LeftGazeValid",
    "RightGazeValid",
    "IsTracking",
    "TargetChanged",
    "DwellTime",
]

DTYPES: dict[str, str | type] = {
    "SessionTime": "float32",
    "Phase": "category",
    "Activity": "category",
    "Target": "category",
    "TargetInstanceId": "int32",
    "AOI": "category",
    "HitX": "float32",
    "HitY": "float32",
    "HitZ": "float32",
    "HitNormalX": "float32",
    "HitNormalY": "float32",
    "HitNormalZ": "float32",
    "Distance": "float32",
    "OriginX": "float32",
    "OriginY": "float32",
    "OriginZ": "float32",
    "DirX": "float32",
    "DirY": "float32",
    "DirZ": "float32",
    "LeftOpenness": "float32",
    "RightOpenness": "float32",
    "IsBlink": "bool",
    "LeftPupil": "float32",
    "RightPupil": "float32",
    "AvgPupil": "float32",
    "LeftPupilValid": "bool",
    "RightPupilValid": "bool",
    "LeftGazeValid": "bool",
    "RightGazeValid": "bool",
    "IsTracking": "bool",
    "TargetChanged": "bool",
    "DwellTime": "float32",
}


def load_config(config_path: str | Path) -> dict[str, Any]:
    """Carrega arquivo YAML de configuração."""
    path = Path(config_path)
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_eyetracking_csv(csv_path: str | Path) -> pd.DataFrame:
    """
    Carrega CSV de eye-tracking com dtypes otimizados para arquivos volumosos (120 Hz).

    Raises
    ------
    ValueError
        Se colunas obrigatórias estiverem ausentes.
    """
    path = Path(csv_path)
    header_cols = pd.read_csv(path, nrows=0).columns.tolist()

    read_dtypes = {k: v for k, v in DTYPES.items() if k in header_cols}
    df = pd.read_csv(path, dtype=read_dtypes, low_memory=False)

    if "Activity" not in df.columns:
        df["Activity"] = "Sessao"
        df["Activity"] = df["Activity"].astype("category")

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Colunas ausentes no CSV: {missing}")

    bool_cols = [
        "IsBlink",
        "LeftPupilValid",
        "RightPupilValid",
        "LeftGazeValid",
        "RightGazeValid",
        "IsTracking",
        "TargetChanged",
    ]
    for col in bool_cols:
        df[col] = df[col].astype(bool)

    df = df.sort_values("SessionTime").reset_index(drop=True)
    return df
