from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
import threading
import time
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

try:
    from .coinex_client import CoinExClient
except ImportError:  # pragma: no cover - fallback for direct module imports
    from coinex_client import CoinExClient


_TIMEFRAME_ALIASES = {
    "1m": "1min",
    "3m": "3min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1hour",
    "2h": "2hour",
    "4h": "4hour",
    "6h": "6hour",
    "12h": "12hour",
    "1d": "1day",
    "3d": "3day",
    "1w": "1week",
}


def normalize_timeframe(timeframe: str) -> str:
    return _TIMEFRAME_ALIASES.get(timeframe, timeframe)


@dataclass(frozen=True)
class NormalizedTrade:
    symbol: str
    trade_id: Optional[str]
    side: Optional[str]
    price: float
    amount: float
    timestamp_ms: int


@dataclass(frozen=True)
class OHLCVBar:
    symbol: str
    timeframe: str
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class OrderBookLevel:
    price: float
    amount: float


@dataclass(frozen=True)
class OrderBookSnapshot:
    symbol: str
    timestamp_ms: int
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]
    checksum: Optional[int] = None


def _extract_data_list(payload: Any) -> list[Any]:
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            list_value = data.get("list")
            if isinstance(list_value, list):
                return list_value
    if isinstance(payload, list):
        return payload
    return []


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return int(float(value))
        except ValueError:
            return None
    return None


def _coerce_timestamp_ms(value: Any) -> Optional[int]:
    number = _coerce_int(value)
    if number is None:
        return None
    if number < 100_000_000_000:
        return number * 1000
    return number


def normalize_trades(payload: Any, symbol: str) -> list[NormalizedTrade]:
    normalized: list[NormalizedTrade] = []
    for entry in _extract_data_list(payload):
        trade = _parse_trade_entry(entry, symbol)
        if trade is not None:
            normalized.append(trade)
    return normalized


def _parse_trade_entry(entry: Any, symbol: str) -> Optional[NormalizedTrade]:
    if isinstance(entry, Mapping):
        trade_id = entry.get("deal_id") or entry.get("trade_id") or entry.get("id")
        side = entry.get("side")
        price = _coerce_float(entry.get("price"))
        amount = _coerce_float(entry.get("amount") or entry.get("qty"))
        timestamp_ms = _coerce_timestamp_ms(
            entry.get("created_at")
            or entry.get("date_ms")
            or entry.get("timestamp")
            or entry.get("date")
        )
        if price is None or amount is None or timestamp_ms is None:
            return None
        return NormalizedTrade(
            symbol=symbol,
            trade_id=str(trade_id) if trade_id is not None else None,
            side=str(side) if side is not None else None,
            price=price,
            amount=amount,
            timestamp_ms=timestamp_ms,
        )
    if isinstance(entry, (list, tuple)):
        if len(entry) < 3:
            return None
        timestamp_ms = _coerce_timestamp_ms(entry[0])
        price = _coerce_float(entry[1])
        amount = _coerce_float(entry[2])
        side = entry[3] if len(entry) > 3 else None
        trade_id = entry[4] if len(entry) > 4 else None
        if price is None or amount is None or timestamp_ms is None:
            return None
        return NormalizedTrade(
            symbol=symbol,
            trade_id=str(trade_id) if trade_id is not None else None,
            side=str(side) if side is not None else None,
            price=price,
            amount=amount,
            timestamp_ms=timestamp_ms,
        )
    return None


def normalize_ohlcv(payload: Any, symbol: str, timeframe: str) -> list[OHLCVBar]:
    normalized: list[OHLCVBar] = []
    for entry in _extract_data_list(payload):
        bar = _parse_ohlcv_entry(entry, symbol, timeframe)
        if bar is not None:
            normalized.append(bar)
    return normalized


