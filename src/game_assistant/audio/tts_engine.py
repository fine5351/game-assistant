if __name__ == "__main__" and not __package__:
    import sys
    from pathlib import Path
    _src = str(Path(__file__).resolve().parents[2])
    if _src not in sys.path:
        sys.path.insert(0, _src)

import re
import pyttsx3
from game_assistant.core.config import TTS_RATE, TTS_VOLUME

try:
    import pythoncom
except ImportError:
    pythoncom = None


def clean_markdown_for_tts(text: str) -> str:
    """
    清除 Markdown 標點符號、代碼塊、網址與 Emoji，轉為適合 TTS 朗讀的純文字
    """
    if not text:
        return ""

    # 1. 移除 Markdown 代碼區塊 ```...```
    text = re.sub(r'```[\s\S]*?```', '', text)
    # 2. 移除行內代碼 `...`
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # 3. 移除 Markdown 連結 [標題](URL) -> 僅保留標題
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # 4. 移除 HTTP/HTTPS URL
    text = re.sub(r'https?://\S+', '', text)
    # 5. 移除 Markdown 語法符號 (#, *, _, ~, >, |, +, -)
    text = re.sub(r'[#*\_~>|]', ' ', text)
    # 6. 移除條列項目開頭標記 (如 - 或 1.)
    text = re.sub(r'^\s*[\-\+\*]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # 7. 移除常用的 Emoji 符號與特殊字元
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    text = re.sub(r'[\u2600-\u27BF]', '', text)
    text = re.sub(r'[\u2300-\u23FF]', '', text)

    # 8. 整理換行與連續空白
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned_text = " ".join(lines)
    return cleaned_text


class TTSEngine:
    """
    Windows SAPI5 離線 TTS 語音朗讀引擎
    支援語速/音量設定、繁簡體中文語音選擇與 COM 線程防護
    """

    def __init__(self, rate: int = TTS_RATE, volume: float = TTS_VOLUME):
        self.rate = rate
        self.volume = volume
        self._current_engine = None

    def speak(self, text: str):
        """
        將 Markdown 報告淨化後進行背景語音朗讀
        :param text: Markdown 或原始文字
        """
        cleaned_text = clean_markdown_for_tts(text)
        if not cleaned_text:
            return

        # COM 執行緒安全初始化
        if pythoncom:
            try:
                pythoncom.CoInitialize()
            except Exception:
                pass

        try:
            # 優先嘗試 SAPI5
            try:
                engine = pyttsx3.init('sapi5')
            except Exception:
                engine = pyttsx3.init()

            self._current_engine = engine
            engine.setProperty('rate', self.rate)
            engine.setProperty('volume', self.volume)

            # 搜尋可用之中文語音包
            try:
                voices = engine.getProperty('voices')
                for voice in voices:
                    voice_str = (str(voice.id) + " " + str(voice.name)).lower()
                    if any(k in voice_str for k in ["zh", "chinese", "hanhan", "huihui", "yating", "taiwan", "tradi", "zhtw"]):
                        engine.setProperty('voice', voice.id)
                        break
            except Exception as e:
                print(f"[TTSEngine] 選擇語音包發生提醒: {e}")

            engine.say(cleaned_text)
            engine.runAndWait()
        except Exception as e:
            print(f"[TTSEngine] 語音播報異常: {e}")
        finally:
            if self._current_engine:
                try:
                    self._current_engine.stop()
                except Exception:
                    pass
                self._current_engine = None
            if pythoncom:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def stop(self):
        """強行中斷目前語音朗讀"""
        if self._current_engine:
            try:
                self._current_engine.stop()
            except Exception:
                pass


if __name__ == "__main__":
    # 測試文字淨化與 TTS
    test_md = "### 1. **敵我戰術建議**:\n- ⚡ `使用技能E` 切換 [原神](https://example.com) 角色！"
    cleaned = clean_markdown_for_tts(test_md)
    print("淨化後文字:", cleaned)
    engine = TTSEngine()
    print("測試 TTS 播放...")
    engine.speak("Gemini 語音朗讀測試成功。")
