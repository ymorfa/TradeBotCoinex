import os
import sys
import unittest
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from coinex_client import CoinExClient  # noqa: E402


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


class CoinExClientLiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base_url = os.getenv("COINEX_BASE_URL", "https://api.coinex.com")
        self.market_fallback = os.getenv("COINEX_TEST_MARKET", "BTCUSDT")

    def test_get_markets(self) -> None:
        client = CoinExClient("public", "public", base_url=self.base_url)
        response = client.get_markets()
        self.assertIsNotNone(response)
        print("get_markets response:", response)

    def test_get_orderbook(self) -> None:
        client = CoinExClient("public", "public", base_url=self.base_url)
        markets = client.get_markets()
        symbol = _extract_market(markets, self.market_fallback)
        response = client.get_orderbook(symbol, limit=5)
        self.assertIsNotNone(response)
        print(f"get_orderbook response ({symbol}):", response)

    def test_get_balance(self) -> None:
        api_key = _get_env("ACCESS_ID", "COINEX_API_KEY", "API_KEY")
        api_secret = _get_env("SECRET_KEY", "COINEX_API_SECRET", "API_SECRET")
        if not api_key or not api_secret:
            self.skipTest("Missing CoinEx API credentials in environment.")
        client = CoinExClient(api_key, api_secret, base_url=self.base_url)
        response = client.get_balance()
        self.assertIsNotNone(response)
        print("get_balance response:", response)


if __name__ == "__main__":
    unittest.main()
