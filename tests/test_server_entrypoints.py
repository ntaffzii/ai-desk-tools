import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ServerEntrypointTests(unittest.TestCase):
    def test_http_server_builds_fastmcp_and_registers_tools(self):
        fake_server = MagicMock()
        with patch.dict("sys.modules", {"mcp": MagicMock(), "mcp.server": MagicMock(), "mcp.server.fastmcp": MagicMock(FastMCP=MagicMock(return_value=fake_server))}):
            module = load_module(REPO_ROOT / "mcp-tools" / "server_http.py", "server_http_test")
            server = module.build_server()
        self.assertIs(server, fake_server)
        self.assertTrue(fake_server.tool.called)


if __name__ == "__main__":
    unittest.main()

