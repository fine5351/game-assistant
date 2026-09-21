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


class DynamicActionScriptHand(BaseOrganTool):
    """
    自律生長操作手：動態按鍵腳本接管手 (Dynamic Action Script Hand)
    由大腦與動作序列抽取器即時生長建置，直接承載真實鍵鼠動作序列並執行操作接管。
    """

    def __init__(
        self,
        organ_id: str,
        name: str,
        steps: Optional[List[Any]] = None,
        actuator: Optional[ScreenActuator] = None,
        requirement: str = ""
    ):
        super().__init__(
            organ_id=organ_id,
            organ_type=OrganType.ACTUATOR_HAND,
            name=name,
            description=f"針對需求【{requirement or name}】自律生長建置之真實鍵鼠操作接管手",
            is_built_in=False
        )
        self.steps = steps or []
        self.actuator = actuator
        self.requirement = requirement

    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        執行操作腳本接管
        依序執行每個 ActionStep，遇 F8 緊急停止中斷
        """
        self.execution_count += 1
        executed_details = []
        performed_real = False

        # 優先取用 kwargs 傳入的 actuator
        actuator = kwargs.get("actuator", self.actuator)
        initially_enabled = bool(actuator and getattr(actuator, "is_enabled", False))

        for i, step in enumerate(self.steps):
            # 若為字典則相容轉換
            action_type = getattr(step, "action_type", None) or (step.get("action_type") if isinstance(step, dict) else "key")
            target = getattr(step, "target", None) or (step.get("target") if isinstance(step, dict) else "e")
            duration = getattr(step, "duration", None) or (step.get("duration") if isinstance(step, dict) else 0.05)
            post_delay = getattr(step, "post_delay", None) or (step.get("post_delay") if isinstance(step, dict) else 0.15)
            desc = getattr(step, "description", None) or (step.get("description") if isinstance(step, dict) else f"Step {i+1}")

            if actuator and actuator.is_enabled:
                performed_real = True
                try:
                    if action_type in ("key", "hold_key"):
                        actuator.press_key(target, hold_sec=duration)
                    elif action_type in ("click", "hold_click"):
                        actuator.click_mouse(button_name=target, count=1)
                except Exception as e:
                    print(f"[DynamicActionScriptHand] 執行步驟失敗 ({desc}): {e}")

            executed_details.append(desc)

            # 步驟間間隔時間
            if post_delay > 0:
                time.sleep(post_delay)

            # 檢查是否觸發 F8 急停 (原本為啟用但在中途被急停禁用)
            if initially_enabled and actuator and not actuator.is_enabled:
                executed_details.append("⚠️ 偵測到 F8 緊急急停，終止後續動作")
                break

        result = {
            "action": "dynamic_script_takeover",
            "organ_id": self.organ_id,
            "name": self.name,
            "requirement": self.requirement,
            "performed_real": performed_real,
            "steps_count": len(self.steps),
            "executed_steps": executed_details,
            "status": "completed"
        }
        self.last_result = result
        return result

    def extract_predicates(self, **kwargs) -> Dict[str, Any]:
        return {
            f"{self.organ_id}_executed": True,
            f"{self.organ_id}_steps": len(self.steps),
            "has_hand_takeover": True
        }

    def generate_python_code(self) -> str:
        """生成符合 AST 審查規範的專屬 Python 腳本代碼"""
        steps_repr = []
        for s in self.steps:
            if hasattr(s, "to_dict"):
                steps_repr.append(s.to_dict())
            elif isinstance(s, dict):
                steps_repr.append(s)
            else:
                steps_repr.append({"action_type": "key", "target": str(s), "duration": 0.05, "post_delay": 0.15})

        clean_req = self.requirement.replace("\n", " ").replace('"', "'").strip()
        clean_name = self.name.replace("\n", " ").replace('"', "'").strip()
        class_name = f"DynamicHand_{abs(hash(self.organ_id)) % 100000}"
        return f'''"""
自律生長專屬操作手腳本 - {clean_name}
需求: {clean_req}
"""

import time
from typing import Dict, Any, Optional, List
from game_assistant.organs.base import BaseOrganTool, OrganType


class {class_name}(BaseOrganTool):
    def __init__(self, actuator=None):
        super().__init__(
            organ_id="{self.organ_id}",
            organ_type=OrganType.ACTUATOR_HAND,
            name="{clean_name}",
            description="針對需求【{clean_req}】自律生長建置之真實操作接管手",
            is_built_in=False
        )
        self.actuator = actuator
        self.steps = {repr(steps_repr)}

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

        res = {{
            "action": "script_takeover_executed",
            "organ_id": self.organ_id,
            "performed_real": performed,
            "steps": details,
            "status": "completed"
        }}
        self.last_result = res
        return res

    def extract_predicates(self, **kwargs) -> Dict[str, Any]:
        return {{
            "{self.organ_id}_executed": True,
            "has_hand_takeover": True
        }}
'''
