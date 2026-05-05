import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.env_loader import load_env_file
from core.exchange import OKXExchange
from loop import load_config, load_state, run_once, save_state


def main() -> None:
    load_env_file(".env")
    cfg = load_config()
    state = load_state()
    exchange = OKXExchange(cfg["exchange"], proxy=cfg.get("proxy", {}))
    run_once(exchange, cfg, state)
    save_state(state)


if __name__ == "__main__":
    main()
