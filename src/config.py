from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

CONFIG_DIR = Path(__file__).parent.parent / "config"
DEFAULT_CONFIG = CONFIG_DIR / "config.yaml"
PROJECT_ROOT = Path(__file__).parent.parent


def load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_CONFIG
    with open(path) as f:
        return yaml.safe_load(f)


def get_data_dir(config: dict) -> Path:
    return (PROJECT_ROOT / config["data"]["input_dir"]).resolve()


def get_cache_dir(config: dict) -> Path:
    return (PROJECT_ROOT / config["data"]["cache_dir"]).resolve()


def get_reports_dir(config: dict) -> Path:
    return (PROJECT_ROOT / config["data"]["reports_dir"]).resolve()
