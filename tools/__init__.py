from tools.filesystem import register as register_filesystem
from tools.web import register as register_web
from tools.code_editing import register as register_code_editing
from tools.media import register as register_media
from tools.system import register as register_system


def register_all_tools(mcp):
    """ลงทะเบียน Tools ทุกโมดูลเข้ากับ MCP Server Instance"""
    register_filesystem(mcp)
    register_web(mcp)
    register_code_editing(mcp)
    register_media(mcp)
    register_system(mcp)
