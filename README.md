# TradeBotCoinex
Bot de trading en CoinEx en fase inicial. Incluye un cliente HTTP simple para la API v2, carga de configuracion desde `.env` y pruebas basicas.

## Estructura del proyecto
- `tradebot_main.py`: script de entrada para probar llamadas basicas (markets, orderbook, balance).
- `src/coinex_client.py`: cliente CoinEx con firmado HMAC, endpoints spot y helpers de request.
- `src/config.py`: carga y validacion de configuracion desde `.env` y variables de entorno.
- `src/market_data.py`: normalizacion de feeds (trades, OHLCV, order book), cache in-memory/Redis y monitor polling.
- `tests/test_coinex_client.py`: pruebas live contra la API (requiere credenciales para balance).
- `tests/test_coinex_auth.py`: pruebas unitarias del firmado y cabeceras.

## Modulos
### `src/coinex_client.py`
Cliente sin dependencias externas basado en `urllib` que implementa:
- Firmado HMAC SHA256 para endpoints autenticados (`CoinExSigner`).
- Llamadas publicas: `get_markets`, `get_trades`, `get_ohlcv`, `get_orderbook`.
- Llamadas privadas: `get_balance`, `get_open_orders`, `get_fills`, `get_positions`.
- Operaciones de trading (solo si `enable_trading=True`): `place_order`, `cancel_order`.

### `src/config.py`
Gestiona configuracion y validaciones:
- Lee `.env` (si existe) y exporta variables al entorno.
- Valida limites, listas y formato de entorno (`paper` o `live`).
- Devuelve un objeto `Config` con `secrets`, `limits`, `symbols` y `timeframes`.

### `src/market_data.py`
Market Data Layer para monitoreo:
- Normaliza trades, velas y order book.
- Cache in-memory o Redis para velas y snapshots.
- Monitor de polling con callbacks opcionales.
- Convierte timeframes comunes (`1m`, `5m`, `1h`) a periodos CoinEx (`1min`, `5min`, `1hour`).
- Redis requiere instalar `redis` (`pip install redis`).

### `tradebot_main.py`
Script de prueba manual:
- Carga `.env` con `_load_dotenv`.
- Permite consultar `get_balance` cuando existen credenciales.
- Incluye helpers para detectar un mercado de prueba.
 - Ejecuta una pasada de monitoreo y muestra el contenido cacheado.

## Configuracion
Ejemplo minimo de `.env`:
```env
ACCESS_ID=tu_access_id
SECRET_KEY=tu_secret_key
COINEX_BASE_URL=https://api.coinex.com
COINEX_TEST_MARKET=BTCUSDT

TRADING_ENV=paper
SYMBOLS=BTCUSDT,ETHUSDT
TIMEFRAMES=1m,5m
MAX_POSITION_USDT=200
MAX_ORDER_USDT=50
MAX_DAILY_LOSS_PCT=3
```

Variables soportadas:
- Credenciales: `ACCESS_ID` / `SECRET_KEY` (o `COINEX_API_KEY` / `COINEX_API_SECRET`, `API_KEY` / `API_SECRET`).
- API: `COINEX_BASE_URL` (default: `https://api.coinex.com`), `COINEX_TEST_MARKET`.
- Config: `TRADING_ENV`, `SYMBOLS`, `TIMEFRAMES`, `MAX_POSITION_USDT`, `MAX_ORDER_USDT`, `MAX_DAILY_LOSS_PCT`.

## Uso rapido
```bash
python tradebot_main.py
```

## Pruebas
```bash
python -m unittest tests/test_coinex_auth.py
python -m unittest tests/test_coinex_client.py
```

`test_coinex_client.py` usa la API real. `get_balance` se omite si no hay credenciales.
