#!/usr/bin/env python3
import os
from pathlib import Path
import tomllib


def load_config(path=None):
    if path:
        config_path = Path(path)
    else:
        config_path = Path(os.environ.get("CRI_CONFIG", Path(__file__).with_name("config.toml")))

    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    data["_root"] = str(config_path.parent)
    data["_config_path"] = str(config_path)
    return data


def resolve_from_root(config, relative_path):
    return Path(config["_root"]) / relative_path


def get_path(config, key, section="paths"):
    value = config.get(section, {}).get(key)
    if value is None:
        raise KeyError(f"Missing config key: {section}.{key}")
    return resolve_from_root(config, value)
