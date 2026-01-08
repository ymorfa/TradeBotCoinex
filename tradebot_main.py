import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    from prettytable import PrettyTable
except ImportError as exc:
    raise RuntimeError(
        "prettytable is required. Install it with: pip install prettytable"
    ) from exc
from src.coinex_client import CoinExClient  # noqa: E402
from src.config import ConfigError, _load_dotenv, load_config  # noqa: E402
from src.market_data import (  # noqa: E402
    InMemoryMarketDataCache,
    MarketDataMonitor,
    MarketDataPollConfig,
)


def _get_env(*keys: str) -> Optional[str]:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return None


def _extract_market(response: Any, fallback: str) -> str:
    if isinstance(response, dict):
        data = response.get("data")
        if isinstance(data, dict):
            entries = data.get("list")
            if isinstance(entries, list) and entries:
                first = entries[0]
                if isinstance(first, dict):
                    return (
                        first.get("market")
                        or first.get("symbol")
                        or first.get("name")
                        or fallback
                    )
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                return (
                    first.get("market")
                    or first.get("symbol")
                    or first.get("name")
                    or fallback
                )
    if isinstance(response, list) and response:
        first = response[0]
        if isinstance(first, dict):
            return (
                first.get("market")
                or first.get("symbol")
                or first.get("name")
                or fallback
            )
    return fallback

        

def _parse_list_env(key: str) -> list[str]:
    raw = os.getenv(key)
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_positive_float_env(key: str, default: float) -> float:
    raw = os.getenv(key)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if value <= 0:
        return default
    return value


def _format_price(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value:.8f}".rstrip("0").rstrip(".")


def _build_price_table(
    symbols: list[str], timeframes: list[str], cache: InMemoryMarketDataCache
) -> PrettyTable:
    table = PrettyTable()
    table.field_names = ["symbol", *timeframes]
    table.align = "l"
    for symbol in symbols:
        row = [symbol]
        for timeframe in timeframes:
            bars = cache.get_ohlcv_bars(symbol, timeframe)
            last_close = bars[-1].close if bars else None
            row.append(_format_price(last_close))
        table.add_row(row)
    return table


def _poll_ohlcv_history(
    monitor: MarketDataMonitor, symbols: list[str], timeframes: list[str]
) -> None:
    for symbol in symbols:
        for timeframe in timeframes:
            try:
                monitor.poll_ohlcv(symbol, timeframe)
            except Exception as exc:
                print(f"Error polling {symbol} {timeframe}: {exc}")


def main() -> None:
    _load_dotenv(Path(__file__).with_name(".env"))
    base_url = os.getenv("COINEX_BASE_URL", "https://api.coinex.com")
    market_fallback = os.getenv("COINEX_TEST_MARKET", "BTCUSDT")
    api_key = _get_env("ACCESS_ID", "COINEX_API_KEY", "API_KEY") or "public"
    api_secret = _get_env("SECRET_KEY", "COINEX_API_SECRET", "API_SECRET") or "public"
    client = CoinExClient(api_key, api_secret, base_url=base_url)

    symbols: list[str] = []
    timeframes: list[str] = []
    try:
        config = load_config(Path(__file__).with_name(".env"))
        symbols = list(config.symbols)
        timeframes = list(config.timeframes)
    except ConfigError as exc:
        print("Config warning:", exc)
        symbols = _parse_list_env("SYMBOLS")
        timeframes = _parse_list_env("TIMEFRAMES")

    if not symbols:
        markets = client.get_markets()
        symbols = [_extract_market(markets, market_fallback)]
    if not timeframes:
        timeframes = [os.getenv("COINEX_TIMEFRAME", "1min")]

    cache = InMemoryMarketDataCache()
    monitor = MarketDataMonitor(
        client,
        cache,
        symbols=symbols,
        timeframes=timeframes,
        poll_config=MarketDataPollConfig(),
    )

    interval_minutes = _parse_positive_float_env("MONITOR_INTERVAL_MINUTES", 5.0)
    interval_seconds = interval_minutes * 60.0

    _poll_ohlcv_history(monitor, symbols, timeframes)
    print(f"[{datetime.now().isoformat(timespec='seconds')}] OHLCV snapshot")
    print(_build_price_table(symbols, timeframes, cache))

    while True:
        time.sleep(interval_seconds)
        _poll_ohlcv_history(monitor, symbols, timeframes)
        print(f"[{datetime.now().isoformat(timespec='seconds')}] OHLCV snapshot")
        print(_build_price_table(symbols, timeframes, cache))


if __name__ == "__main__":
    main()


    
    
