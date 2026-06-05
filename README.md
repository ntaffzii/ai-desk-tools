# 🛠️ ai-desk-tools (MCP Server)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Model Context Protocol](https://img.shields.io/badge/MCP-FastMCP-green.svg)](https://modelcontextprotocol.io/)

**ai-desk-tools** คือเซิร์ฟเวอร์ Model Context Protocol (MCP) ที่พัฒนาด้วย Python FastMCP ออกแบบมาเพื่อเป็นเครื่องมือเสริมพลังให้กับโมดูล AI/LLM ในการควบคุมและเข้าถึงข้อมูลภายในคอมพิวเตอร์ส่วนบุคคล (Desktop) ทั้งการค้นหาเว็บ การรันคำสั่ง Terminal การจัดการไฟล์ และการควบคุมระบบ GUI

---

## 🌟 ฟีเจอร์หลัก (Key Features)

ระบบแบ่งหมวดหมู่เครื่องมือออกเป็น 5 กลุ่มหลัก เพื่อให้ AI เรียกใช้งานได้อย่างเหมาะสม:

### 1. 📂 Filesystem Tools (การจัดการไฟล์และโฟลเดอร์)
- **`list_directory_tree`**: สแกนและสร้างโครงสร้างโฟลเดอร์แบบ Tree เพื่อให้ AI เห็นภาพรวมโครงการ
- **`find_files_by_keyword`**: ค้นหาไฟล์ด้วยคีย์เวิร์ดอย่างรวดเร็ว (รองรับระบบค้นหาแบบ Optimized สำหรับ Windows)
- **`search_in_files`**: ค้นหาข้อความหรือคีย์เวิร์ดภายในเนื้อหาของไฟล์แบบ Recursive (ทำงานคล้าย grep/findstr รองรับการค้นหาด้วย Regex และจำกัดขนาดไฟล์เพื่อป้องกัน Timeout)

### 2. 🌐 Web Tools (การสืบค้นข้อมูลอินเทอร์เน็ตระดับมืออาชีพ)
- **`search_web`**: ค้นหาข้อมูลเรียลไทม์ผ่าน DuckDuckGo API (คืนค่าเป็น Title, URL, และ Snippet จริง) มีระบบ Fallback ไปยังฐานข้อมูลวิชาการ Crossref
- **`search_web_news`**: ค้นหาข่าวสารล่าสุด ระบุแหล่งข่าว วันที่เผยแพร่ และตรวจสอบความน่าเชื่อถือผ่าน Trusted Sources list
- **`browse_webpage`**: ดึงเนื้อหาหน้าเว็บและแปลงให้อยู่ในรูปแบบ Markdown ที่อ่านง่าย รักษาโครงสร้าง Headings, Links, และ Lists (เหมาะกับเว็บแบบ Static HTML)
- **`browse_dynamic_webpage`**: ดึงเนื้อหาหน้าเว็บที่มีการโหลดข้อมูลผ่าน JavaScript (เช่น SPA, React, Vue, AJAX) โดยจำลองรันผ่านเบราว์เซอร์จริง (Playwright Headless Chromium) และรองรับการรอ CSS Selector จนกว่าจะโหลดเสร็จ

