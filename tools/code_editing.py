from pathlib import Path


def register(mcp):
    """ลงทะเบียน Code Editing Tools เข้ากับ MCP Server"""

    @mcp.tool()
    def view_file_content(file_path: str) -> str:
        """
        อ่านเนื้อหาภายในไฟล์ที่กำหนดทั้งหมดเป็นข้อความแบบ UTF-8
        ใช้เครื่องมือนี้หลังจากที่ AI ค้นพบไฟล์ที่ต้องการจากโครงสร้างโฟลเดอร์แล้ว
        """
        path = Path(file_path).resolve()
        if not path.exists():
            return f"ข้อผิดพลาด: ไม่พบไฟล์ '{file_path}'"
        if path.is_dir():
            return f"ข้อผิดพลาด: '{file_path}' เป็นโฟลเดอร์ กรุณาใช้ list_directory_tree แทน"
            
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return f"=== เนื้อหาไฟล์: {path} ===\n{content}\n=== จบเนื้อหาไฟล์ ==="
        except Exception as e:
            return f"เกิดข้อผิดพลาดในการอ่านไฟล์: {str(e)}"

    @mcp.tool()
    def write_file(file_path: str, content: str) -> str:
        """เขียนเนื้อหาใหม่ทับลงในไฟล์ หรือสร้างไฟล์ใหม่"""
        path = Path(file_path).resolve()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Success: File written to {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"

    @mcp.tool()
    def edit_file_specific(file_path: str, target_block: str, new_block: str) -> str:
        """แก้ไขบล็อกโค้ดเฉพาะจุดภายในไฟล์"""
        path = Path(file_path).resolve()
        if not path.exists():
            return f"Error: File '{file_path}' not found."
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            # ใช้ stripped version เดียวกันทั้ง check และ replace เพื่อป้องกัน mismatch
            clean_target = target_block.strip()
            if clean_target not in content:
                return "Error: The target code block to replace was not found."
            updated = content.replace(clean_target, new_block)
            with open(path, "w", encoding="utf-8") as f:
                f.write(updated)
            return f"Success: Code modified in '{path.name}'"
        except Exception as e:
            return f"Error editing file: {str(e)}"
