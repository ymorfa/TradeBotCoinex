import os
from pathlib import Path
from typing import Any, Optional
from src.coinex_client import CoinExClient  # noqa: E402
from src.config import _load_dotenv  # noqa: E402


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

        


if __name__ == "__main__":
    _load_dotenv(Path(__file__).with_name(".env"))
    base_url = os.getenv("COINEX_BASE_URL", "https://api.coinex.com")
    market_fallback = os.getenv("COINEX_TEST_MARKET", "BTCUSDT")
    api_key = _get_env("ACCESS_ID", "COINEX_API_KEY", "API_KEY")
    api_secret = _get_env("SECRET_KEY", "COINEX_API_SECRET", "API_SECRET")

    client = CoinExClient("public", "public", base_url=base_url)

    # markets = client.get_markets()
    # symbol = _extract_market(markets, market_fallback)
    # response = client.get_orderbook(symbol, limit=5)
    # print(f"get_orderbook response ({symbol}):", response)

    if not api_key or not api_secret:
        raise SystemExit(
            "Missing CoinEx API credentials. "
            "Set ACCESS_ID/SECRET_KEY (or COINEX_API_KEY/COINEX_API_SECRET) "
            "in .env or the environment."
        )

    client = CoinExClient(api_key, api_secret, base_url=base_url)
    response = client.get_balance()
    print("get_balance response:", response)

    
    
