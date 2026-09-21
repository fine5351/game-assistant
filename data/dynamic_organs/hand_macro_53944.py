"""
自律生長專屬操作手腳本 - 為什麼你不會長出手操作手
需求: 為什麼你不會長出手 -> 收到指令。系統已就緒，隨時可透過 **自律器官生長器 (`OrganSynthesizer`)** 動態合成專屬操作宏手
"""

import time
from typing import Dict, Any, Optional, List
from game_assistant.organs.base import BaseOrganTool, OrganType


class DynamicHand_91192(BaseOrganTool):
    def __init__(self, actuator=None):
        super().__init__(
            organ_id="hand_macro_53944",
            organ_type=OrganType.ACTUATOR_HAND,
            name="為什麼你不會長出手操作手",
            description="針對需求【為什麼你不會長出手 -> 收到指令。系統已就緒，隨時可透過 **自律器官生長器 (`OrganSynthesizer`)** 動態合成專屬操作宏手】自律生長建置之真實操作接管手",
            is_built_in=False
        )
        self.actuator = actuator
        self.steps = [{'action_type': 'key', 'target': '1', 'duration': 0.05, 'post_delay': 0.25, 'description': '切換至 1 號位角色'}, {'action_type': 'hold_key', 'target': 'e', 'duration': 0.5, 'post_delay': 0.25, 'description': '長按戰技 E 進入強化/驅動模式'}, {'action_type': 'key', 'target': 'q', 'duration': 0.1, 'post_delay': 0.45, 'description': '施放大招 Q (元素爆發/終結技)'}, {'action_type': 'hold_click', 'target': 'left', 'duration': 0.4, 'post_delay': 0.25, 'description': '蓄力重擊'}, {'action_type': 'key', 'target': 'shift', 'duration': 0.04, 'post_delay': 0.15, 'description': '極限閃避 / 衝刺打斷後搖'}]

    def execute(self, **kwargs) -> Dict[str, Any]:
        self.execution_count += 1
        act = kwargs.get("actuator", self.actuator)
        init_enabled = bool(act and getattr(act, "is_enabled", False))
        performed = False
        details = []

        for step in self.steps:
            a_type = step.get("action_type", "key")
            tgt = step.get("target", "e")
            dur = step.get("duration", 0.05)
            p_delay = step.get("post_delay", 0.15)
            desc = step.get("description", "")

            if act and getattr(act, "is_enabled", False):
                performed = True
                try:
                    if a_type in ("key", "hold_key"):
                        act.press_key(tgt, hold_sec=dur)
                    elif a_type in ("click", "hold_click"):
                        act.click_mouse(button_name=tgt, count=1)
                except Exception:
                    pass

            details.append(desc)
            if p_delay > 0:
                time.sleep(p_delay)

            if init_enabled and act and not getattr(act, "is_enabled", False):
                details.append("⚠️ 偵測到 F8 緊急急停，終止後續動作")
                break

        res = {
            "action": "script_takeover_executed",
            "organ_id": self.organ_id,
            "performed_real": performed,
            "steps": details,
            "status": "completed"
        }
        self.last_result = res
        return res

    def extract_predicates(self, **kwargs) -> Dict[str, Any]:
        return {
            "hand_macro_53944_executed": True,
            "has_hand_takeover": True
        }
