import json
import re
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# รองรับทั้ง package ใหม่ (ddgs) และเก่า (duckduckgo_search)
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

# โหลดรายชื่อแหล่งข่าวที่เชื่อถือได้จากไฟล์ config
_PROJECT_ROOT = Path(__file__).parent.parent
_TRUSTED_SOURCES_FILE = _PROJECT_ROOT / "trusted_sources.json"


def _load_trusted_sources() -> set:
    """โหลดรายชื่อแหล่งข่าวที่เชื่อถือได้ (case-insensitive)"""
    try:
        with open(_TRUSTED_SOURCES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {s.lower() for s in data.get("trusted_news_sources", [])}
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def register(mcp):
    """ลงทะเบียน Web Tools เข้ากับ MCP Server"""

    @mcp.tool()
    def search_web(query: str, max_results: int = 5) -> str:
        """
        ค้นหาข้อมูลบนอินเทอร์เน็ตแบบเรียลไทม์ ได้ผลลัพธ์จริง (ชื่อเรื่อง, URL, สรุปเนื้อหา)
        ใช้เมื่อต้องการหาข้อมูล ความรู้ หรือเว็บไซต์ที่เกี่ยวข้องกับหัวข้อที่กำหนด
        :param query: คำค้นหา (รองรับทั้งไทยและอังกฤษ)
        :param max_results: จำนวนผลลัพธ์สูงสุด (ค่าเริ่มต้น 5, สูงสุด 10)
        """
        max_results = min(max(1, max_results), 10)
        print(f"[Web Search] DuckDuckGo search for: '{query}' (max={max_results})")

        try:
            # ============================
            # ท่อหลัก: DuckDuckGo DDGS — ได้ผลค้นหาจริง (title + URL + snippet)
            # ============================
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            if results:
                res_text = f"🔎 ผลการค้นหาสำหรับ '{query}' ({len(results)} รายการ):\n\n"
                for idx, r in enumerate(results, start=1):
                    title = r.get("title", "No Title")
                    url = r.get("href", "No URL")
                    snippet = r.get("body", "ไม่มีคำอธิบาย")
                    res_text += f"[{idx}] {title}\n"
                    res_text += f"    URL: {url}\n"
                    res_text += f"    สรุป: {snippet}\n\n"
                return res_text

        except Exception as ddg_err:
            print(f"[Web Search] DuckDuckGo error: {ddg_err}. Falling back to Crossref...")

        # ============================
        # ท่อสำรอง: Crossref Academic API — กรณี DuckDuckGo ล่ม
        # ============================
        try:
            fallback_url = f"https://api.crossref.org/works?query={urllib.parse.quote(query)}&rows={max_results}"
            fb_res = requests.get(fallback_url, timeout=8).json()
            items = fb_res.get("message", {}).get("items", [])
            if items:
                fb_text = f"🔎 [Crossref Backup] ผลค้นหาจากฐานข้อมูลวิชาการ:\n\n"
                for idx, item in enumerate(items, start=1):
                    title = item.get("title", ["No Title"])[0]
                    link = item.get("URL", "No URL")
                    fb_text += f"[{idx}] {title}\n    URL: {link}\n\n"
                return fb_text
        except Exception as fb_err:
            print(f"[Web Search] Crossref fallback also failed: {fb_err}")

        return f"ไม่สามารถค้นหาข้อมูลสำหรับ '{query}' ได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง"

    @mcp.tool()
    def search_web_news(query: str, max_results: int = 5, trusted_only: bool = False) -> str:
        """
        ค้นหาข่าวสารล่าสุดบนอินเทอร์เน็ต ได้ผลลัพธ์พร้อมวันที่และแหล่งข่าว
        รองรับการกรองเฉพาะแหล่งข่าวที่เชื่อถือได้ (กำหนดใน trusted_sources.json)
        :param query: คำค้นหาข่าว (รองรับทั้งไทยและอังกฤษ)
        :param max_results: จำนวนผลลัพธ์สูงสุด (ค่าเริ่มต้น 5, สูงสุด 10)
        :param trusted_only: ถ้าเป็น True จะแสดงเฉพาะข่าวจากแหล่งที่เชื่อถือได้เท่านั้น
        """
        # ดึงมากกว่าที่ขอ เผื่อกรอง trusted แล้วเหลือน้อย
        fetch_count = min(max(1, max_results), 10)
        if trusted_only:
            fetch_count = min(fetch_count * 3, 25)

        print(f"[Web News] DuckDuckGo news search for: '{query}' (trusted_only={trusted_only})")

        # โหลด trusted sources ใหม่ทุกครั้ง เพื่อให้แก้ไขไฟล์แล้วมีผลทันที
        trusted = _load_trusted_sources()

        try:
            with DDGS() as ddgs:
                results = list(ddgs.news(query, max_results=fetch_count))

            if results:
                filtered = []
                for r in results:
                    source = r.get("source", "")
                    is_trusted = source.lower() in trusted
                    r["_trusted"] = is_trusted
                    if trusted_only and not is_trusted:
                        continue
                    filtered.append(r)

                # จำกัดผลลัพธ์ตามที่ขอ
                display = filtered[:min(max_results, 10)]

                if not display:
                    return f"ไม่พบข่าวจากแหล่งที่เชื่อถือได้สำหรับ '{query}'\nลองใช้ trusted_only=False หรือเพิ่มแหล่งข่าวใน trusted_sources.json"

                mode_label = "เฉพาะแหล่งที่เชื่อถือ" if trusted_only else "ทุกแหล่ง"
                res_text = f"📰 ข่าวล่าสุดสำหรับ '{query}' ({len(display)} รายการ | {mode_label}):\n\n"
                for idx, r in enumerate(display, start=1):
                    title = r.get("title", "No Title")
                    url = r.get("url", "No URL")
                    snippet = r.get("body", "ไม่มีคำอธิบาย")
                    source = r.get("source", "ไม่ทราบแหล่งข่าว")
                    date = r.get("date", "ไม่ทราบวันที่")
                    badge = " ✅" if r.get("_trusted") else ""
                    res_text += f"[{idx}] {title}\n"
                    res_text += f"    แหล่งข่าว: {source}{badge} | วันที่: {date}\n"
                    res_text += f"    URL: {url}\n"
                    res_text += f"    สรุป: {snippet}\n\n"
                return res_text

        except Exception as e:
            return f"ไม่สามารถค้นหาข่าวสำหรับ '{query}' ได้: {str(e)}"

        return f"ไม่พบข่าวที่เกี่ยวข้องกับ '{query}'"

    @mcp.tool()
    def browse_webpage(url: str) -> str:
        """
        เข้าถึง URL ของหน้าเว็บเพื่ออ่านเนื้อหาแบบ Markdown ที่มีโครงสร้างชัดเจน
        ผลลัพธ์จะรักษา headings, links, lists ไว้เพื่อให้ AI เข้าใจเนื้อหาได้ง่ายขึ้น
        ใช้เมื่อต้องการดึงบทความ เอกสาร หรือข้อมูลจากหน้าเว็บมาให้ AI วิเคราะห์
        """
        print(f"[Web Browser] Extracting content from: {url}")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5,th;q=0.3"
        }

        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                return f"Error: ไม่สามารถเข้าถึงหน้าเว็บได้ (HTTP {response.status_code})"

            soup = BeautifulSoup(response.text, "html.parser")

            # ============================
            # 1. ดึง Metadata จาก <head>
            # ============================
            title_tag = soup.find("title")
            page_title = title_tag.get_text().strip() if title_tag else "ไม่มีชื่อเรื่อง"

            desc_tag = soup.find("meta", attrs={"name": "description"})
            if not desc_tag:
                desc_tag = soup.find("meta", attrs={"property": "og:description"})
            page_desc = desc_tag.get("content", "").strip() if desc_tag else ""

            # ============================
            # 2. เลือก Content Body หลัก
            # ============================
            content_body = (
                soup.find("article")
                or soup.find("main")
                or soup.find("div", {"role": "main"})
                or soup.find("div", class_="content")
                or soup.find("div", class_="post-content")
            )
            source = content_body if content_body else soup.body or soup

            # ============================
            # 3. ลบแท็กขยะ
            # ============================
            for element in source(["script", "style", "nav", "footer", "header", "aside",
                                    "form", "iframe", "noscript", "svg", "button",
                                    "input", "select", "textarea"]):
                element.extract()

            # ============================
            # 4. แปลง HTML → Markdown-like text
            # ============================
            # แปลง headings → markdown headings
            for tag in source.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
                level = int(tag.name[1])
                heading_text = tag.get_text().strip()
                if heading_text:
                    tag.replace_with(f"\n\n{'#' * level} {heading_text}\n\n")

            # แปลง links → markdown links
            for a in source.find_all("a", href=True):
                link_text = a.get_text().strip()
                href = a.get("href", "")
                if link_text and href and not href.startswith("#") and not href.startswith("javascript:"):
                    # แปลง relative URL → absolute URL
                    if href.startswith("/"):
                        from urllib.parse import urlparse
                        parsed = urlparse(url)
                        href = f"{parsed.scheme}://{parsed.netloc}{href}"
                    a.replace_with(f"[{link_text}]({href})")

            # แปลง list items → markdown bullets
            for li in source.find_all("li"):
                li_text = li.get_text().strip()
                if li_text:
                    li.replace_with(f"\n- {li_text}")

            # แปลง <code>/<pre> → markdown code blocks
            for code in source.find_all("pre"):
                code_text = code.get_text().strip()
                if code_text:
                    code.replace_with(f"\n```\n{code_text}\n```\n")

            # แปลง bold/italic
            for strong in source.find_all(["strong", "b"]):
                text = strong.get_text().strip()
                if text:
                    strong.replace_with(f"**{text}**")

            for em in source.find_all(["em", "i"]):
                text = em.get_text().strip()
                if text:
                    em.replace_with(f"*{text}*")

            # ============================
            # 5. สกัด text สุดท้ายและจัดระเบียบ
            # ============================
            raw_text = source.get_text()

            # จัดระเบียบบรรทัด: ลดช่องว่างเกิน, ลบบรรทัดว่างซ้ำ
            lines = []
            for line in raw_text.splitlines():
                stripped = line.strip()
                if stripped:
                    lines.append(stripped)
                elif lines and lines[-1] != "":
                    lines.append("")  # เก็บ 1 บรรทัดว่างระหว่าง paragraphs

            clean_text = "\n".join(lines)

            # ลบบรรทัดว่างเกิน 2 บรรทัดติดกัน
            clean_text = re.sub(r"\n{3,}", "\n\n", clean_text)

            # ============================
            # 6. ประกอบผลลัพธ์สุดท้ายพร้อม metadata
            # ============================
            max_chars = 35000

            result = f"📄 **{page_title}**\n"
            result += f"🔗 {url}\n"
            if page_desc:
                result += f"📝 {page_desc}\n"
            result += "---\n\n"

            if len(clean_text) > max_chars:
                result += clean_text[:max_chars]
                result += f"\n\n...[⚠️ ตัดที่ {max_chars} ตัวอักษร — เนื้อหาหลักส่วนใหญ่ครบแล้ว]..."
            else:
                result += clean_text

            if not clean_text.strip():
                return "Error: หน้าเว็บนี้ไม่มีเนื้อหาข้อความ หรือเนื้อหาถูกสร้างด้วย JavaScript (ต้องใช้เบราว์เซอร์จริง)"

            return result

        except requests.exceptions.Timeout:
            return f"Error: หน้าเว็บ {url} ใช้เวลาโหลดนานเกินไป (timeout 15 วินาที)"
        except requests.exceptions.ConnectionError:
            return f"Error: ไม่สามารถเชื่อมต่อกับ {url} ได้ (ตรวจสอบ URL หรือการเชื่อมต่ออินเทอร์เน็ต)"
        except Exception as e:
            return f"Error reading webpage: {str(e)}"
