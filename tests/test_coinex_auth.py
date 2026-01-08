import hashlib
import hmac
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from coinex_client import CoinExSigner  # noqa: E402


class CoinExAuthTests(unittest.TestCase):
    def test_signature_includes_sorted_query(self) -> None:
        signer = CoinExSigner("key", "secret", time_fn=lambda: 1700000000.123)
        timestamp = "1700000000123"
        payload = (
            f"GET/v2/spot/market?limit=2&market=BTCUSDT{timestamp}"
        )
        expected = hmac.new(
            b"secret",
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        signature, used_ts = signer.build_signature(
            "GET",
            "/spot/market",
            params={"market": "BTCUSDT", "limit": 2},
            timestamp=timestamp,
        )

        self.assertEqual(used_ts, timestamp)
        self.assertEqual(signature, expected)

    def test_headers_include_auth_fields(self) -> None:
        signer = CoinExSigner("access", "secret", time_fn=lambda: 1700000000.0)
        headers = signer.build_headers(
            "GET",
            "/spot/market",
            params={"market": "BTCUSDT"},
        )

        self.assertEqual(headers["X-COINEX-KEY"], "access")
        self.assertEqual(headers["X-COINEX-TIMESTAMP"], "1700000000000")
        self.assertIn("X-COINEX-SIGN", headers)
        self.assertEqual(headers["Content-Type"], "application/json")


if __name__ == "__main__":
    unittest.main()
