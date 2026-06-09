import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT))

from tools import web_capture


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class WebCaptureToolTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        web_capture.register(self.mcp)

    def test_list_web_capture_providers(self):
        result = self.mcp.tools["list_web_capture_providers"]()
        self.assertTrue(result["success"])
        self.assertTrue(any(item["id"] == "local-static" for item in result["providers"]))

    def test_extract_html_content(self):
        html = "<html><head><title>Demo</title></head><body><main><h1>Hello</h1><p>Readable text</p><a href='/next'>Next</a></main></body></html>"
        result = self.mcp.tools["extract_html_content"](html, "https://example.com/page")
        self.assertTrue(result["success"])
        self.assertEqual(result["title"], "Demo")
        self.assertIn("Readable text", result["content"])
        self.assertEqual(result["links"][0]["url"], "https://example.com/next")

    def test_extract_links_internal_only(self):
        html = "<a href='/a'>A</a><a href='https://other.example/b'>B</a>"
        result = self.mcp.tools["extract_links_from_html"](html, "https://example.com/start", True)
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["links"][0]["url"], "https://example.com/a")

    def test_plan_social_capture_policy(self):
        result = self.mcp.tools["plan_web_capture"]("https://www.instagram.com/example/")
        self.assertTrue(result["success"])
        self.assertTrue(result["social_policy"]["is_social_domain"])
        self.assertFalse(result["social_policy"]["auth_bypass_allowed"])

    def test_capture_webpage_rejects_bad_scheme(self):
        result = self.mcp.tools["capture_webpage"]("ftp://example.test")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "unsupported_url_scheme")

    def test_batch_capture_urls_invalid_json(self):
        result = self.mcp.tools["batch_capture_urls"]("{bad json")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "invalid_urls_json")


if __name__ == "__main__":
    unittest.main()
