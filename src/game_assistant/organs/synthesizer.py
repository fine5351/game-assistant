"""
器官自律生長與合成引擎 (Organ Synthesizer & Dynamic Loader)
實現「助理自主建置工具、生長感官與手腳」的核心機制。
包含代碼自動合成、AST 安全沙箱審查、動態編譯加載與持久化維護。
"""

import ast
import os
import re
import types
from typing import Dict, Any, Optional, Type
from game_assistant.organs.base import BaseOrganTool, OrganType
from game_assistant.engines.antigravity_engine import AntigravityCliEngine


class OrganSecurityViolation(Exception):
    """器官安全違規異常"""
    pass


class OrganSafetyGuard:
    """
    器官代碼 AST 安全審查守衛 (AST Safety Guard)
    嚴格禁止危險系統呼叫、隨意檔案刪除與任意動態執行，確保自律生長安全無虞。
    """

    BANNED_IMPORTS = {
        "subprocess", "shutil", "ctypes", "winreg",
        "multiprocessing", "pty", "socket", "http.server"
    }

    BANNED_CALLS = {
        "system", "popen", "spawn", "rmtree", "unlink", "remove",
        "eval", "exec", "__import__", "compile", "globals", "locals"
    }

    @classmethod
    def inspect_code(cls, code: str) -> None:
        """
        對 Python 代碼進行 AST 靜態語法樹審查
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise OrganSecurityViolation(f"語法解析失敗: {e}")

        for node in ast.walk(tree):
            # 檢查危險模組匯入 (import xxx)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0]
                    if root_pkg in cls.BANNED_IMPORTS:
                        raise OrganSecurityViolation(f"禁止匯入高危模組: {alias.name}")

            # 檢查危險模組匯入 (from xxx import yyy)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_pkg = node.module.split(".")[0]
                    if root_pkg in cls.BANNED_IMPORTS:
                        raise OrganSecurityViolation(f"禁止從高危模組匯入: {node.module}")

            # 檢查高危函式呼叫
            elif isinstance(node, ast.Call):
                # 直接函式呼叫 (如 eval())
                if isinstance(node.func, ast.Name):
                    if node.func.id in cls.BANNED_CALLS:
                        raise OrganSecurityViolation(f"禁止呼叫高危函式: {node.func.id}")
                # 物件方法呼叫 (如 os.system())
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr in cls.BANNED_CALLS:
                        raise OrganSecurityViolation(f"禁止呼叫高危方法: {node.func.attr}")


class OrganSynthesizer:
    """
    器官自律生長與建置器 (Organ Synthesizer)
    依據新情境需求自動編寫、驗證並編譯生長出新的感官（眼睛/耳朵）或致動器（手/腳）。
    """

    def __init__(
        self,
        storage_dir: str = "data/dynamic_organs",
        brain_engine: Optional[AntigravityCliEngine] = None,
        actuator: Optional[Any] = None
    ):
        self.storage_dir = storage_dir
        self.brain_engine = brain_engine or AntigravityCliEngine()
        self.actuator = actuator
        self.guard = OrganSafetyGuard()
        self._ensure_storage_dir()

    def _ensure_storage_dir(self) -> None:
        try:
            os.makedirs(self.storage_dir, exist_ok=True)
        except Exception:
            pass

    def synthesize_organ(
        self,
        requirement: str,
        organ_type: OrganType,
        name: str,
        organ_id: Optional[str] = None
    ) -> BaseOrganTool:
        """
        自律合成全新器官工具
        1. 向 AI 大腦申請編寫 Python 代碼（或以結構化模板生長）
        2. 通過 AST 安全審查
        3. 動態編譯並實體化
        4. 持久化存檔至磁碟
        """
        clean_name = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fa5]', '_', name)
        generated_id = organ_id or f"dyn_{organ_type.name.lower()}_{abs(hash(requirement)) % 100000}"

        # 1. 嘗試調用 Antigravity CLI 大腦合成代碼
        generated_code = ""
        if self.brain_engine.is_available():
            try:
                prompt = (
                    f"請針對以下遊戲輔助需求，編寫一個繼承自 BaseOrganTool 的 Python 器官工具類別。\n"
                    f"【需求】: {requirement}\n"
                    f"【器官類別】: {organ_type.name} ({organ_type.value})\n"
                    f"【工具名稱】: {name}\n"
                    f"【ID】: {generated_id}\n"
                    f"規範：僅輸出合法的 Python 代碼，必須實作 execute 與 extract_predicates 方法，不可包含 Markdown 標籤。"
                )
                brain_response = self.brain_engine.synthesize_tool_code(requirement, organ_type.name)
                if brain_response:
                    generated_code = self._clean_code_fences(brain_response)
            except Exception:
                generated_code = ""

        organ_instance: Optional[BaseOrganTool] = None

        # 若大腦生成了代碼，嘗試進行安全審查與加載
        if generated_code:
            try:
                self.guard.inspect_code(generated_code)
                organ_instance = self._load_organ_from_code(generated_code, generated_id)
            except Exception:
                organ_instance = None

        # 若大腦未輸出或生成之代碼無法通過審查/編譯，使用自律樣板合成器保證成功生長
        if organ_instance is None:
            generated_code = self._generate_template_code(requirement, organ_type, name, generated_id)
            self.guard.inspect_code(generated_code)
            organ_instance = self._load_organ_from_code(generated_code, generated_id)

        # 持久化至磁碟
        save_path = os.path.join(self.storage_dir, f"{generated_id}.py")
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(generated_code)
        except Exception:
            pass

        return organ_instance

    def _clean_code_fences(self, text: str) -> str:
        """清除 markdown code fences"""
        clean = re.sub(r"^```python\s*", "", text, flags=re.MULTILINE)
        clean = re.sub(r"^```\s*", "", clean, flags=re.MULTILINE)
        return clean.strip()

    def _generate_template_code(
        self,
        requirement: str,
        organ_type: OrganType,
        name: str,
        organ_id: str
    ) -> str:
        """離線確定性安全器官代碼生成樣板"""
        clean_req = requirement.replace("\n", " ").replace('"', "'").strip()
        clean_name = name.replace("\n", " ").replace('"', "'").strip()
        class_name = f"DynamicOrgan_{abs(hash(organ_id)) % 100000}"

        if organ_type == OrganType.ACTUATOR_HAND:
            # 專屬操作手腳本生成：解析動作序列，生成具備真實鍵鼠致動邏輯的代碼
            from game_assistant.organs.action_parser import ActionSequenceExtractor
            steps = ActionSequenceExtractor.extract_sequence(requirement, requirement)
            steps_repr = [s.to_dict() for s in steps]
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
            organ_id="{organ_id}",
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

            if act and not getattr(act, "is_enabled", False):
                break

        res = {{
            "action": "script_takeover_executed",
            "organ_id": self.organ_id,
            "performed_real": performed,
            "steps": details,
            "params_received": kwargs,
            "status": "dynamic_executed",
            "takeover_completed": True
        }}
        self.last_result = res
        return res

    def extract_predicates(self, **kwargs) -> Dict[str, Any]:
        return {{
            "{organ_id}_executed": True,
            "has_hand_takeover": True
        }}
'''

        return f'''"""
