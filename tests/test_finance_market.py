import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT))

from tools import finance_market


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class FinanceMarketToolTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        finance_market.register(self.mcp)

    def test_list_finance_providers(self):
        result = self.mcp.tools["list_finance_providers"]()
        self.assertTrue(result["success"])
        self.assertTrue(any(item["id"] == "yahoo-chart" for item in result["providers"]))
        self.assertIn("not financial advice", result["disclaimer"].lower())

    def test_plan_finance_lookup_crypto(self):
        result = self.mcp.tools["plan_finance_lookup"]("bitcoin", "crypto")
        self.assertTrue(result["success"])
        self.assertEqual(result["provider_order"][0], "coingecko")

    def test_market_quote_rejects_invalid_symbol(self):
        result = self.mcp.tools["get_market_quote"]("AAPL;rm")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "invalid_symbol")

    def test_crypto_price_rejects_empty_ids(self):
        result = self.mcp.tools["get_crypto_price"]("")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "empty_coin_ids")

    def test_watchlist_invalid_json(self):
        result = self.mcp.tools["build_watchlist_summary"]("{bad json")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "invalid_symbols_json")

    def test_plan_finance_news_query(self):
        result = self.mcp.tools["plan_finance_news_query"]("AAPL")
        self.assertTrue(result["success"])
        self.assertIn("web.search_web_news", result["use_tools"])

    def test_calculate_position_risk(self):
        result = self.mcp.tools["calculate_position_risk"](100, 95, 10, 10_000)
        self.assertTrue(result["success"])
        self.assertEqual(result["total_risk"], 50)
        self.assertEqual(result["risk_percent_of_account"], 0.5)


if __name__ == "__main__":
    unittest.main()
