import os
import subprocess
import shutil
from pathlib import Path


def build_tree(dir_path: Path, prefix: str = "", max_depth: int = 3, current_depth: int = 1) -> str:
    """ฟังก์ชันสร้าง Directory Tree"""
    if current_depth > max_depth:
        return f"{prefix}... (จำกัดความลึกไว้ที่ชั้น {max_depth})\n"
    
    tree_str = ""
    ignored = {".git", "__pycache__", "node_modules", ".venv", ".env"}
    try:
        all_items = sorted(list(dir_path.iterdir()), key=lambda x: (x.is_file(), x.name.lower()))
        # กรองรายการที่ไม่จำเป็นออกก่อน เพื่อให้ is_last คำนวณถูกต้อง
        items = [item for item in all_items if item.name not in ignored]
    except PermissionError:
        return f"{prefix} [Permission Denied - ไม่มีสิทธิ์เข้าถึง]\n"
    except Exception as e:
        return f"{prefix} [Error: {str(e)}]\n"

    for i, item in enumerate(items):
        is_last = (i == len(items) - 1)
        connector = "└── " if is_last else "├── "
        
        if item.is_dir():
            tree_str += f"{prefix}{connector}{item.name}/\n"
            new_prefix = prefix + ("    " if is_last else "│   ")
            tree_str += build_tree(item, new_prefix, max_depth, current_depth + 1)
        else:
            tree_str += f"{prefix}{connector}{item.name}\n"
            
    return tree_str


