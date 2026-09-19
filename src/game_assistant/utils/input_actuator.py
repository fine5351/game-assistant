import time
import threading
from typing import Optional, List, Dict, Any

try:
    from pynput.keyboard import Controller as KeyboardController, Key
    from pynput.mouse import Controller as MouseController, Button
    PYNPUT_AVAILABLE = True
except ImportError:
    KeyboardController = None
    MouseController = None
    Key = None
    Button = None
    PYNPUT_AVAILABLE = False


class ScreenActuator:
    """
    遊戲螢幕操作致動器 (Screen Actuator)
    支援透過 pynput 模擬實體鍵盤與滑鼠操作，實現「代替操作」能力。
    具備緊急安全熔斷開關 (Emergency Stop)、冷卻防洪保護與操作歷史稽核追蹤。
    """

    def __init__(self, action_cooldown: float = 0.15):
        self.action_cooldown = action_cooldown
        self._is_enabled = False  # 預設需手動開啓「代替操作」模式
        self._lock = threading.Lock()
        self._last_action_time = 0.0
        self._action_history: List[Dict[str, Any]] = []
        self._max_history = 50
        self._held_keys = set()
        self._held_mouse_buttons = set()

        # 初始化控制器
        if PYNPUT_AVAILABLE:
            try:
                self._keyboard = KeyboardController()
                self._mouse = MouseController()
            except Exception as e:
                print(f"[ScreenActuator] 控制器初始化失敗: {e}")
                self._keyboard = None
                self._mouse = None
        else:
            self._keyboard = None
            self._mouse = None

    @property
    def is_enabled(self) -> bool:
        return self._is_enabled

    def enable(self):
        """啟用代替操作 (螢幕自動操控)"""
        with self._lock:
            self._is_enabled = True

    def disable(self):
        """禁用代替操作"""
        with self._lock:
            self._is_enabled = False

    def emergency_stop(self):
        """
        緊急停止開關 (F8 / ESC)
        立即終止代替操作，解除所有鍵盤按鍵與滑鼠按下狀態
        """
        with self._lock:
            self._is_enabled = False
            self._record_action("EMERGENCY_STOP", {"reason": "User triggered emergency stop"})

            # 強制釋放所有記錄中按下的鍵
            if self._keyboard:
                for k in list(self._held_keys):
                    try:
                        self._keyboard.release(k)
                    except Exception:
                        pass
                self._held_keys.clear()

                # 安全釋放常見遊戲修改鍵與動作鍵
                if Key:
                    common_keys = [
                        Key.shift, Key.ctrl, Key.alt, Key.space,
                        'w', 'a', 's', 'd', 'q', 'e', 'r', 'f', '1', '2', '3', '4'
                    ]
                    for k in common_keys:
                        try:
                            self._keyboard.release(k)
                        except Exception:
                            pass

            if self._mouse and Button:
                for b in list(self._held_mouse_buttons):
                    try:
                        self._mouse.release(b)
                    except Exception:
                        pass
                self._held_mouse_buttons.clear()
                try:
                    self._mouse.release(Button.left)
                    self._mouse.release(Button.right)
                except Exception:
                    pass

    def can_act(self) -> bool:
        """檢查是否允許發送螢幕操作指令 (非鎖內簡易檢查)"""
        if not self._is_enabled:
            return False
        now = time.perf_counter()
        if now - self._last_action_time < self.action_cooldown:
            return False
        return True

    def press_key(self, key_name: str, hold_sec: float = 0.05) -> bool:
        """
        模擬按下並放開指定鍵盤按鍵
        :param key_name: 按鍵名稱 (如 'e', 'q', 'space', '1', 'shift')
        :param hold_sec: 按住時間 (秒)
        :return: 是否成功觸發
        """
        with self._lock:
            if not self._is_enabled:
                return False
            now = time.perf_counter()
            if now - self._last_action_time < self.action_cooldown:
                return False
            self._last_action_time = now
            self._record_action("KEY_PRESS", {"key": key_name, "hold": hold_sec})

            if not self._keyboard:
                return True

            key_obj = self._resolve_key(key_name)
            if key_obj is None:
                return False

            try:
                self._held_keys.add(key_obj)
                self._keyboard.press(key_obj)
                time.sleep(hold_sec)
                self._keyboard.release(key_obj)
                self._held_keys.discard(key_obj)
                return True
            except Exception as e:
                print(f"[ScreenActuator] 按鍵模擬異常 ({key_name}): {e}")
                return False
            finally:
                if key_obj in self._held_keys:
                    try:
                        self._keyboard.release(key_obj)
                    except Exception:
                        pass
                    self._held_keys.discard(key_obj)

    def click_mouse(self, button_name: str = "left", count: int = 1) -> bool:
        """
        模擬滑鼠點擊
        :param button_name: 'left', 'right', 'middle'
        :param count: 點擊次數
        """
        with self._lock:
            if not self._is_enabled:
                return False
            now = time.perf_counter()
            if now - self._last_action_time < self.action_cooldown:
                return False
            self._last_action_time = now
            self._record_action("MOUSE_CLICK", {"button": button_name, "count": count})

            if not self._mouse or not Button:
                return True

            btn = Button.left
            if button_name.lower() == "right":
                btn = Button.right
            elif button_name.lower() == "middle":
                btn = Button.middle

            try:
                self._held_mouse_buttons.add(btn)
                self._mouse.click(btn, count)
                self._held_mouse_buttons.discard(btn)
                return True
            except Exception as e:
                print(f"[ScreenActuator] 滑鼠模擬異常 ({button_name}): {e}")
                return False
            finally:
                if btn in self._held_mouse_buttons:
                    try:
                        self._mouse.release(btn)
                    except Exception:
                        pass
                    self._held_mouse_buttons.discard(btn)

    def _resolve_key(self, key_name: str):
        """解析常見遊戲按鍵別名為 pynput Key 或字元"""
        k = key_name.lower().strip()
        if Key:
            key_map = {
                "space": Key.space,
                "shift": Key.shift,
                "ctrl": Key.ctrl,
                "alt": Key.alt,
                "enter": Key.enter,
                "esc": Key.esc,
                "tab": Key.tab,
                "left": Key.left,
                "right": Key.right,
                "up": Key.up,
                "down": Key.down,
                "f1": Key.f1,
                "f2": Key.f2,
                "f3": Key.f3,
                "f4": Key.f4,
                "f5": Key.f5,
                "f6": Key.f6,
                "f7": Key.f7,
                "f8": Key.f8,
                "f9": Key.f9,
                "f10": Key.f10,
                "f11": Key.f11,
                "f12": Key.f12,
            }
            if k in key_map:
                return key_map[k]
        if len(k) == 1:
            return k
        return None

    def _record_action(self, action_type: str, details: Dict[str, Any]):
        entry = {
            "timestamp": time.time(),
            "type": action_type,
            "details": details
        }
        self._action_history.append(entry)
        if len(self._action_history) > self._max_history:
            self._action_history.pop(0)

    def copy_to_clipboard(self, text: str) -> bool:
        """將指定文字寫入系統剪貼簿 (支援 pyperclip 與 Win32 64-bit ctypes 雙重降級)"""
        try:
            import pyperclip
            pyperclip.copy(text)
            return True
        except Exception:
            pass

        try:
            import ctypes
            u32 = ctypes.windll.user32
            k32 = ctypes.windll.kernel32

            k32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
            k32.GlobalAlloc.restype = ctypes.c_void_p
            k32.GlobalLock.argtypes = [ctypes.c_void_p]
            k32.GlobalLock.restype = ctypes.c_void_p
            k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            k32.GlobalUnlock.restype = ctypes.c_int
            u32.OpenClipboard.argtypes = [ctypes.c_void_p]
            u32.OpenClipboard.restype = ctypes.c_int
            u32.EmptyClipboard.argtypes = []
            u32.EmptyClipboard.restype = ctypes.c_int
            u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
            u32.SetClipboardData.restype = ctypes.c_void_p
            u32.CloseClipboard.argtypes = []
            u32.CloseClipboard.restype = ctypes.c_int

            if not u32.OpenClipboard(None):
                return False

            try:
                u32.EmptyClipboard()
                text_bytes = text.encode('utf-16le') + b'\x00\x00'
                # GHND = GMEM_MOVEABLE (0x0002) | GMEM_ZEROINIT (0x0040)
                h_mem = k32.GlobalAlloc(0x0042, len(text_bytes))
                if not h_mem:
                    return False

                p_mem = k32.GlobalLock(h_mem)
                if not p_mem:
                    k32.GlobalFree(h_mem)
                    return False

                ctypes.cdll.msvcrt.memcpy(ctypes.c_void_p(p_mem), text_bytes, len(text_bytes))
                k32.GlobalUnlock(h_mem)
                # CF_UNICODETEXT = 13
                u32.SetClipboardData(13, h_mem)
                return True
            finally:
                u32.CloseClipboard()
        except Exception as e:
            print(f"[ScreenActuator] 剪貼簿寫入異常: {e}")
            return False

    def paste_text_to_chat(
        self,
        text: str,
        enter_chat_key: Optional[str] = "enter",
        submit: bool = True,
        force: bool = True
    ) -> bool:
        """
        將翻譯文字輸入至遊戲文字聊天框中
        支援以剪貼簿貼上 (Ctrl+V) 確保跨語言與特殊字元正確輸入
        :param text: 要輸入的翻譯文字
        :param enter_chat_key: 開啟聊天框的按鍵 (預設為 'enter'，若為 None 則假定聊天框已開啟)
        :param submit: 輸入後是否按 Enter 發送訊息
        :param force: 是否強制執行 (語音翻譯專屬致動即使在指導模式亦允許發送)
        :return: 是否成功執行
        """
        if not text or not text.strip():
            return False

        with self._lock:
            if not force and not self._is_enabled:
                return False

            # 複製至系統剪貼簿
            clipboard_ok = self.copy_to_clipboard(text.strip())
            self._record_action("CHAT_PASTE", {
                "text": text.strip(),
                "enter_chat_key": enter_chat_key,
                "submit": submit,
                "clipboard_ok": clipboard_ok
            })

            if not self._keyboard or not Key:
                return clipboard_ok

            try:
                # 1. 開啟遊戲聊天輸入框 (若有指定)
                if enter_chat_key:
                    k_open = self._resolve_key(enter_chat_key)
                    if k_open is not None:
                        try:
                            self._keyboard.press(k_open)
                            time.sleep(0.04)
                        finally:
                            self._keyboard.release(k_open)
                        time.sleep(0.12)  # 等待遊戲呼叫出聊天框

                # 2. 模擬 Ctrl+V 貼上剪貼簿內容 (嚴格 try/finally 防按鍵卡死)
                self._keyboard.press(Key.ctrl)
                try:
                    time.sleep(0.02)
                    self._keyboard.press('v')
                    try:
                        time.sleep(0.03)
                    finally:
                        self._keyboard.release('v')
                    time.sleep(0.02)
                finally:
                    self._keyboard.release(Key.ctrl)
                time.sleep(0.08)

                # 3. 發送訊息 (按下 Enter 提交)
                if submit:
                    self._keyboard.press(Key.enter)
                    try:
                        time.sleep(0.04)
                    finally:
                        self._keyboard.release(Key.enter)

                return True
            except Exception as e:
                print(f"[ScreenActuator] paste_text_to_chat 模擬異常: {e}")
                return False

    def type_text(self, text: str, auto_enter: bool = False) -> bool:
        """
        直接鍵盤輸入字串
        :param text: 字串內容
        :param auto_enter: 是否自動在末尾按 Enter
        """
        if not text:
            return False

        with self._lock:
            self._record_action("TYPE_TEXT", {"text": text, "auto_enter": auto_enter})
            if not self._keyboard:
                return self.copy_to_clipboard(text)

            try:
                self._keyboard.type(text)
                if auto_enter and Key:
                    time.sleep(0.03)
                    self._keyboard.press(Key.enter)
                    try:
                        time.sleep(0.03)
                    finally:
                        self._keyboard.release(Key.enter)
                return True
            except Exception as e:
                print(f"[ScreenActuator] type_text 異常: {e}")
                return False

    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._action_history[-limit:])


if __name__ == "__main__":
    actuator = ScreenActuator(action_cooldown=0.1)
    print(f"ScreenActuator 初始化成功 (pynput available: {PYNPUT_AVAILABLE})")
    print(f"預設狀態 is_enabled: {actuator.is_enabled}")
    actuator.enable()
    print(f"啟用後 is_enabled: {actuator.is_enabled}")
    actuator.emergency_stop()
    print(f"F8 急停後 is_enabled: {actuator.is_enabled}")

