from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, MutableMapping, Optional
from urllib import error, parse, request


class CoinExAPIError(RuntimeError):
    """Raised when the CoinEx API returns an error response."""


DEFAULT_ENDPOINTS = {
    "markets": "/spot/market",
    "balance": "/assets/spot/balance",
    "orderbook": "/spot/depth",
    "place_order": "/spot/order",
    "cancel_order": "/spot/cancel-order",
    "open_orders": "/spot/pending-order",
    "fills": "/spot/fill",
    "positions": "/futures/position",
}


def _encode_query(params: Optional[Mapping[str, Any]]) -> str:
    if not params:
        return ""
    items: list[tuple[str, str]] = []
    for key in sorted(params.keys()):
        value = params[key]
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            for entry in value:
                items.append((key, str(entry)))
        else:
            items.append((key, str(value)))
    return parse.urlencode(items)


def _encode_body(body: Optional[Any]) -> str:
    if body is None:
        return ""
    if isinstance(body, str):
        return body
    return json.dumps(body, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True)
class CoinExSigner:
    api_key: str
    api_secret: str
    time_fn: Callable[[], float] = time.time

    def timestamp_ms(self) -> str:
        return str(int(self.time_fn() * 1000))

    def build_payload(
        self,
        method: str,
        path: str,
        params: Optional[Mapping[str, Any]] = None,
        body: Optional[Any] = None,
        timestamp: Optional[str] = None,
    ) -> tuple[str, str]:
        ts = timestamp or self.timestamp_ms()
        query = _encode_query(params)
        body_str = _encode_body(body)
        normalized_path = path if path.startswith("/") else f"/{path}"
        if not normalized_path.startswith("/v2/") and normalized_path != "/v2":
            normalized_path = f"/v2{normalized_path}"
        request_path = normalized_path
        if query:
            request_path = f"{request_path}?{query}"
        payload = f"{method.upper()}{request_path}{body_str}{ts}"
        return payload, ts

    def build_signature(
        self,
        method: str,
        path: str,
        params: Optional[Mapping[str, Any]] = None,
        body: Optional[Any] = None,
        timestamp: Optional[str] = None,
    ) -> tuple[str, str]:
        payload, ts = self.build_payload(method, path, params, body, timestamp)
        digest = hmac.new(
            self.api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return digest, ts

    def build_headers(
        self,
        method: str,
        path: str,
        params: Optional[Mapping[str, Any]] = None,
        body: Optional[Any] = None,
        timestamp: Optional[str] = None,
        extra_headers: Optional[Mapping[str, str]] = None,
    ) -> dict[str, str]:
        signature, ts = self.build_signature(method, path, params, body, timestamp)
        headers = {
            "X-COINEX-KEY": self.api_key,
            "X-COINEX-SIGN": signature,
            "X-COINEX-TIMESTAMP": ts,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        return headers


class CoinExClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        base_url: str = "https://api.coinex.com/v2",
        timeout: float = 30.0,
        enable_trading: bool = False,
        market_type: str = "spot",
        endpoints: Optional[Mapping[str, str]] = None,
        time_fn: Callable[[], float] = time.time,
    ) -> None:
        normalized = base_url.rstrip("/")
        if not normalized.endswith("/v2"):
            normalized = f"{normalized}/v2"
        self.base_url = normalized
        self.timeout = timeout
        self.enable_trading = enable_trading
        self.market_type = market_type
        self.endpoints = {**DEFAULT_ENDPOINTS, **(endpoints or {})}
        self.signer = CoinExSigner(api_key, api_secret, time_fn=time_fn)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        body: Optional[Any] = None,
        signed: bool = False,
    ) -> Any:
        query = _encode_query(params)
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        headers: MutableMapping[str, str] = {"Accept": "application/json"}
        payload = None
        if body is not None:
            body_str = _encode_body(body)
            payload = body_str.encode("utf-8")
            headers["Content-Type"] = "application/json"

        if signed:
            headers.update(
                self.signer.build_headers(method, path, params=params, body=body)
            )

        req = request.Request(url, data=payload, headers=dict(headers), method=method)
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise CoinExAPIError(f"HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise CoinExAPIError(f"Network error: {exc}") from exc

        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    def get_markets(self) -> Any:
        return self._request("GET", self.endpoints["markets"], signed=False)

    def get_balance(self) -> Any:
        return self._request("GET", self.endpoints["balance"], signed=True)

    def get_orderbook(
        self,
        symbol: str,
        *,
        limit: int = 50,
        interval: str = "0",
    ) -> Any:
        return self._request(
            "GET",
            self.endpoints["orderbook"],
            params={"market": symbol, "limit": limit, "interval": interval},
            signed=False,
        )

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        *,
        price: Optional[float] = None,
        client_id: Optional[str] = None,
    ) -> Any:
        if not self.enable_trading:
            raise RuntimeError("Trading is disabled for this client instance.")
        if order_type.lower() == "limit" and price is None:
            raise ValueError("Limit orders require a price.")
        body = {
            "market": symbol,
            "side": side,
            "type": order_type,
            "amount": amount,
        }
        if price is not None:
            body["price"] = price
        if client_id is not None:
            body["client_id"] = client_id
        return self._request(
            "POST",
            self.endpoints["place_order"],
            body=body,
            signed=True,
        )

    def cancel_order(
        self,
        *,
        order_id: Optional[str] = None,
        client_id: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> Any:
        if not self.enable_trading:
            raise RuntimeError("Trading is disabled for this client instance.")
        if not order_id and not client_id:
            raise ValueError("Provide order_id or client_id to cancel an order.")
        body: dict[str, Any] = {}
        if order_id:
            body["order_id"] = order_id
        if client_id:
            body["client_id"] = client_id
        if symbol:
            body["market"] = symbol
        return self._request(
            "POST",
            self.endpoints["cancel_order"],
            body=body,
            signed=True,
        )

    def get_open_orders(self, *, symbol: Optional[str] = None) -> Any:
        params = {"market": symbol} if symbol else None
        return self._request(
            "GET",
            self.endpoints["open_orders"],
            params=params,
            signed=True,
        )

    def get_positions(self) -> Any:
        if self.market_type.lower() not in {"swap", "futures", "perpetual"}:
            return []
        return self._request("GET", self.endpoints["positions"], signed=True)

    def get_fills(self, *, symbol: Optional[str] = None) -> Any:
        params = {"market": symbol} if symbol else None
        return self._request(
            "GET",
            self.endpoints["fills"],
            params=params,
            signed=True,
        )