def register(mcp):
    """ลงทะเบียน Filesystem Tools เข้ากับ MCP Server"""

    @mcp.tool()
    def list_directory_tree(target_path: str, max_depth: int = 3) -> str:
        """
        แสกนและแสดงโครงสร้างโฟลเดอร์ทั้งหมดเป็น Tree
        ใช้เครื่องมือนี้เมื่อต้องการให้ AI เข้าใจภาพรวมของโปรเจกต์ก่อนอ่านไฟล์
        """
        path = Path(target_path).resolve()
        if not path.exists():
            return f"ข้อผิดพลาด: ไม่พบเส้นทาง (Path) '{target_path}'"
        if not path.is_dir():
            return f"ข้อผิดพลาด: '{target_path}' เป็นไฟล์ ไม่ใช่โฟลเดอร์"
            
        tree_output = f"โครงสร้างโฟลเดอร์ของ: {path}\n"
        tree_output += build_tree(path, max_depth=max_depth)
        return tree_output

    @mcp.tool()
    def find_files_by_keyword(root_path: str, keyword: str, file_pattern: str = "*") -> str:
        """
        ค้นหาไฟล์จากชื่อหรือคีย์เวิร์ดอย่างรวดเร็วสูงสุด ป้องกัน Timeout
        """
        print(f"[File Search] Searching in {root_path} for '{keyword}'")
        
        clean_root = root_path.replace("/", "\\")
        if not clean_root.endswith("\\"):
            clean_root += "\\"

        patterns = [p.strip() for p in file_pattern.split(",")]
        if not patterns or patterns == ["*"]:
            patterns = [f"*{keyword}*"]
        else:
            patterns = [p.replace("*", f"*{keyword}*") for p in patterns]

        found_files = []

        try:
            if os.name == 'nt' and shutil.which("where"):
                for pat in patterns:
                    cmd = ["where", "/R", clean_root, pat]
                    # ขยายเวลา Timeout เป็น 12 วินาทีให้หายใจโล่งขึ้น
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=12)
                    
                    if result.returncode == 0 and result.stdout:
                        paths = result.stdout.strip().split("\n")
                        found_files.extend(paths)
            else:
                return "Error: This optimized search is for Windows only."

        except subprocess.TimeoutExpired:
            return f"Timeout: Searching in '{root_path}' took too long. Please specify a narrower folder like 'C:\\Users' or 'I:\\01_Work'."
        except Exception as e:
            return f"Error: {str(e)}"

        ignored = [".git", "node_modules", "__pycache__", ".venv", "$recycle.bin"]
        final_files = [f for f in found_files if not any(ig in f.lower() for ig in ignored)]

        if not final_files:
            return f"Search finished: No files found matching '{keyword}' under '{root_path}'."

        display_files = final_files[:15]
        res_text = f"Found {len(final_files)} files (Showing top 15):\n"
        for f in display_files:
            res_text += f"- {f}\n"
        return res_text

    @mcp.tool()
    def search_in_files(root_path: str, query: str, file_pattern: str = "*", is_regex: bool = False, case_insensitive: bool = True) -> str:
        """
        ค้นหาข้อความหรือคีย์เวิร์ดภายในเนื้อหาไฟล์แบบ recursive (คล้าย grep หรือ findstr)
        :param root_path: โฟลเดอร์เริ่มต้นในการค้นหา
        :param query: คำหรือข้อความที่ต้องการค้นหา (รองรับ Regex และ Plain Text)
        :param file_pattern: รูปแบบไฟล์ที่ต้องการค้นหา เช่น '*.py' หรือคั่นด้วยคอมมา เช่น '*.py,*.md' (ค่าเริ่มต้น '*')
        :param is_regex: ค้นหาโดยใช้ Regular Expression หรือไม่ (ค่าเริ่มต้น False)
        :param case_insensitive: ค้นหาแบบไม่สนใจตัวอักษรพิมพ์เล็ก-ใหญ่หรือไม่ (ค่าเริ่มต้น True)
        """
        import fnmatch
        import re

        path = Path(root_path).resolve()
        if not path.exists():
            return f"ข้อผิดพลาด: ไม่พบโฟลเดอร์ '{root_path}'"
        if not path.is_dir():
            return f"ข้อผิดพลาด: '{root_path}' ไม่ใช่โฟลเดอร์"

        # แยก file patterns
        patterns = [p.strip() for p in file_pattern.split(",")]

        # กรองโฟลเดอร์ที่ไม่ควรแสกนเพื่อเพิ่มความเร็วและป้องกัน Timeout
        ignored_dirs = {".git", "node_modules", "__pycache__", ".venv", ".idea", ".vscode"}

        # เตรียม Regex
        if is_regex:
            flags = re.IGNORECASE if case_insensitive else 0
            try:
                pattern_re = re.compile(query, flags)
            except re.error as e:
                return f"ข้อผิดพลาด: Regex ไม่ถูกต้อง: {str(e)}"
        else:
            search_str = query.lower() if case_insensitive else query

        matches = []
        max_matches = 50
        max_file_size = 1 * 1024 * 1024  # 1MB

        # ค้นหาไฟล์
        for root, dirs, files in os.walk(path):
            # กรองโฟลเดอร์ใน dirs inplace เพื่อไม่ให้ os.walk เดินเข้าไป
            dirs[:] = [d for d in dirs if d not in ignored_dirs]

            for file in files:
                # ตรวจสอบรูปแบบไฟล์
                match_pattern = False
                for pat in patterns:
                    if fnmatch.fnmatch(file, pat):
                        match_pattern = True
                        break

                if not match_pattern:
                    continue

                file_path = Path(root) / file

                # ตรวจสอบขนาดไฟล์ ป้องกันไฟล์ขนาดใหญ่
                try:
                    if file_path.stat().st_size > max_file_size:
                        continue
                except OSError:
                    continue

                # อ่านไฟล์และหาคำค้นหา
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        for line_no, line in enumerate(f, 1):
                            matched = False
                            if is_regex:
                                if pattern_re.search(line):
                                    matched = True
                            else:
                                line_to_check = line.lower() if case_insensitive else line
                                if search_str in line_to_check:
                                    matched = True

                            if matched:
                                matches.append({
                                    "file": str(file_path.relative_to(path)),
                                    "line_no": line_no,
                                    "content": line.strip()
                                })
                                if len(matches) >= max_matches:
                                    break
                except Exception:
                    # ข้ามไฟล์ที่มีปัญหาระหว่างอ่าน เช่น ติด lock หรือ binary files
                    continue

            if len(matches) >= max_matches:
                break

        if not matches:
            return f"ค้นหาเสร็จสิ้น: ไม่พบคำว่า '{query}' ในเนื้อหาไฟล์ภายใต้ '{root_path}'"

        res_text = f"🔎 ผลการค้นหาเนื้อหาสำหรับ '{query}' (พบทั้งหมด {len(matches)} รายการ):\n\n"
        for m in matches:
            res_text += f"📄 {m['file']} (บรรทัด {m['line_no']}):\n"
            res_text += f"    {m['content']}\n\n"

        if len(matches) >= max_matches:
            res_text += f"⚠️ หมายเหตุ: แสดงผลลัพธ์สูงสุด {max_matches} รายการแรกเท่านั้น"

        return res_text

