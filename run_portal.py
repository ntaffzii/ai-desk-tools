import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Resolve paths
TOOLS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_ROOT.parent
CONFIG_PATH = TOOLS_ROOT / "config" / "active_config.json"
TOOLS_JSON_PATH = REPO_ROOT / "data" / "tools.json"
TOOLSETS_JSON_PATH = REPO_ROOT / "data" / "toolsets.json"

class PortalRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.serve_file(TOOLS_ROOT / "portal.html", "text/html")
        elif self.path == "/api/status":
            self.handle_api_status()
        else:
            self.send_error(404, "File Not Found")

    def do_POST(self):
        if self.path == "/api/save":
            self.handle_api_save()
        else:
            self.send_error(404, "Endpoint Not Found")

    def serve_file(self, file_path: Path, content_type: str):
        if not file_path.exists():
            self.send_error(404, f"{file_path.name} not found")
            return
        
        try:
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading file: {e}")

    def handle_api_status(self):
        try:
            tools = []
            if TOOLS_JSON_PATH.exists():
                with open(TOOLS_JSON_PATH, "r", encoding="utf-8") as f:
                    tools = json.load(f)

            toolsets = []
            if TOOLSETS_JSON_PATH.exists():
                with open(TOOLSETS_JSON_PATH, "r", encoding="utf-8") as f:
                    toolsets = json.load(f)

            active_config = {}
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    active_config = json.load(f)
            else:
                active_config = {"active_toolset": "", "active_groups": []}

            response_data = {
                "success": True,
                "tools": tools,
                "toolsets": toolsets,
                "active_config": active_config
            }
            self.send_json(response_data)
        except Exception as e:
            self.send_error(500, f"Error loading status: {e}")

    def handle_api_save(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode("utf-8"))

            active_toolset = payload.get("active_toolset", "")
            active_groups = payload.get("active_groups", [])

            # Ensure config dir exists
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

            config_data = {
                "active_toolset": active_toolset,
                "active_groups": active_groups
            }

            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

            self.send_json({"success": True, "message": "Configuration saved successfully."})
        except Exception as e:
            self.send_error(500, f"Error saving configuration: {e}")

    def send_json(self, data: dict):
        response_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(response_bytes))
        self.end_headers()
        self.wfile.write(response_bytes)

def run(port=8000):
    server_address = ("", port)
    httpd = HTTPServer(server_address, PortalRequestHandler)
    print(f"\n=======================================================")
    print(f"  MCP Web Portal started successfully!")
    print(f"  Access the dashboard at: http://localhost:{port}")
    print(f"  Press Ctrl+C to stop.")
    print(f"=======================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down portal server...")
        httpd.server_close()
        sys.exit(0)

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run(port)
