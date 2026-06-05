import os
import time
from pathlib import Path


def register(mcp):
    """ลงทะเบียน System Tools เข้ากับ MCP Server"""

    @mcp.tool()
    def get_system_drives() -> str:
        """
        ดึงรายชื่อไดรฟ์หรือเส้นทางหลักที่มีทั้งหมดในคอมพิวเตอร์เครื่องนี้มาแสดง
        ใช้เครื่องมือนี้เป็นอันดับแรกสุดเมื่อ AI ไม่รู้ว่าคอมพิวเตอร์เครื่องนี้มีไดรฟ์ไหนให้แสกนบ้าง (เช่น มี C:/, D:/, I:/)
        """
        import string
        # ตรวจสอบบนระบบ Windows
        if os.name == 'nt':
            drives = []
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    drives.append(drive)
            return f"💻 ระบบนี้เป็น Windows พบไดรฟ์ทั้งหมดในเครื่อง: {', '.join(drives)}"
        else:
            # ระบบ Mac / Linux
            return "💻 ระบบนี้เป็น Unix-based สามารถเริ่มแสกนจาก Root Path '/' ได้เลย"

    @mcp.tool()
    def generate_efficiency_report(project_name: str, score: float, summary_text: str, output_dir: str) -> str:
        """
        สร้างรายงานประเมินประสิทธิภาพ (Efficiency Report) เป็นไฟล์ Markdown (.md)
        ใช้สำหรับบันทึกผลการทดสอบการทำงาน ความเร็ว หรือการประเมินคุณภาพของโมเดล AI
        """
        out_path = Path(output_dir).resolve()
        # สร้างโฟลเดอร์ให้หากยังไม่มี
        out_path.mkdir(parents=True, exist_ok=True)
        
        file_name = f"efficiency_report_{int(time.time())}.md"
        target_file = out_path / file_name
        
        # สร้างเนื้อหารายงานแบบ Markdown
        report_content = f"""# รายงานประเมินประสิทธิภาพ: {project_name}
วันที่ประเมิน: {time.strftime('%Y-%m-%d %H:%M:%S')}
คะแนนประสิทธิภาพสุทธิ: **{score}/100**

## บทสรุปผลการประเมิน
{summary_text}

## รายละเอียดการทดสอบฮาร์ดแวร์/ซอฟต์แวร์ที่เกี่ยวข้อง
- **ระบบขับเคลื่อน:** Model Context Protocol (MCP) Server via Python FastMCP
- **อินเทอร์เฟซการสื่อสาร:** JSON-RPC 2.0 via Standard Input/Output (Stdio)
- **สถานะการเข้าถึงไฟล์ระบบ:** ทำงานได้ปกติ (Full Directory Scanning Enabled)

---
*รายงานนี้ถูกสร้างขึ้นโดยอัตโนมัติผ่านระบบ AI-LLM-Tools MCP Server*
"""
        try:
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(report_content)
            return f"สร้างรายงานประเมินประสิทธิภาพสำเร็จแล้วที่: {target_file}"
        except Exception as e:
            return f"ไม่สามารถสร้างรายงานได้เนื่องจาก: {str(e)}"

    @mcp.tool()
    def run_command(command: str, cwd: str = None) -> str:
        """
        รันคำสั่ง terminal/shell บนระบบคอมพิวเตอร์ของผู้ใช้แบบ synchronous (เช่น 'dir', 'git status', 'pip install')
        :param command: คำสั่งที่ต้องการรัน (เช่น 'dir', 'git status', 'echo hello')
        :param cwd: โฟลเดอร์ที่ต้องการให้รันคำสั่ง (หากไม่ระบุจะรันที่ตำแหน่งปัจจุบันของเซิร์ฟเวอร์)
        """
        import subprocess
        import locale

        if cwd:
            cwd_path = Path(cwd).resolve()
            if not cwd_path.exists():
                return f"ข้อผิดพลาด: ไม่พบโฟลเดอร์ปฏิบัติการ (cwd) ที่ระบุ: {cwd}"
            cwd_str = str(cwd_path)
        else:
            cwd_str = None

        print(f"[OS Control] Running command: '{command}' in cwd: {cwd_str}")

        try:
            # รันคำสั่งด้วย shell=True เพื่อรองรับคำสั่ง built-in ใน cmd/powershell
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd_str,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30  # จำกัดเวลารันเพื่อไม่ให้ค้าง
            )

            # ตรวจสอบตัวถอดรหัสที่เหมาะสมกับระบบ (โดยเฉพาะ Windows ที่ใช้ encoding ภาษาไทย/ต่างประเทศ)
            system_encoding = locale.getpreferredencoding() or "utf-8"
            
            stdout_decoded = ""
            stderr_decoded = ""

            for enc in [system_encoding, "utf-8", "cp874", "ascii"]:
                try:
                    stdout_decoded = result.stdout.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                stdout_decoded = result.stdout.decode("utf-8", errors="replace")

            for enc in [system_encoding, "utf-8", "cp874", "ascii"]:
                try:
                    stderr_decoded = result.stderr.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                stderr_decoded = result.stderr.decode("utf-8", errors="replace")

            output_str = f"=== ผลลัพธ์คำสั่ง (Exit Code: {result.returncode}) ===\n"
            if stdout_decoded.strip():
                output_str += f"[Stdout]\n{stdout_decoded}\n"
            if stderr_decoded.strip():
                output_str += f"[Stderr]\n{stderr_decoded}\n"
            if not stdout_decoded.strip() and not stderr_decoded.strip():
                output_str += "(คำสั่งเสร็จสิ้นโดยไม่มีผลลัพธ์แสดงออกมา)\n"

            return output_str

        except subprocess.TimeoutExpired:
            return f"Timeout: การรันคำสั่ง '{command}' ใช้เวลานานเกิน 30 วินาที"
        except Exception as e:
            return f"เกิดข้อผิดพลาดในการรันคำสั่ง: {str(e)}"

    @mcp.tool()
    def get_current_datetime() -> str:
        """
        ดึงวัน เวลา วันในสัปดาห์ และไทม์โซนปัจจุบันของคอมพิวเตอร์ผู้ใช้
        ใช้เมื่อ AI ต้องการทราบวันหรือเวลาปัจจุบันเพื่อบันทึกรายงาน อ้างอิง หรือเปรียบเทียบข้อมูลล่าสุด
        """
        import datetime
        
        now = datetime.datetime.now()
        local_now = now.astimezone()
        day_name = now.strftime("%A")
        
        thai_days = {
            "Monday": "วันจันทร์",
            "Tuesday": "วันอังคาร",
            "Wednesday": "วันพุธ",
            "Thursday": "วันพฤหัสบดี",
            "Friday": "วันศุกร์",
            "Saturday": "วันเสาร์",
            "Sunday": "วันอาทิตย์"
        }
        thai_day = thai_days.get(day_name, day_name)
        
        tz_offset = local_now.strftime("%z")
        formatted_tz = f"UTC{tz_offset[:3]}:{tz_offset[3:]}" if tz_offset else "ไม่ระบุ"
        tz_name = local_now.tzname() or "Local Time"
        
        return (
            f"📅 วันที่: {now.strftime('%Y-%m-%d')}\n"
            f"📆 วันในสัปดาห์: {thai_day} ({day_name})\n"
            f"⏰ เวลาปัจจุบัน: {now.strftime('%H:%M:%S')}\n"
            f"🌐 ไทม์โซน: {tz_name} ({formatted_tz})"
        )


