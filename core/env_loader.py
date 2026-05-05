import os
from pathlib import Path


def load_env_file(path: str = ".env") -> dict:
    env_path = Path(path)
    loaded = {}
    if not env_path.exists():
        return loaded

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        loaded[key] = value
        os.environ.setdefault(key, value)
    return loaded


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value or value.startswith("YOUR_"):
        raise RuntimeError(f"Missing required .env value: {name}")
    return value


def apply_env_config(cfg: dict) -> dict:
    cfg = cfg or {}
    cfg.setdefault("exchange", {})
    cfg.setdefault("ai", {})
    cfg.setdefault("proxy", {})
    cfg.setdefault("external_apis", {})

    cfg["exchange"]["api_key"] = require_env("OKX_API_KEY")
    cfg["exchange"]["secret_key"] = require_env("OKX_SECRET_KEY")
    cfg["exchange"]["passphrase"] = require_env("OKX_PASSPHRASE")
    cfg["exchange"]["testnet"] = env_bool("OKX_TESTNET", True)

    cfg["ai"]["base_url"] = require_env("LLM_BASE_URL")
    cfg["ai"]["api_key"] = require_env("LLM_API_KEY")
    cfg["ai"]["model"] = require_env("LLM_MODEL")

    cfg["proxy"]["http"] = os.environ.get("HTTP_PROXY_URL", "").strip()
    cfg["proxy"]["https"] = os.environ.get("HTTPS_PROXY_URL", "").strip()

    cfg["external_apis"]["cryptopanic_token"] = os.environ.get("CRYPTOPANIC_TOKEN", "").strip()
    cfg["external_apis"]["coingecko_demo_key"] = os.environ.get("COINGECKO_DEMO_KEY", "").strip()
    return cfg
