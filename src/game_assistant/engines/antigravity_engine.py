"""
Antigravity CLI 大腦驅動引擎 (Antigravity Brain Provider)

透過本機已授權之 agy.exe (Antigravity CLI) 與 AI 大腦進行推論互動：
1. 免除 GEMINI_API_KEY 限制與無效金鑰報錯
2. 原生支援思考深度分級: --effort medium (相似問題快速思考) vs --effort high (新問題深度慢思考)
3. 原生支援結構化 JSON 輸出與自律工具合成
4. 具備非同步/子行程逾時防禦，保證系統高可用性
"""

import os
import shutil
import subprocess
import threading
from typing import Optional, Dict, Any, List
from pathlib import Path

from game_assistant.core.config import GameType, AssistCapability


class AntigravityCliEngine:
    """
    Antigravity CLI 大腦引擎封裝
    優先探測本機路徑與系統 PATH 中的 agy 執行檔
    """

    KNOWN_SEARCH_PATHS = [
        r"C:\Users\User\AppData\Local\agy\bin\agy.exe",
        r"C:\Users\User\AppData\Local\Programs\Antigravity IDE\bin\agy.exe",
        r"D:\work\tool\Antigravity\bin\antigravity.cmd",
        r"C:\Users\User\.gemini\antigravity-cli\bin\agy.exe",
    ]

    def __init__(self, cli_path: Optional[str] = None):
        self.cli_path = cli_path or self._detect_cli_path()
        self._is_available: Optional[bool] = None
        self._lock = threading.Lock()

    def _detect_cli_path(self) -> Optional[str]:
        """自動探測本機 Antigravity CLI 執行檔路徑"""
        # 1. 檢查預設已知路徑
        for p in self.KNOWN_SEARCH_PATHS:
            if os.path.isfile(p):
                return p

        # 2. 檢查系統 PATH
        in_path = shutil.which("agy") or shutil.which("antigravity")
        if in_path:
            return in_path

        return None

    def is_available(self) -> bool:
        """檢測本機 CLI 是否可正常呼叫與執行"""
        if self._is_available is not None:
            return self._is_available

        with self._lock:
            if not self.cli_path or not os.path.exists(self.cli_path):
                self._is_available = False
                return False

            try:
                cmd = [self.cli_path, "--help"]
                res = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5,
                    check=False
                )
                self._is_available = (res.returncode == 0)
            except Exception:
                self._is_available = False

            return self._is_available

    def generate(
        self,
        prompt: str,
        effort: str = "medium",
        timeout: float = 40.0,
        output_format: str = "text"
    ) -> Optional[str]:
        """
        呼叫 agy 進行單次非互動推論
        :param prompt: 提示詞
        :param effort: 'low', 'medium', 'high' (對應 thinking effort)
        :param timeout: 逾時秒數
        :param output_format: 'text' 或 'json'
        :return: 推論文字結果
        """
        if not self.is_available():
            return None

        # 思考深度參數映射
        effort_flag = "medium"
        if effort in ("max", "high", "deep"):
            effort_flag = "high"
        elif effort in ("low", "fast"):
            effort_flag = "low"

        cmd = [
            self.cli_path,
            "-p", prompt,
            "--effort", effort_flag,
            "--output-format", output_format,
            "--dangerously-skip-permissions"
        ]

        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
                check=False
            )
            if res.returncode == 0 and res.stdout:
                return res.stdout.strip()
            elif res.stderr:
                # 記錄但優雅回退
                err_msg = res.stderr.strip()
                if not err_msg.startswith("Loaded plugins"):
                    print(f"[AntigravityCliEngine] CLI 回應提示: {err_msg[:200]}")
            return res.stdout.strip() if res.stdout else None
        except subprocess.TimeoutExpired:
            print(f"[AntigravityCliEngine] 調用逾時 ({timeout}s)")
            return None
        except Exception as e:
            print(f"[AntigravityCliEngine] 執行異常: {e}")
            return None

    def decompose_user_demand(
        self,
        user_demand: str,
        game_type: GameType,
        capability: AssistCapability,
        thinking_effort: str = "medium"
    ) -> str:
        """
        透過 Antigravity CLI 大腦將玩家需求拆解為戰術指示
        """
        game_name = game_type.value if hasattr(game_type, "value") else str(game_type)
        cap_name = capability.value if hasattr(capability, "value") else str(capability)
        effort_desc = "深度深思 (Deep Thinking)" if thinking_effort == "max" else "敏捷快速思考"

        prompt = (
            f"你是一位頂級遊戲戰術決策大師。\n"
            f"當前遊戲：{game_name}\n"
            f"輔助模式：{cap_name}\n"
            f"思考模式：【{effort_desc}】\n"
            f"玩家提出了具體需求：【{user_demand.strip()}】。\n"
            "請將玩家需求轉化為極度簡潔的即時戰術指示 (Directive)，格式包含：\n"
            "1. 核心目標 (例如：破韌、極限閃避、元素反應、自動打怪)\n"
            "2. 推薦技能序列與優先級 (例如：切 2 號位 -> E -> 普攻)\n"
            "3. 警戒條件 (例如：遇黃光招架、遇紅光閃避)\n"
            "請以繁體中文回答，條點清晰，適合 Jev 反射神經固化與高頻決策直接取用。"
        )

        effort_level = "high" if thinking_effort == "max" else "medium"
        result = self.generate(prompt=prompt, effort=effort_level, timeout=35.0)
        if result:
            return result
        return f"戰術目標：因應需求【{user_demand}】執行最佳輸出與防守。"

    def synthesize_tool_code(
        self,
        tool_spec: str,
        game_type: Optional[GameType] = None,
        context_info: str = ""
    ) -> Optional[str]:
        """
        透過 Antigravity CLI 大腦自主編寫 Python 器官工具程式碼
        """
        game_str = game_type.value if game_type and hasattr(game_type, "value") else str(game_type or "泛用遊戲")
        prompt = (
            "你是一位頂尖的 Python 遊戲周邊工具架構師。\n"
            f"目標遊戲：{game_str}\n"
            f"工具規格需求：\n{tool_spec}\n"
            f"周邊上下文：\n{context_info}\n\n"
            "請為遊戲助理自主生長一個合規的 Python 工具模組代碼。\n"
            "必須滿足以下技術規範：\n"
            "1. 必須定義一個繼承自 BaseOrganTool (或 SensoryOrganTool / ActuatorOrganTool) 的類別\n"
            "2. 必須實作 execute(**kwargs) 方法，回傳 ActionResult 或狀態字典\n"
            "3. 必須實作 get_predicates() 方法，回傳供 Jev 評判之特徵述詞\n"
            "4. 嚴格禁止使用 os.system, shutil.rmtree, eval, exec 或讀取 .env 等破壞性操作\n"
            "5. 代碼必須使用繁體中文註解\n"
            "只輸出純 Python 代碼區塊 (使用 ```python ... ``` 包裹)。"
        )

        code_resp = self.generate(prompt=prompt, effort="high", timeout=45.0)
        return code_resp