### 3. 💻 System & OS Control (การสั่งการระบบและคำสั่ง)
- **`get_system_drives`**: ดึงรายชื่อ Drive ที่มีทั้งหมดในระบบ (เช่น `C:\`, `D:\`, `I:\`) เพื่อเป็นข้อมูลตั้งต้นให้ AI เริ่มต้นการสแกนระบบ
- **`run_command`**: สั่งรันคำสั่ง Terminal/Shell บนเครื่องผู้ใช้แบบ Synchronous (เช่น `pip install`, `git status`, `dir`) พร้อมระบบแปลงรหัส Encoding อัตโนมัติ ป้องกันปัญหาภาษาไทยและอักษรพิเศษบน Windows
- **`get_current_datetime`**: ดึงวัน เวลา วันในสัปดาห์ (เช่น วันจันทร์-วันอาทิตย์) และข้อมูลไทม์โซนปัจจุบันของเครื่องผู้ใช้ ช่วยให้ AI รู้เวลาในการทำงานเชิงเวลาจริง


### 4. 📺 Media & GUI Automation (การควบคุมอินเทอร์เฟซของระบบ)
- **`open_website`**: เปิดเว็บไซต์ที่ระบุผ่าน Default Web Browser ทันที
- **`play_and_search_youtube`**: เปิดเพลงบน YouTube และใช้เทคโนโลยี Image Recognition (Template Matching ผ่าน `PyAutoGUI`) เพื่อเล็งและคลิกกดเล่นวิดีโอตัวแรกโดยอัตโนมัติ

### 5. ✏️ Code Editing (การอ่านเขียนและปรับแต่งโค้ด)
- **`view_file_content`**: อ่านเนื้อหาในไฟล์ข้อความ UTF-8
- **`write_file`**: เขียนเนื้อหาใหม่ทับลงในไฟล์ หรือสร้างไฟล์ใหม่
- **`edit_file_specific`**: ค้นหาและแก้ไขบล็อกโค้ดเฉพาะจุดภายในไฟล์แบบเจาะจง ป้องกันปัญหาระบบเขียนทับผิดพลาด

---

## 🚀 วิธีการติดตั้งและเริ่มใช้งาน (Installation & Quick Start)

### 1. เตรียมระบบ (Prerequisites)
- ติดตั้ง **Python 3.10 ขึ้นไป**
- (แนะนำ) ติดตั้ง Git สำหรับการควบคุมเวอร์ชัน

### 2. ติดตั้ง Dependencies
โคลนโปรเจกต์นี้ไปยังเครื่องคอมพิวเตอร์ของคุณ จากนั้นรันคำสั่งเพื่อติดตั้งไลบรารีที่จำเป็น:

```bash
# สร้าง Virtual Environment
python -m venv .venv

# เปิดใช้งาน Virtual Environment
# สำหรับ Windows:
.venv\Scripts\activate
# สำหรับ macOS/Linux:
source .venv/bin/activate

# ติดตั้งไลบรารีทั้งหมด
pip install -r requirements.txt

# ติดตั้งเบราว์เซอร์สำหรับ Playwright (ต้องทำอย่างน้อย 1 ครั้งหลังติดตั้งแพ็กเกจ)
playwright install chromium
```

---

## ⚙️ การตั้งค่าใช้งานร่วมกับ Claude Desktop

คุณสามารถเชื่อมต่อเซิร์ฟเวอร์นี้เข้ากับแอปพลิเคชัน Claude Desktop เพื่อใช้งานในฐานะ AI Assistant ส่วนตัวได้โดยแก้ไขไฟล์ตั้งค่า:

**Path สำหรับ Windows:**
`%APPDATA%\Claude\claude_desktop_config.json`

**เนื้อหาไฟล์ตั้งค่าที่ต้องเพิ่ม:**
```json
{
  "mcpServers": {
    "ai-desk-tools": {
      "command": "python",
      "args": [
        "I:/01_Work/Dev/project/ai-llm-tools/server.py"
      ],
      "env": {
        "PYTHONPATH": "I:/01_Work/Dev/project/ai-llm-tools"
      }
    }
  }
}
```
*(หมายเหตุ: กรุณาแก้ไขเส้นทาง Path ให้ตรงกับโฟลเดอร์จริงบนเครื่องของคุณ และใช้เครื่องหมาย Forward Slash `/` ในการระบุเส้นทาง)*

---

## 🧪 การทดสอบระบบ (Testing)

สามารถรันสคริปต์ทดสอบภายในโฟลเดอร์โครงการเพื่อตรวจสอบการทำงานของเซิร์ฟเวอร์แบบเบื้องต้น:

```bash
python -c "from tools.system import register; from tools.filesystem import register"
```

หรือเปิดใช้งานเซิร์ฟเวอร์โดยตรงเพื่อตรวจสอบการลงทะเบียนเครื่องมือผ่าน FastMCP CLI:
```bash
mcp dev server.py
```

---

## 📄 สัญญาอนุญาต (License)

โครงการนี้อยู่ภายใต้สัญญาอนุญาตแบบ **[MIT License](LICENSE)** สามารถนำไปใช้งาน พัฒนาต่อ หรือแจกจ่ายได้อย่างอิสระเสรี
