from __future__ import annotations
import functools
from pathlib import Path
from typing import Any
import yaml
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / 'configs'
DATA_DIR = REPO_ROOT / 'data'
ARTIFACT_DIR = REPO_ROOT / 'artifacts'

def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p

@functools.lru_cache(maxsize=None)
def load_config(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / f'{name}.yaml'
    if not path.exists():
        raise FileNotFoundError(f'config not found: {path}')
    with path.open(encoding='utf-8') as fh:
        return yaml.safe_load(fh)

def datasets() -> dict[str, Any]:
    return load_config('datasets')

def models() -> dict[str, Any]:
    return load_config('models')

def pipeline() -> dict[str, Any]:
    return load_config('pipeline')
