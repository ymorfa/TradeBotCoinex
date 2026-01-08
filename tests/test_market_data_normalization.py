import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from market_data import (  # noqa: E402
    InMemoryMarketDataCache,
    OHLCVBar,
    OrderBookLevel,
    OrderBookSnapshot,
    normalize_ohlcv,
    normalize_orderbook,
    normalize_trades,
)


class MarketDataNormalizationTests(unittest.TestCase):
    def test_normalize_trades(self) -> None:
        payload = {
            "code": 0,
            "data": [
                {
                    "amount": "0.00334902",
                    "created_at": 1767895749049,
                    "deal_id": 6327323683,
                    "price": "91288",
                    "side": "sell",
                }
            ],
            "message": "OK",
        }
        trades = normalize_trades(payload, "BTCUSDT")
        self.assertEqual(len(trades), 1)
        trade = trades[0]
        self.assertEqual(trade.symbol, "BTCUSDT")
        self.assertEqual(trade.trade_id, "6327323683")
        self.assertEqual(trade.side, "sell")
        self.assertEqual(trade.price, 91288.0)
        self.assertEqual(trade.amount, 0.00334902)
        self.assertEqual(trade.timestamp_ms, 1767895749049)

    def test_normalize_ohlcv(self) -> None:
        payload = {
            "code": 0,
            "data": [
                {
                    "close": "91273",
                    "created_at": 1767895500000,
                    "high": "91371",
                    "low": "91272",
                    "market": "BTCUSDT",
                    "open": "91348",
                    "value": "48933.82820726",
                    "volume": "0.53571687",
                }
            ],
            "message": "OK",
        }
        bars = normalize_ohlcv(payload, "BTCUSDT", "1min")
        self.assertEqual(len(bars), 1)
        bar = bars[0]
        self.assertEqual(bar.symbol, "BTCUSDT")
        self.assertEqual(bar.timeframe, "1min")
        self.assertEqual(bar.timestamp_ms, 1767895500000)
        self.assertEqual(bar.open, 91348.0)
        self.assertEqual(bar.high, 91371.0)
        self.assertEqual(bar.low, 91272.0)
        self.assertEqual(bar.close, 91273.0)
        self.assertEqual(bar.volume, 0.53571687)

    def test_normalize_orderbook(self) -> None:
        payload = {
            "code": 0,
            "data": {
                "depth": {
                    "asks": [["91289", "0.02492163"]],
                    "bids": [["91288", "1.42649982"]],
                    "checksum": 2896762209,
                    "last": "91288",
                    "updated_at": 1767895746575,
                },
                "is_full": True,
                "market": "BTCUSDT",
            },
            "message": "OK",
        }
        snapshot = normalize_orderbook(payload, "BTCUSDT")
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.symbol, "BTCUSDT")
        self.assertEqual(snapshot.timestamp_ms, 1767895746575)
        self.assertEqual(snapshot.checksum, 2896762209)
        self.assertEqual(snapshot.bids[0].price, 91288.0)
        self.assertEqual(snapshot.bids[0].amount, 1.42649982)
        self.assertEqual(snapshot.asks[0].price, 91289.0)

    def test_inmemory_cache(self) -> None:
        cache = InMemoryMarketDataCache(max_trades=2, max_ohlcv=2)
        snapshot = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp_ms=1700000000000,
            bids=(OrderBookLevel(price=1.0, amount=2.0),),
            asks=(OrderBookLevel(price=1.1, amount=3.0),),
        )
        cache.set_orderbook_snapshot(snapshot)
        self.assertEqual(cache.get_orderbook_snapshot("BTCUSDT"), snapshot)

        bars = [
            OHLCVBar(
                symbol="BTCUSDT",
                timeframe="1min",
                timestamp_ms=1,
                open=1.0,
                high=1.0,
                low=1.0,
                close=1.0,
                volume=1.0,
            ),
            OHLCVBar(
                symbol="BTCUSDT",
                timeframe="1min",
                timestamp_ms=2,
                open=2.0,
                high=2.0,
                low=2.0,
                close=2.0,
                volume=2.0,
            ),
        ]
        cache.set_ohlcv_bars("BTCUSDT", "1min", bars)
        self.assertEqual(len(cache.get_ohlcv_bars("BTCUSDT", "1min")), 2)


if __name__ == "__main__":
    unittest.main()