def _parse_ohlcv_entry(
    entry: Any, symbol: str, timeframe: str
) -> Optional[OHLCVBar]:
    if isinstance(entry, Mapping):
        timestamp_ms = _coerce_timestamp_ms(
            entry.get("created_at") or entry.get("timestamp") or entry.get("t")
        )
        open_value = _coerce_float(entry.get("open"))
        high_value = _coerce_float(entry.get("high"))
        low_value = _coerce_float(entry.get("low"))
        close_value = _coerce_float(entry.get("close"))
        volume = _coerce_float(entry.get("volume") or entry.get("amount"))
        if (
            timestamp_ms is None
            or open_value is None
            or high_value is None
            or low_value is None
            or close_value is None
            or volume is None
        ):
            return None
        return OHLCVBar(
            symbol=symbol,
            timeframe=timeframe,
            timestamp_ms=timestamp_ms,
            open=open_value,
            high=high_value,
            low=low_value,
            close=close_value,
            volume=volume,
        )
    if isinstance(entry, (list, tuple)):
        if len(entry) < 6:
            return None
        timestamp_ms = _coerce_timestamp_ms(entry[0])
        open_value = _coerce_float(entry[1])
        close_value = _coerce_float(entry[2])
        high_value = _coerce_float(entry[3])
        low_value = _coerce_float(entry[4])
        volume = _coerce_float(entry[5])
        if (
            timestamp_ms is None
            or open_value is None
            or high_value is None
            or low_value is None
            or close_value is None
            or volume is None
        ):
            return None
        return OHLCVBar(
            symbol=symbol,
            timeframe=timeframe,
            timestamp_ms=timestamp_ms,
            open=open_value,
            high=high_value,
            low=low_value,
            close=close_value,
            volume=volume,
        )
    return None


def normalize_orderbook(payload: Any, symbol: str) -> Optional[OrderBookSnapshot]:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    market = data.get("market") or symbol
    depth = data.get("depth")
    if isinstance(depth, dict):
        book = depth
    else:
        book = data
    bids = _parse_levels(book.get("bids"))
    asks = _parse_levels(book.get("asks"))
    timestamp_ms = _coerce_timestamp_ms(
        book.get("updated_at") or book.get("timestamp") or data.get("updated_at")
    )
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    checksum = _coerce_int(book.get("checksum"))
    return OrderBookSnapshot(
        symbol=market,
        timestamp_ms=timestamp_ms,
        bids=bids,
        asks=asks,
        checksum=checksum,
    )


def _parse_levels(entries: Any) -> tuple[OrderBookLevel, ...]:
    if not isinstance(entries, Iterable):
        return tuple()
    levels: list[OrderBookLevel] = []
    for entry in entries:
        if isinstance(entry, Mapping):
            price = _coerce_float(entry.get("price"))
            amount = _coerce_float(entry.get("amount") or entry.get("qty"))
        elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
            price = _coerce_float(entry[0])
            amount = _coerce_float(entry[1])
        else:
            continue
        if price is None or amount is None:
            continue
        levels.append(OrderBookLevel(price=price, amount=amount))
    return tuple(levels)


class MarketDataCache:
    def set_orderbook_snapshot(self, snapshot: OrderBookSnapshot) -> None:
        raise NotImplementedError

    def get_orderbook_snapshot(self, symbol: str) -> Optional[OrderBookSnapshot]:
        raise NotImplementedError

    def set_ohlcv_bars(
        self, symbol: str, timeframe: str, bars: Sequence[OHLCVBar]
    ) -> None:
        raise NotImplementedError

    def get_ohlcv_bars(self, symbol: str, timeframe: str) -> tuple[OHLCVBar, ...]:
        raise NotImplementedError

    def append_trades(self, symbol: str, trades: Sequence[NormalizedTrade]) -> int:
        raise NotImplementedError

    def get_trades(self, symbol: str) -> tuple[NormalizedTrade, ...]:
        raise NotImplementedError