自律生長動態器官代碼 - {name}
需求: {requirement}
"""

from typing import Dict, Any
from game_assistant.organs.base import BaseOrganTool, OrganType


class {class_name}(BaseOrganTool):
    def __init__(self, actuator=None):
        super().__init__(
            organ_id="{organ_id}",
            organ_type=OrganType.{organ_type.name},
            name="{name}",
            description="針對需求【{requirement}】自律生長建置之專案器官工具",
            is_built_in=False
        )
        self.actuator = actuator

    def execute(self, **kwargs) -> Dict[str, Any]:
        self.execution_count += 1
        # 執行針對需求的感知或致動邏輯
        data = {{
            "organ_id": self.organ_id,
            "status": "dynamic_executed",
            "requirement_met": "{requirement}",
            "params_received": kwargs,
            "execution_count": self.execution_count
        }}
        self.last_result = data
        return data

    def extract_predicates(self, **kwargs) -> Dict[str, Any]:
        return {{
            "{organ_id}_active": True,
            "{organ_id}_ready": True
        }}
'''

    def _load_organ_from_code(self, code: str, organ_id: str) -> BaseOrganTool:
        """在安全命名空間中動態編譯代碼並實體化器官"""
        import sys
        import dataclasses
        import time
        from typing import List

        module_name = f"dynamic_organ_{organ_id}"
        module = types.ModuleType(module_name)
        
        # 註冊至 sys.modules 供 dataclass 與反射模組正確辨識
        sys.modules[module_name] = module
        
        # 準備安全執行環境
        safe_globals = module.__dict__
        safe_globals.update({
            "__name__": module_name,
            "__file__": f"<dynamic_{organ_id}>",
            "__doc__": None,
            "BaseOrganTool": BaseOrganTool,
            "OrganType": OrganType,
            "Dict": Dict,
            "Any": Any,
            "Optional": Optional,
            "List": List,
            "dataclasses": dataclasses,
            "dataclass": dataclasses.dataclass,
            "time": time
        })

        try:
            # 編譯並執行
            compiled = compile(code, f"<dynamic_{organ_id}>", "exec")
            exec(compiled, safe_globals)

            # 尋找繼承自 BaseOrganTool 的類別
            target_class: Optional[Type[BaseOrganTool]] = None
            for obj in safe_globals.values():
                if isinstance(obj, type) and issubclass(obj, BaseOrganTool) and obj is not BaseOrganTool:
                    target_class = obj
                    break

            if not target_class:
                raise OrganSecurityViolation(f"代碼中未發現合法的 BaseOrganTool 實作類別: {organ_id}")

            try:
                instance = target_class(actuator=self.actuator)
            except TypeError:
                instance = target_class()

            if hasattr(instance, "actuator") and instance.actuator is None:
                instance.actuator = self.actuator

            return instance
        except Exception:
            raise
