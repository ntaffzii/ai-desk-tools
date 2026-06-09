"""Finance and market-data MCP tools.

These tools provide educational market lookups and lightweight calculations.
They are not financial advice and should not be used as the sole source for
investment decisions.
"""

from __future__ import annotations

import json
import math
import re
import time
import urllib.parse
import urllib.request


DISCLAIMER = "For education and research only. This is not financial advice."
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
COINGECKO_SIMPLE_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price"


def _clean_symbol(symbol: str) -> str:
    cleaned = symbol.strip().upper()
    if not re.match(r"^[A-Z0-9.^=_-]{1,24}$", cleaned):
        raise ValueError("symbol must contain only letters, numbers, dot, caret, dash, underscore, or equals")
    return cleaned


def _json_get(url: str, params: dict | None = None, timeout_seconds: int = 20) -> dict:
    query = urllib.parse.urlencode(params or {})
    request_url = f"{url}?{query}" if query else url
    request = urllib.request.Request(request_url, headers={"User-Agent": "AI-Desk-Tools/1.0 finance-market"})
    with urllib.request.urlopen(request, timeout=max(3, min(int(timeout_seconds), 60))) as response:
        return json.loads(response.read(5_000_000).decode("utf-8", errors="replace"))


def _parse_yahoo_chart(data: dict, symbol: str) -> dict:
    chart = data.get("chart", {})
    error = chart.get("error")
    if error:
        return {"success": False, "error": "provider_error", "provider": "yahoo-chart", "details": error, "symbol": symbol, "disclaimer": DISCLAIMER}
    results = chart.get("result") or []
    if not results:
        return {"success": False, "error": "quote_not_found", "provider": "yahoo-chart", "symbol": symbol, "disclaimer": DISCLAIMER}
    result = results[0]
    meta = result.get("meta", {})
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    timestamps = result.get("timestamp") or []
    closes = quote.get("close") or []
    last_close = next((value for value in reversed(closes) if value is not None), None)
    price = meta.get("regularMarketPrice") or last_close
    previous_close = meta.get("chartPreviousClose") or meta.get("previousClose")
    change = None
    change_percent = None
    if isinstance(price, (int, float)) and isinstance(previous_close, (int, float)) and previous_close:
        change = price - previous_close
        change_percent = (change / previous_close) * 100
    return {
        "success": True,
        "provider": "yahoo-chart",
        "symbol": symbol,
        "exchange": meta.get("exchangeName") or meta.get("fullExchangeName"),
        "currency": meta.get("currency"),
        "instrument_type": meta.get("instrumentType"),
        "price": price,
        "previous_close": previous_close,
        "change": change,
        "change_percent": change_percent,
        "regular_market_time": meta.get("regularMarketTime"),
        "timezone": meta.get("exchangeTimezoneName"),
        "range": meta.get("range"),
        "timestamps_count": len(timestamps),
        "disclaimer": DISCLAIMER,
    }