class InMemoryMarketDataCache(MarketDataCache):
    def __init__(
        self,
        *,
        max_trades: int = 1000,
        max_ohlcv: int = 500,
    ) -> None:
        self._max_trades = max_trades
        self._max_ohlcv = max_ohlcv
        self._orderbooks: dict[str, OrderBookSnapshot] = {}
        self._ohlcv: dict[tuple[str, str], deque[OHLCVBar]] = {}
        self._trades: dict[str, deque[NormalizedTrade]] = {}
        self._lock = threading.Lock()

    def set_orderbook_snapshot(self, snapshot: OrderBookSnapshot) -> None:
        with self._lock:
            self._orderbooks[snapshot.symbol] = snapshot

    def get_orderbook_snapshot(self, symbol: str) -> Optional[OrderBookSnapshot]:
        with self._lock:
            return self._orderbooks.get(symbol)

    def set_ohlcv_bars(
        self, symbol: str, timeframe: str, bars: Sequence[OHLCVBar]
    ) -> None:
        key = (symbol, timeframe)
        with self._lock:
            existing = {bar.timestamp_ms: bar for bar in self._ohlcv.get(key, [])}
            for bar in bars:
                existing[bar.timestamp_ms] = bar
            merged = [existing[k] for k in sorted(existing)][-self._max_ohlcv :]
            self._ohlcv[key] = deque(merged, maxlen=self._max_ohlcv)

    def get_ohlcv_bars(self, symbol: str, timeframe: str) -> tuple[OHLCVBar, ...]:
        key = (symbol, timeframe)
        with self._lock:
            bars = self._ohlcv.get(key, deque())
            return tuple(bars)

    def append_trades(self, symbol: str, trades: Sequence[NormalizedTrade]) -> int:
        with self._lock:
            book = self._trades.get(symbol)
            if book is None:
                book = deque(maxlen=self._max_trades)
                self._trades[symbol] = book
            existing_ids = {
                trade.trade_id for trade in book if trade.trade_id is not None
            }
            added = 0
            for trade in trades:
                if trade.trade_id is not None and trade.trade_id in existing_ids:
                    continue
                book.append(trade)
                if trade.trade_id is not None:
                    existing_ids.add(trade.trade_id)
                added += 1
            return added

    def get_trades(self, symbol: str) -> tuple[NormalizedTrade, ...]:
        with self._lock:
            trades = self._trades.get(symbol, deque())
            return tuple(trades)


class RedisMarketDataCache(MarketDataCache):
    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        *,
        key_prefix: str = "market_data",
        max_trades: int = 1000,
        max_ohlcv: int = 500,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        try:
            import redis  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "redis package is required for RedisMarketDataCache"
            ) from exc
        self._redis = redis.Redis.from_url(url, decode_responses=True)
        self._prefix = key_prefix
        self._max_trades = max_trades
        self._max_ohlcv = max_ohlcv
        self._ttl_seconds = ttl_seconds

    def set_orderbook_snapshot(self, snapshot: OrderBookSnapshot) -> None:
        key = self._key_orderbook(snapshot.symbol)
        payload = json.dumps(_snapshot_to_dict(snapshot))
        self._redis.set(key, payload, ex=self._ttl_seconds)

    def get_orderbook_snapshot(self, symbol: str) -> Optional[OrderBookSnapshot]:
        raw = self._redis.get(self._key_orderbook(symbol))
        if not raw:
            return None
        return _snapshot_from_dict(json.loads(raw))

    def set_ohlcv_bars(
        self, symbol: str, timeframe: str, bars: Sequence[OHLCVBar]
    ) -> None:
        key = self._key_ohlcv(symbol, timeframe)
        payload = json.dumps([_ohlcv_to_dict(bar) for bar in bars][-self._max_ohlcv :])
        self._redis.set(key, payload, ex=self._ttl_seconds)

    def get_ohlcv_bars(self, symbol: str, timeframe: str) -> tuple[OHLCVBar, ...]:
        raw = self._redis.get(self._key_ohlcv(symbol, timeframe))
        if not raw:
            return tuple()
        return tuple(_ohlcv_from_dict(item) for item in json.loads(raw))

    def append_trades(self, symbol: str, trades: Sequence[NormalizedTrade]) -> int:
        key = self._key_trades(symbol)
        existing = self.get_trades(symbol)
        combined = list(existing) + list(trades)
        combined = combined[-self._max_trades :]
        payload = json.dumps([_trade_to_dict(trade) for trade in combined])
        self._redis.set(key, payload, ex=self._ttl_seconds)
        return max(0, len(combined) - len(existing))

    def get_trades(self, symbol: str) -> tuple[NormalizedTrade, ...]:
        raw = self._redis.get(self._key_trades(symbol))
        if not raw:
            return tuple()
        return tuple(_trade_from_dict(item) for item in json.loads(raw))

    def _key_orderbook(self, symbol: str) -> str:
        return f"{self._prefix}:orderbook:{symbol}"

    def _key_ohlcv(self, symbol: str, timeframe: str) -> str:
        return f"{self._prefix}:ohlcv:{symbol}:{timeframe}"

    def _key_trades(self, symbol: str) -> str:
        return f"{self._prefix}:trades:{symbol}"


