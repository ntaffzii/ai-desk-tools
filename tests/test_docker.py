import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = TOOLS_ROOT / "tests" / "_docker_fixture"
sys.path.insert(0, str(TOOLS_ROOT))

from tools import docker


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class DockerToolTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        docker.register(self.mcp)

    def test_find_docker_files(self):
        result = self.mcp.tools["find_docker_files"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertEqual(result["dockerfile_count"], 1)
        self.assertEqual(result["compose_file_count"], 1)

    def test_inspect_dockerfile(self):
        result = self.mcp.tools["inspect_dockerfile"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        dockerfile = result["dockerfile"]
        self.assertEqual(dockerfile["stages"][0]["image"], "python:3.12-slim")
        self.assertIn("8000", dockerfile["exposes"])
        self.assertEqual(dockerfile["cmd"], '["python", "server.py"]')

    def test_inspect_docker_compose(self):
        result = self.mcp.tools["inspect_docker_compose"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        compose = result["compose"]
        self.assertEqual(compose["service_count"], 2)
        self.assertEqual(compose["services"][0]["name"], "web")

    def test_plan_docker_validation(self):
        result = self.mcp.tools["plan_docker_validation"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        commands = [item["command"] for item in result["commands"]]
        self.assertTrue(any("docker build --check" in command for command in commands))
        self.assertTrue(any("docker compose" in command for command in commands))

    def test_blocks_outside_allowed_roots(self):
        result = self.mcp.tools["find_docker_files"](str(FIXTURE_ROOT.parents[3]))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "path_outside_allowed_roots")


if __name__ == "__main__":
    unittest.main()