def register(mcp) -> None:
    """Register finance market tools."""

    @mcp.tool()
    def list_finance_providers() -> dict:
        """List configured finance data providers and capabilities."""
        return {
            "success": True,
            "providers": [
                {"id": "yahoo-chart", "configured": True, "capabilities": ["quote", "intraday_chart", "historical_chart"], "best_for": "Stocks, ETFs, indexes, FX, and Yahoo-compatible symbols"},
                {"id": "coingecko", "configured": True, "capabilities": ["crypto_spot_price", "24h_change", "market_cap", "volume"], "best_for": "Crypto assets by CoinGecko coin id"},
                {"id": "web-news", "configured": True, "capabilities": ["finance_news_search_plan"], "best_for": "Ticker/company news through the web tools"},
            ],
            "disclaimer": DISCLAIMER,
        }

    @mcp.tool()
    def plan_finance_lookup(topic: str, asset_type: str = "auto") -> dict:
        """Plan a finance lookup without fetching data."""
        normalized_topic = topic.strip()
        if not normalized_topic:
            return {"success": False, "error": "empty_topic"}
        provider_order = ["yahoo-chart", "web-news"]
        if asset_type.lower() in {"crypto", "auto"}:
            provider_order.insert(0, "coingecko")
        return {
            "success": True,
            "topic": normalized_topic,
            "asset_type": asset_type,
            "provider_order": provider_order,
            "recommended_checks": [
                "Get quote or crypto spot price",
                "Read recent public news from reputable sources",
                "Check timestamp, currency, and provider",
                "Label uncertainty and avoid investment advice",
            ],
            "disclaimer": DISCLAIMER,
        }

    @mcp.tool()
    def get_market_quote(symbol: str, range: str = "1d", interval: str = "1m", timeout_seconds: int = 20) -> dict:
        """Get a market quote for a Yahoo-compatible stock, ETF, index, FX, or crypto symbol."""
        try:
            clean_symbol = _clean_symbol(symbol)
        except ValueError as exc:
            return {"success": False, "error": "invalid_symbol", "message": str(exc), "symbol": symbol, "disclaimer": DISCLAIMER}
        params = {"range": range, "interval": interval}
        try:
            data = _json_get(YAHOO_CHART_URL.format(symbol=urllib.parse.quote(clean_symbol, safe="")), params=params, timeout_seconds=timeout_seconds)
            return _parse_yahoo_chart(data, clean_symbol)
        except Exception as exc:
            return {"success": False, "error": "quote_fetch_failed", "provider": "yahoo-chart", "message": str(exc), "symbol": clean_symbol, "disclaimer": DISCLAIMER}

    @mcp.tool()
    def get_crypto_price(ids: str, vs_currency: str = "usd", include_market_data: bool = True, timeout_seconds: int = 20) -> dict:
        """Get crypto spot prices from CoinGecko by comma-separated coin ids such as bitcoin,ethereum."""
        coin_ids = [item.strip().lower() for item in ids.split(",") if item.strip()]
        if not coin_ids:
            return {"success": False, "error": "empty_coin_ids", "disclaimer": DISCLAIMER}
        if len(coin_ids) > 25:
            return {"success": False, "error": "too_many_coin_ids", "max": 25, "disclaimer": DISCLAIMER}
        clean_vs = vs_currency.strip().lower()
        if not re.match(r"^[a-z0-9_]{2,16}$", clean_vs):
            return {"success": False, "error": "invalid_vs_currency", "vs_currency": vs_currency, "disclaimer": DISCLAIMER}
        params = {
            "ids": ",".join(coin_ids),
            "vs_currencies": clean_vs,
            "include_24hr_change": str(bool(include_market_data)).lower(),
            "include_market_cap": str(bool(include_market_data)).lower(),
            "include_24hr_vol": str(bool(include_market_data)).lower(),
            "include_last_updated_at": "true",
        }
        try:
            data = _json_get(COINGECKO_SIMPLE_PRICE_URL, params=params, timeout_seconds=timeout_seconds)
        except Exception as exc:
            return {"success": False, "error": "crypto_fetch_failed", "provider": "coingecko", "message": str(exc), "disclaimer": DISCLAIMER}
        return {"success": True, "provider": "coingecko", "ids": coin_ids, "vs_currency": clean_vs, "prices": data, "disclaimer": DISCLAIMER}

    @mcp.tool()
    def build_watchlist_summary(symbols_json: str, range: str = "1d", interval: str = "1m") -> dict:
        """Get quotes for up to 20 Yahoo-compatible symbols and return a compact watchlist summary."""
        try:
            symbols = json.loads(symbols_json)
            if not isinstance(symbols, list):
                return {"success": False, "error": "symbols_must_be_list", "disclaimer": DISCLAIMER}
        except json.JSONDecodeError as exc:
            return {"success": False, "error": "invalid_symbols_json", "message": str(exc), "disclaimer": DISCLAIMER}
        results = []
        for raw_symbol in symbols[:20]:
            results.append(get_market_quote(str(raw_symbol), range=range, interval=interval))
        return {"success": True, "count": len(results), "results": results, "truncated": len(symbols) > 20, "generated_at": int(time.time()), "disclaimer": DISCLAIMER}

    @mcp.tool()
    def plan_finance_news_query(symbol_or_topic: str, market: str = "US", max_results: int = 5) -> dict:
        """Plan finance-news queries that can be executed by web or web-capture tools."""
        topic = symbol_or_topic.strip()
        if not topic:
            return {"success": False, "error": "empty_topic", "disclaimer": DISCLAIMER}
        safe_limit = max(1, min(int(max_results), 10))
        queries = [
            f"{topic} stock news today {market}",
            f"{topic} earnings revenue guidance analyst today",
            f"{topic} market news latest",
        ]
        return {"success": True, "topic": topic, "market": market, "max_results": safe_limit, "queries": queries, "use_tools": ["web.search_web_news", "web-capture.capture_webpage"], "disclaimer": DISCLAIMER}

    @mcp.tool()
    def calculate_position_risk(entry_price: float, stop_price: float, shares: float = 1.0, account_size: float | None = None) -> dict:
        """Calculate simple position risk for education and planning."""
        entry = float(entry_price)
        stop = float(stop_price)
        qty = float(shares)
        if not all(math.isfinite(value) for value in (entry, stop, qty)) or entry <= 0 or qty <= 0:
            return {"success": False, "error": "invalid_numeric_input", "disclaimer": DISCLAIMER}
        risk_per_share = abs(entry - stop)
        total_risk = risk_per_share * qty
        risk_percent_of_account = None
        if account_size is not None:
            account = float(account_size)
            if account <= 0 or not math.isfinite(account):
                return {"success": False, "error": "invalid_account_size", "disclaimer": DISCLAIMER}
            risk_percent_of_account = (total_risk / account) * 100
        return {
            "success": True,
            "entry_price": entry,
            "stop_price": stop,
            "shares": qty,
            "risk_per_share": risk_per_share,
            "total_risk": total_risk,
            "risk_percent_of_account": risk_percent_of_account,
            "disclaimer": DISCLAIMER,
        }