def _trade_to_dict(trade: NormalizedTrade) -> dict[str, Any]:
    return {
        "symbol": trade.symbol,
        "trade_id": trade.trade_id,
        "side": trade.side,
        "price": trade.price,
        "amount": trade.amount,
        "timestamp_ms": trade.timestamp_ms,
    }


def _trade_from_dict(data: Mapping[str, Any]) -> NormalizedTrade:
    return NormalizedTrade(
        symbol=str(data["symbol"]),
        trade_id=data.get("trade_id"),
        side=data.get("side"),
        price=float(data["price"]),
        amount=float(data["amount"]),
        timestamp_ms=int(data["timestamp_ms"]),
    )


def _ohlcv_to_dict(bar: OHLCVBar) -> dict[str, Any]:
    return {
        "symbol": bar.symbol,
        "timeframe": bar.timeframe,
        "timestamp_ms": bar.timestamp_ms,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
    }


def _ohlcv_from_dict(data: Mapping[str, Any]) -> OHLCVBar:
    return OHLCVBar(
        symbol=str(data["symbol"]),
        timeframe=str(data["timeframe"]),
        timestamp_ms=int(data["timestamp_ms"]),
        open=float(data["open"]),
        high=float(data["high"]),
        low=float(data["low"]),
        close=float(data["close"]),
        volume=float(data["volume"]),
    )


def _snapshot_to_dict(snapshot: OrderBookSnapshot) -> dict[str, Any]:
    return {
        "symbol": snapshot.symbol,
        "timestamp_ms": snapshot.timestamp_ms,
        "checksum": snapshot.checksum,
        "bids": [[level.price, level.amount] for level in snapshot.bids],
        "asks": [[level.price, level.amount] for level in snapshot.asks],
    }


def _snapshot_from_dict(data: Mapping[str, Any]) -> OrderBookSnapshot:
    bids = tuple(
        OrderBookLevel(price=float(level[0]), amount=float(level[1]))
        for level in data.get("bids", [])
    )
    asks = tuple(
        OrderBookLevel(price=float(level[0]), amount=float(level[1]))
        for level in data.get("asks", [])
    )
    return OrderBookSnapshot(
        symbol=str(data["symbol"]),
        timestamp_ms=int(data["timestamp_ms"]),
        bids=bids,
        asks=asks,
        checksum=_coerce_int(data.get("checksum")),
    )


@dataclass(frozen=True)
class MarketDataPollConfig:
    trades_limit: int = 100
    orderbook_limit: int = 50
    ohlcv_limit: int = 200
    trades_interval_s: float = 2.0
    orderbook_interval_s: float = 2.0
    ohlcv_interval_s: float = 30.0
    orderbook_interval: str = "0"


