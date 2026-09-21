"""
預裝致動器官 (Actuator Organs: Hands and Feet)
包含閃避取消後搖手、連招爆發手與探索跑圖腳。
"""

import time
from typing import Dict, Any, Optional, List
from game_assistant.organs.base import BaseOrganTool, OrganType
from game_assistant.utils.input_actuator import ScreenActuator


class DodgeCancelHand(BaseOrganTool):
    """
    致動操作手：閃避取消後搖宏 (Dodge Cancel Hand)
    在普通攻擊或重擊後搖階段，精準觸發短按閃避 (Dash/Dodge) 打斷後搖動畫並迅速重置攻擊幀。
    """

    def __init__(self, actuator: Optional[ScreenActuator] = None, organ_id: str = "hand_dodge_cancel"):
        super().__init__(
            organ_id=organ_id,
            organ_type=OrganType.ACTUATOR_HAND,
            name="閃避取消後搖手",
            description="精準利用衝刺/滑步打斷重擊或連招後搖，提高 DPS 並維持機動性",
            is_built_in=True
        )
        self.actuator = actuator

    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        執行後搖取消宏
        支援參數: key (預設 'shift' 或右鍵), follow_up (後續動作 'attack')
        """
        self.execution_count += 1
        follow_up = kwargs.get("follow_up", "attack")
        performed_real = False

        if self.actuator and self.actuator.is_enabled:
            # 真實致動操作
            try:
                self.actuator.press_key("shift", duration=0.03)
                time.sleep(0.04)
                if follow_up == "attack":
                    self.actuator.click_mouse("left")
                performed_real = True
            except Exception:
                performed_real = False

        result = {
            "action": "dodge_cancel_macro",
            "performed_real": performed_real,
            "steps": ["dash_cancel", f"follow_up_{follow_up}"],
            "frame_advantage_saved_ms": 320
        }
        self.last_result = result
        return result

    def extract_predicates(self, **kwargs) -> Dict[str, Any]:
        return {
            "can_dodge_cancel": True,
            "hand_state": "ready"
        }


class ElementalComboHand(BaseOrganTool):
    """
    致動操作手：元素連招與終結技爆發宏 (Elemental Combo Hand)
    執行快速戰技釋放 ➔ 切換角色 ➔ 爆發連攜之預設宏連打。
    """

    def __init__(self, actuator: Optional[ScreenActuator] = None, organ_id: str = "hand_elemental_combo"):
        super().__init__(
            organ_id=organ_id,
            organ_type=OrganType.ACTUATOR_HAND,
            name="元素爆發連招手",
            description="自動化執行戰技(E)、大招(Q)與隊友快速換人連鎖輸出宏",
            is_built_in=True
        )
        self.actuator = actuator

    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        執行連招宏
        支援參數: combo_sequence: List[str] (例如 ['e', 'q', '2', 'e'])
        """
        self.execution_count += 1
        sequence = kwargs.get("combo_sequence", ["e", "q"])
        performed_real = False

        if self.actuator and self.actuator.is_enabled:
            try:
                for step in sequence:
                    self.actuator.press_key(step, duration=0.05)
                    time.sleep(0.06)
                performed_real = True
            except Exception:
                performed_real = False

        result = {
            "action": "elemental_combo_macro",
            "performed_real": performed_real,
            "sequence": sequence,
            "status": "completed"
        }
        self.last_result = result
        return result

    def extract_predicates(self, **kwargs) -> Dict[str, Any]:
        return {
            "combo_available": True,
            "burst_ready": True
        }


class AutoLootSprintFoot(BaseOrganTool):
    """
    致動移動腳：自動跟跑與採集腳步宏 (Auto-Loot & Sprint Foot)
    控制前進方向鍵 (W) 連續衝刺，並以高頻發送互動/拾取鍵 (F) 實現大世界邊跑邊採。
    """

    def __init__(self, actuator: Optional[ScreenActuator] = None, organ_id: str = "foot_auto_loot_sprint"):
        super().__init__(
            organ_id=organ_id,
            organ_type=OrganType.ACTUATOR_FOOT,
            name="自動採集跟跑腳",
            description="大地圖探索時維持衝刺前進，同步快速連按互動拾取鍵採集周邊資源",
            is_built_in=True
        )
        self.actuator = actuator

    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        執行採集移動宏
        支援參數: duration_sec (持續秒數), loot_key (拾取鍵, 預設 'f')
        """
        self.execution_count += 1
        duration_sec = min(float(kwargs.get("duration_sec", 1.0)), 5.0)
        loot_key = kwargs.get("loot_key", "f")
        performed_real = False

        if self.actuator and self.actuator.is_enabled:
            try:
                start = time.time()
                self.actuator.key_down("w")
                while time.time() - start < duration_sec:
                    self.actuator.press_key(loot_key, duration=0.02)
                    time.sleep(0.1)
                self.actuator.key_up("w")
                performed_real = True
            except Exception:
                if self.actuator:
                    self.actuator.key_up("w")
                performed_real = False

        result = {
            "action": "auto_loot_sprint",
            "performed_real": performed_real,
            "duration": duration_sec,
            "loot_key": loot_key
        }
        self.last_result = result
        return result

    def extract_predicates(self, **kwargs) -> Dict[str, Any]:
        return {
            "foot_moving": bool(self.last_result and self.last_result.get("performed_real")),
            "auto_loot_active": True
        }
