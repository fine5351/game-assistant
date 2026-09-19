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
            }
            if k in key_map:
                return key_map[k]
        return k

    def _record_action(self, action_type: str, details: Dict[str, Any]):
        entry = {
            "timestamp": time.time(),
            "type": action_type,
            "details": details
        }
        self._action_history.append(entry)
        if len(self._action_history) > self._max_history:
            self._action_history.pop(0)

    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._action_history[-limit:])