class MarketDataMonitor:
    def __init__(
        self,
        client: CoinExClient,
        cache: MarketDataCache,
        *,
        symbols: Sequence[str],
        timeframes: Sequence[str],
        poll_config: Optional[MarketDataPollConfig] = None,
        on_trades: Optional[Callable[[str, Sequence[NormalizedTrade]], None]] = None,
        on_ohlcv: Optional[Callable[[str, str, Sequence[OHLCVBar]], None]] = None,
        on_orderbook: Optional[Callable[[str, OrderBookSnapshot], None]] = None,
        on_error: Optional[Callable[[str, Exception], None]] = None,
    ) -> None:
        self.client = client
        self.cache = cache
        self.symbols = tuple(symbols)
        self.timeframes = tuple(timeframes)
        self.poll_config = poll_config or MarketDataPollConfig()
        self.on_trades = on_trades
        self.on_ohlcv = on_ohlcv
        self.on_orderbook = on_orderbook
        self.on_error = on_error

    def poll_trades(self, symbol: str) -> list[NormalizedTrade]:
        raw = self.client.get_trades(symbol, limit=self.poll_config.trades_limit)
        trades = normalize_trades(raw, symbol)
        if trades:
            self.cache.append_trades(symbol, trades)
            if self.on_trades:
                self.on_trades(symbol, trades)
        return trades

    def poll_ohlcv(self, symbol: str, timeframe: str) -> list[OHLCVBar]:
        raw = self.client.get_ohlcv(
            symbol,
            period=normalize_timeframe(timeframe),
            limit=self.poll_config.ohlcv_limit,
        )
        bars = normalize_ohlcv(raw, symbol, timeframe)
        if bars:
            self.cache.set_ohlcv_bars(symbol, timeframe, bars)
            if self.on_ohlcv:
                self.on_ohlcv(symbol, timeframe, bars)
        return bars

    def poll_orderbook(self, symbol: str) -> Optional[OrderBookSnapshot]:
        raw = self.client.get_orderbook(
            symbol,
            limit=self.poll_config.orderbook_limit,
            interval=self.poll_config.orderbook_interval,
        )
        snapshot = normalize_orderbook(raw, symbol)
        if snapshot is not None:
            self.cache.set_orderbook_snapshot(snapshot)
            if self.on_orderbook:
                self.on_orderbook(symbol, snapshot)
        return snapshot

    def poll_once(self) -> None:
        for symbol in self.symbols:
            try:
                self.poll_trades(symbol)
            except Exception as exc:
                if self.on_error:
                    self.on_error(f"trades:{symbol}", exc)
            try:
                self.poll_orderbook(symbol)
            except Exception as exc:
                if self.on_error:
                    self.on_error(f"orderbook:{symbol}", exc)
            for timeframe in self.timeframes:
                try:
                    self.poll_ohlcv(symbol, timeframe)
                except Exception as exc:
                    if self.on_error:
                        self.on_error(f"ohlcv:{symbol}:{timeframe}", exc)

    def run(self, stop_event: threading.Event, *, sleep_s: float = 0.5) -> None:
        next_trades = {symbol: 0.0 for symbol in self.symbols}
        next_books = {symbol: 0.0 for symbol in self.symbols}
        next_ohlcv = {
            (symbol, timeframe): 0.0
            for symbol in self.symbols
            for timeframe in self.timeframes
        }
        while not stop_event.is_set():
            now = time.time()
            for symbol in self.symbols:
                if now >= next_trades[symbol]:
                    try:
                        self.poll_trades(symbol)
                    except Exception as exc:
                        if self.on_error:
                            self.on_error(f"trades:{symbol}", exc)
                    next_trades[symbol] = now + self.poll_config.trades_interval_s
                if now >= next_books[symbol]:
                    try:
                        self.poll_orderbook(symbol)
                    except Exception as exc:
                        if self.on_error:
                            self.on_error(f"orderbook:{symbol}", exc)
                    next_books[symbol] = now + self.poll_config.orderbook_interval_s
            for symbol, timeframe in next_ohlcv:
                if now >= next_ohlcv[(symbol, timeframe)]:
                    try:
                        self.poll_ohlcv(symbol, timeframe)
                    except Exception as exc:
                        if self.on_error:
                            self.on_error(f"ohlcv:{symbol}:{timeframe}", exc)
                    next_ohlcv[(symbol, timeframe)] = (
                        now + self.poll_config.ohlcv_interval_s
                    )
            time.sleep(sleep_s)
