import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import unittest

from game_assistant.core.config import GameType, AssistCapability
from game_assistant.engines.antigravity_engine import AntigravityCliEngine
from game_assistant.engines.ai_engine import GeminiAuxiliaryEngine, BrainProviderType


class TestAntigravityBrainEngine(unittest.TestCase):
    """測試 Antigravity CLI 大腦驅動引擎與 Provider 自動探測"""

    def test_cli_engine_detection(self):
        """驗證 Antigravity CLI 探測器能正確識別本機可執行檔"""
        engine = AntigravityCliEngine()
        # 若本機環境存在 agy，is_available() 應為 True，否則為 False，但不應拋出未捕獲例外
        is_avail = engine.is_available()
        self.assertIsInstance(is_avail, bool)

    def test_provider_auto_selection(self):
        """驗證 AUTO 模式下優先選擇 Antigravity CLI (免金鑰推論)"""
        mock_cli = MagicMock(spec=AntigravityCliEngine)
        mock_cli.is_available.return_value = True

        aux_engine = GeminiAuxiliaryEngine(
            api_key="",
            provider=BrainProviderType.AUTO,
            antigravity_cli=mock_cli
        )
        self.assertEqual(aux_engine.active_provider, BrainProviderType.ANTIGRAVITY_CLI)

    def test_provider_fallback_to_heuristic(self):
        """驗證當 CLI 不可用且無金鑰時，自動降級至本地離線啟發式"""
        mock_cli = MagicMock(spec=AntigravityCliEngine)
        mock_cli.is_available.return_value = False

        aux_engine = GeminiAuxiliaryEngine(
            api_key="",
            provider=BrainProviderType.AUTO,
            antigravity_cli=mock_cli
        )
        self.assertEqual(aux_engine.active_provider, BrainProviderType.OFFLINE_HEURISTIC)

        # 測試離線分解依然穩定輸出繁體中文戰術
        directive = aux_engine.decompose_user_demand(
            user_demand="看到紅光請幫我閃避",
            game_type=GameType.GENSHIN,
            capability=AssistCapability.GUIDANCE
        )
        self.assertIn("閃避", directive)

    def test_decompose_via_antigravity_cli(self):
        """驗證透過 Antigravity CLI 大腦成功拆解使用者需求"""
        mock_cli = MagicMock(spec=AntigravityCliEngine)
        mock_cli.is_available.return_value = True
        mock_cli.decompose_user_demand.return_value = "戰術目標：因應紅光危險執行極限閃避無敵幀。"

        aux_engine = GeminiAuxiliaryEngine(
            api_key="",
            provider=BrainProviderType.ANTIGRAVITY_CLI,
            antigravity_cli=mock_cli
        )
        directive = aux_engine.decompose_user_demand(
            user_demand="敵方紅光前搖，立即閃避",
            game_type=GameType.GENSHIN,
            capability=AssistCapability.GUIDANCE,
            thinking_effort="medium"
        )
        mock_cli.decompose_user_demand.assert_called_once()
        self.assertIn("極限閃避", directive)

    def test_synthesize_tool_code_interface(self):
        """驗證工具代碼合成介面"""
        mock_cli = MagicMock(spec=AntigravityCliEngine)
        mock_cli.is_available.return_value = True
        mock_cli.synthesize_tool_code.return_value = "```python\nclass CustomTool:\n    pass\n```"

        aux_engine = GeminiAuxiliaryEngine(
            provider=BrainProviderType.ANTIGRAVITY_CLI,
            antigravity_cli=mock_cli
        )
        code = aux_engine.synthesize_tool_code(
            tool_spec="建立一個監測敵人失衡值的感官工具",
            game_type=GameType.ZZZ
        )
        self.assertIsNotNone(code)
        self.assertIn("CustomTool", code)


if __name__ == "__main__":
    unittest.main()
