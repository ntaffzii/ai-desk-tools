from mcp.server.fastmcp import FastMCP
from tools import register_all_tools

# สร้าง FastMCP Server สำหรับ AI Desk Tools
mcp = FastMCP("AI Desk Tools")

# ลงทะเบียน Tools ทุกหมวดหมู่จากโมดูลย่อยในโฟลเดอร์ tools/
register_all_tools(mcp)

if __name__ == "__main__":
    # รันเซิร์ฟเวอร์ด้วยมาตรฐาน Stdio สำหรับต่อกับ Claude Desktop หรือ AI Client อื่นๆ
    mcp.run(transport="stdio")