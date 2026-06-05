import os
import urllib.parse
import time
import subprocess
import shutil
import webbrowser
from pathlib import Path

# หาตำแหน่ง root ของโปรเจกต์ (parent ของโฟลเดอร์ tools/)
_PROJECT_ROOT = Path(__file__).parent.parent


def register(mcp):
    """ลงทะเบียน Media Tools เข้ากับ MCP Server"""

    @mcp.tool()
    def open_website(url: str) -> str:
        """
        เปิดเว็บไซต์ที่กำหนดบนบราวเซอร์หลักของเครื่องผู้ใช้ทันที
        เช่น เปิด 'https://www.youtube.com' หรือ 'https://www.google.com'
        """
        print(f"[OS Control] Opening website: {url}")
        try:
            webbrowser.open(url)
            return f"Success: เปิดเว็บไซต์ {url} บนบราวเซอร์เครื่องผู้ใช้สำเร็จแล้ว"
        except Exception as e:
            return f"Error opening website: {str(e)}"

    @mcp.tool()
    def play_and_search_youtube(song_name: str) -> str:
        """
        เปิด YouTube ค้นหาเพลง และใช้ระบบ Image Recognition (ปุ่มสามจุด) เล็งพิกัดเพื่อคลิกเล่นวิดีโอตัวแรกอย่างแม่นยำ
        """
        import pyautogui  # lazy import — ป้องกัน crash บนเครื่องไม่มี GUI

        print(f"[OS Control] Operating YouTube via GUI Recognition for: {song_name}")
        try:
            # 1. เปิดหน้าค้นหาของ YouTube ตรงๆ พร้อมชื่อเพลง
            encoded_query = urllib.parse.quote(song_name)
            search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
            webbrowser.open(search_url)
            
            # 2. รอหน้าเว็บโหลดให้เรียบร้อย (ปรับเป็น 6 วินาที เผื่ออินเทอร์เน็ตโหลดช้า)
            time.sleep(6)
            
            # 3. ค้นหาตำแหน่งของรูปภาพที่เราแคปไว้ (video_anchor.png) บนหน้าจอคอมพิวเตอร์
            image_path = str(_PROJECT_ROOT / "video_anchor.png")
            
            print(f"[OS Control] Scanning screen for anchor image: {image_path}")
            
            try:
                location = pyautogui.locateOnScreen(image_path, confidence=0.7)
                if location:
                    point = pyautogui.center(location)
                    target_x = point.x + 180
                    target_y = point.y - 60
                    pyautogui.click(target_x, target_y)
                    return f"Success: เล็งเป้าหมายจากหน้าปกและกดคลิกเล่นเพลง '{song_name}' สำเร็จ!"
                else:
                    # 🌟 ลอจิกเซฟโซน: ถ้าหาภาพไม่เจอจริง ๆ อย่าปล่อยให้พัง ให้กดทริกเกอร์ Enter รัวด่วนไปเลย!
                    print("[OS Control] Image anchor not found. Using safe Keyboard Fallback...")
                    pyautogui.press('enter')
                    return f"Notice: ค้นหาภาพปกไม่พบ (อาจเพราะขนาดหน้าต่าง) แต่ส่งคำสั่ง Enter เพื่อพยายามกดเล่นเพลง '{song_name}' ให้แล้วครับ"
                    
            except Exception as img_err:
                # 🌟 ดักจับถ้าไลบรารีมีปัญหาเรื่องการจับภาพ ให้ส่งคำสั่งคีย์บอร์ดแทนทันที ระบบจะได้ไม่ค้าง
                pyautogui.press('enter')
                return f"Notice: ระบบสแกนภาพขัดข้อง ({str(img_err)}) ได้เปลี่ยนมาสั่งเล่นเพลงผ่านปุ่ม Enter แทนเรียบร้อยแล้ว"
                
        except Exception as e:
            return f"Error GUI automation: {str(e)}"

    @mcp.tool()
    def play_audio_background(song_name: str) -> str:
        """
        ดึงเสียงเพลงจาก YouTube และสตรีมเล่นบนหลังบ้านทันทีโดยใช้ yt-dlp ร่วมกับ mpv
        เครื่องมือนี้ทำงานเบื้องหลังโดยไม่ต้องเปิดหน้าต่างบราวเซอร์ให้รกเครื่องผู้ใช้
        """
        print(f"[Audio Server] Streaming background audio for: {song_name}")
        
        # ตรวจสอบว่าเครื่องมีโปรแกรมไหม (ต้อง run: pip install yt-dlp และโหลด mpv ก่อนนะ)
        # ใช้ absolute path จาก project root เพื่อไม่ให้ขึ้นกับ cwd
        venv_ytdlp = _PROJECT_ROOT / ".venv" / "Scripts" / "yt-dlp.exe"
        if not shutil.which("yt-dlp") and not venv_ytdlp.exists():
            return "Error: กรุณาลง yt-dlp ในเครื่องก่อนใช้งานทูลนี้"
        if not shutil.which("mpv"):
            return "Error: ไม่พบโปรแกรม 'mpv' ในคอมพิวเตอร์ของคุณ กรุณาพิมพ์คำสั่ง 'winget install mpv.mpv' บน Terminal ก่อนครับ"
            
        try:
            cmd = f'yt-dlp "ytsearch1:{song_name}" --get-url --format bestaudio'
            stream_url_res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
            stream_url = stream_url_res.stdout.strip()
            
            if not stream_url:
                return f"Error: ค้นหาเพลง '{song_name}' ไม่พบ"
                
            subprocess.Popen(["mpv", "--no-video", stream_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"🎵 [Background Player] กำลังเริ่มสตรีมเฉพาะเสียงเพลง '{song_name}' ให้ฟังบนหลังบ้านเรียบร้อยแล้ว!"
            
        except Exception as e:
            return f"Error streaming audio: {str(e)}"

    @mcp.tool()
    def press_system_media_key(action: str) -> str:
        """
        ควบคุมระบบมัลติมีเดียบนคอมพิวเตอร์ของผู้ใช้โดยตรง (เล่นเพลง, หยุดเพลง, เพิ่ม-ลดเสียง)
        :param action: สั่งการระบุได้แก่ 'play_pause' (เล่น/หยุด), 'next' (เพลงถัดไป), 'volume_up' (เพิ่มเสียง), 'volume_down' (ลดเสียง)
        """
        import pyautogui  # lazy import — ป้องกัน crash บนเครื่องไม่มี GUI

        print(f"[OS Control] Media key action: {action}")
        try:
            if action == "play_pause":
                pyautogui.press("playpause")
            elif action == "next":
                pyautogui.press("nexttrack")
            elif action == "volume_up":
                pyautogui.press("volumeup")
            elif action == "volume_down":
                pyautogui.press("volumedown")
            else:
                return "Error: Action ไม่ถูกต้อง"
            return f"Success: สั่งงานระบบสื่อสารมัลติมีเดียปุ่ม '{action}' สำเร็จแล้ว"
        except Exception as e:
            return f"Error executing media key: {str(e)}"
