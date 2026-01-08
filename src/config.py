from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple, Union
import os


class ConfigError(ValueError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Secrets:
    api_key: str
    api_secret: str


@dataclass(frozen=True)
class Limits:
    max_position_usdt: float
    max_order_usdt: float
    max_daily_loss_pct: float


@dataclass(frozen=True)
class Config:
    env: str
    symbols: Tuple[str, ...]
    timeframes: Tuple[str, ...]
    limits: Limits
    secrets: Secrets


def load_config(dotenv_path: Optional[Union[str, Path]] = ".env") -> Config:
    """Load and validate configuration from .env and environment variables."""
    _load_dotenv(dotenv_path)

    errors: list[str] = []
    api_key = _require_env(
        "ACCESS_ID",
        errors,
        fallback_keys=("COINEX_API_KEY", "API_KEY"),
    )
    api_secret = _require_env(
        "SECRET_KEY",
        errors,
        fallback_keys=("COINEX_API_SECRET", "API_SECRET"),
    )
    env_value = _require_env("TRADING_ENV", errors)
    symbols_raw = _require_env("SYMBOLS", errors)
    timeframes_raw = _require_env("TIMEFRAMES", errors)
    max_position_raw = _require_env("MAX_POSITION_USDT", errors)
    max_order_raw = _require_env("MAX_ORDER_USDT", errors)
    max_daily_loss_raw = _require_env("MAX_DAILY_LOSS_PCT", errors)

    env = ""
    if env_value is not None:
        env = env_value.strip().lower()
        if env not in ("paper", "live"):
            errors.append("TRADING_ENV must be 'paper' or 'live'.")

    symbols = _parse_list(symbols_raw, "SYMBOLS", errors)
    timeframes = _parse_list(timeframes_raw, "TIMEFRAMES", errors)
    max_position = _parse_float(max_position_raw, "MAX_POSITION_USDT", errors)
    max_order = _parse_float(max_order_raw, "MAX_ORDER_USDT", errors)
    max_daily_loss = _parse_float(
        max_daily_loss_raw,
        "MAX_DAILY_LOSS_PCT",
        errors,
        min_value=0.0,
        max_value=100.0,
    )

    if max_order is not None and max_position is not None:
        if max_order > max_position:
            errors.append("MAX_ORDER_USDT cannot exceed MAX_POSITION_USDT.")

    if errors:
        raise ConfigError("Config validation failed:\n- " + "\n- ".join(errors))

    limits = Limits(
        max_position_usdt=max_position,
        max_order_usdt=max_order,
        max_daily_loss_pct=max_daily_loss,
    )
    secrets = Secrets(api_key=api_key, api_secret=api_secret)
    return Config(
        env=env,
        symbols=symbols,
        timeframes=timeframes,
        limits=limits,
        secrets=secrets,
    )


def _load_dotenv(dotenv_path: Optional[Union[str, Path]]) -> None:
    if dotenv_path is None:
        return
    path = Path(dotenv_path)
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if (value.startswith("'") and value.endswith("'")) or (
            value.startswith('"') and value.endswith('"')
        ):
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value


def _require_env(
    key: str,
    errors: list[str],
    fallback_keys: Sequence[str] = (),
) -> Optional[str]:
    for candidate in (key, *fallback_keys):
        value = os.getenv(candidate)
        if value:
            return value
    if fallback_keys:
        names = ", ".join((key, *fallback_keys))
    else:
        names = key
    errors.append(f"Missing required env var: {names}.")
    return None


def _parse_list(raw: Optional[str], name: str, errors: list[str]) -> Tuple[str, ...]:
    if raw is None:
        return tuple()
    items = [item.strip() for item in raw.split(",") if item.strip()]
    if not items:
        errors.append(f"{name} must include at least one entry.")
    return tuple(items)


def _parse_float(
    raw: Optional[str],
    name: str,
    errors: list[str],
    min_value: Optional[float] = 0.0,
    max_value: Optional[float] = None,
) -> Optional[float]:
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        errors.append(f"{name} must be a number.")
        return None
    if min_value is not None and value <= min_value:
        errors.append(f"{name} must be greater than {min_value}.")
    if max_value is not None and value > max_value:
        errors.append(f"{name} must be less than or equal to {max_value}.")
    return value
