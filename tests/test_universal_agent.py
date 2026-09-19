import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import unittest
import time
from PIL import Image

import game_assistant
from game_assistant.core.config import (
    GameType, AssistCapability, AnalysisMode, MODEL_NAME, DEFAULT_POLL_INTERVAL,
    HOTKEY_EMERGENCY_STOP, HOTKEY_TOGGLE_POLL
)
from game_assistant.engines.jev_engine import (
    Choice, Noul, Score, JevDecisionEngine, JevResponse,
    ChoiceResult, NoulResult, ScoreResult
)
from game_assistant.utils.input_actuator import ScreenActuator
from game_assistant.strategies.base import (
    BaseGameStrategy, TelemetryData, StrategyDecision, ActionResult
)
from game_assistant.strategies.genshin import GenshinStrategy
from game_assistant.strategies.star_rail import StarRailStrategy
from game_assistant.strategies.zzz import ZZZStrategy
from game_assistant.strategies.general import GeneralGameStrategy
from game_assistant.strategies.registry import StrategyRegistry, get_game_strategy
from game_assistant.engines.ai_engine import GeminiAuxiliaryEngine, GeminiAIEngine
from game_assistant.core.agent import UniversalGameAgent


class TestConfig(unittest.TestCase):
    """測試系統配置與版本升級"""

    def test_gemini_model_upgrade(self):
        self.assertEqual(MODEL_NAME, "gemini-3.8-flash", "Gemini 模型必須升級為 gemini-3.8-flash")

    def test_fixed_poll_interval(self):
        self.assertEqual(DEFAULT_POLL_INTERVAL, 0.25, "畫面傳輸與決策輪詢間隔必須為 0.25 秒")

    def test_emergency_stop_hotkey(self):
        self.assertEqual(HOTKEY_EMERGENCY_STOP, "f8", "緊急急停熱鍵必須配置為 F8")

    def test_assist_capability_enum(self):
        self.assertTrue(hasattr(AssistCapability, "GUIDANCE"))
        self.assertTrue(hasattr(AssistCapability, "AUTONOMOUS"))
        self.assertTrue(hasattr(AssistCapability, "DATA_ANALYSIS"))
        self.assertTrue(hasattr(AssistCapability, "VOICE_QA"))


class TestJevEngine(unittest.TestCase):
    """測試 TypeSafe Jev (System 1) 決策引擎"""

    def setUp(self):
        self.engine = JevDecisionEngine()

    def test_primitives_serialization(self):
        c = Choice(instructions="選擇動作", criteria={"atk": None, "def": None})
        n = Noul(instructions="是否危險")
        s = Score(instructions="緊急度", criteria=["低", "中", "高"])

        self.assertEqual(c.to_dict()["type"], "choice")
        self.assertIn("atk", c.to_dict()["criteria"])
        self.assertEqual(n.to_dict()["type"], "noul")
        self.assertEqual(s.to_dict()["type"], "score")

    def test_local_heuristics_evaluation(self):
        state = "[Game]: 原神\n[ALERT]: 敵方攻擊前搖/紅圈警示！危險！\n[Player]: energy_full"
        questions = {
            "tactical_action": Choice(
                instructions="選擇動作",
                criteria={"dash_dodge": None, "burst_q": None, "idle": None}
            ),
            "should_evade": Noul(instructions="是否需要閃避攻擊警示？"),
            "combat_urgency": Score(instructions="緊急評分", criteria=["低", "中", "高"])
        }

        response = self.engine.evaluate(state, questions)
        self.assertIsInstance(response, JevResponse)
        self.assertIn("tactical_action", response.choices)
        self.assertIn("should_evade", response.nouls)
        self.assertIn("combat_urgency", response.scores)

        # 驗證啟發式命中
        self.assertTrue(response.nouls["should_evade"].noul, "在敵方攻擊前搖下，閃避判定應為 True")
        self.assertGreaterEqual(response.scores["combat_urgency"].score, 0.7, "緊急度打分應偏高")


class TestScreenActuator(unittest.TestCase):
    """測試螢幕操作致動器與安全急停"""

    def setUp(self):
        self.actuator = ScreenActuator(action_cooldown=0.01)

    def test_enable_disable(self):
        self.assertFalse(self.actuator.is_enabled)
        self.actuator.enable()
        self.assertTrue(self.actuator.is_enabled)
        self.actuator.disable()
        self.assertFalse(self.actuator.is_enabled)

    def test_emergency_stop(self):
        self.actuator.enable()
        self.assertTrue(self.actuator.is_enabled)
        self.actuator.emergency_stop()
        self.assertFalse(self.actuator.is_enabled, "急停後必須立即禁用操作")

    def test_action_execution_when_disabled(self):
        # 禁用時不發送實體按鍵
        res = self.actuator.press_key("e")
        self.assertFalse(res)

    def test_action_execution_when_enabled(self):
        self.actuator.enable()
        res = self.actuator.press_key("e")
        self.assertTrue(res)
        history = self.actuator.get_recent_history()
        self.assertGreater(len(history), 0)
        self.assertEqual(history[-1]["type"], "KEY_PRESS")


class TestGameStrategies(unittest.TestCase):
    """測試原神、星穹鐵道、絕區零、泛用遊戲策略與動態擴充"""

    def setUp(self):
        self.dummy_img = Image.new("RGB", (320, 240), color="blue")
        self.actuator = ScreenActuator(action_cooldown=0.01)

    def test_genshin_strategy(self):
        strategy = GenshinStrategy()
        self.assertEqual(strategy.game_type, GameType.GENSHIN)

        telemetry = strategy.extract_telemetry(self.dummy_img, visual_context="紅光前搖")
        self.assertTrue(telemetry.danger_detected)

        questions = strategy.build_jev_questions(AssistCapability.GUIDANCE, {})
        self.assertIn("tactical_action", questions)
        self.assertIn("should_evade", questions)

        state_str = strategy.build_jev_state(telemetry, "切換2號位", "幫我打反應", AssistCapability.GUIDANCE)
        self.assertIn("原神", state_str)

        # 模擬 Jev 決策
        jev_resp = JevResponse(
            choices={"tactical_action": ChoiceResult(choice="burst_q", confidence=0.92)},
            nouls={"should_evade": NoulResult(noul=False, confidence=0.9)},
            scores={"combat_urgency": ScoreResult(score=0.8, confidence=0.9)}
        )
        decision = strategy.interpret_decision(jev_resp, telemetry, AssistCapability.GUIDANCE)
        self.assertEqual(decision.primary_action, "burst_q")
        self.assertIn("Q", decision.guidance_text)

        # 測試代替操作 (開啓前)
        res_disabled = strategy.execute_action(decision, self.actuator)
        self.assertFalse(res_disabled.executed)

        # 測試代替操作 (開啓後)
        self.actuator.enable()
        res_enabled = strategy.execute_action(decision, self.actuator)
        self.assertTrue(res_enabled.executed)
        self.assertEqual(res_enabled.target_key_or_button, "q")

    def test_star_rail_strategy(self):
        strategy = StarRailStrategy()
        self.assertEqual(strategy.game_type, GameType.STAR_RAIL)

        telemetry = strategy.extract_telemetry(self.dummy_img, visual_context="SP不足 終結技滿")
        self.assertTrue(telemetry.energy_ready)

        questions = strategy.build_jev_questions(AssistCapability.AUTONOMOUS, {})
        self.assertIn("should_interrupt_ultimate", questions)

        jev_resp = JevResponse(
            choices={"tactical_action": ChoiceResult(choice="ultimate_1", confidence=0.95)},
            nouls={"should_interrupt_ultimate": NoulResult(noul=True, confidence=0.95)},
            scores={"sp_urgency": ScoreResult(score=0.9, confidence=0.9)}
        )
        decision = strategy.interpret_decision(jev_resp, telemetry, AssistCapability.AUTONOMOUS)
        self.assertEqual(decision.primary_action, "ultimate_1")

        self.actuator.enable()
        res = strategy.execute_action(decision, self.actuator)
        self.assertTrue(res.executed)
        self.assertEqual(res.target_key_or_button, "1")

    def test_zzz_strategy(self):
        strategy = ZZZStrategy()
        self.assertEqual(strategy.game_type, GameType.ZZZ)

        # 測試黃光極限招架
        telemetry_yellow = strategy.extract_telemetry(self.dummy_img, visual_context="敵方黃光前搖")
        self.assertTrue(telemetry_yellow.features["yellow_flash"])

        jev_resp = JevResponse(
            choices={"tactical_action": ChoiceResult(choice="parry_assist_space", confidence=0.98)},
            nouls={"yellow_flash": NoulResult(noul=True, confidence=0.98), "red_flash": NoulResult(noul=False)},
            scores={"reaction_urgency": ScoreResult(score=0.99, confidence=0.99)}
        )
        decision = strategy.interpret_decision(jev_resp, telemetry_yellow, AssistCapability.AUTONOMOUS)
        self.assertEqual(decision.primary_action, "parry_assist_space")

        self.actuator.enable()
        res = strategy.execute_action(decision, self.actuator)
        self.assertTrue(res.executed)
        self.assertEqual(res.target_key_or_button, "space")

    def test_general_strategy(self):
        strategy = GeneralGameStrategy()
        self.assertEqual(strategy.game_type, GameType.GENERAL)

        telemetry = strategy.extract_telemetry(self.dummy_img, visual_context="一般戰況")
        questions = strategy.build_jev_questions(AssistCapability.GUIDANCE, {})
        self.assertIn("tactical_action", questions)

        jev_resp = JevResponse(
            choices={"tactical_action": ChoiceResult(choice="use_skill_1", confidence=0.88)},
            nouls={"threat_alert": NoulResult(noul=False)},
            scores={"action_confidence": ScoreResult(score=0.8)}
        )
        decision = strategy.interpret_decision(jev_resp, telemetry, AssistCapability.AUTONOMOUS)
        self.assertEqual(decision.primary_action, "use_skill_1")

        self.actuator.enable()
        res = strategy.execute_action(decision, self.actuator)
        self.assertTrue(res.executed)
        self.assertEqual(res.target_key_or_button, "e")

    def test_strategy_registry_and_future_extension(self):
        """測試 Strategy 工廠與未來擴充能力"""
        # 測試取得已存在的預設策略
        genshin_strat = StrategyRegistry.get(GameType.GENSHIN)
        self.assertIsInstance(genshin_strat, GenshinStrategy)

        # 測試動態擴充一個全新自訂遊戲策略 (例如鳴潮 / 艾爾登法環)
        class CustomNewGameStrategy(BaseGameStrategy):
            @property
            def game_type(self) -> str:
                return "CustomNewGame"

            @property
            def name(self) -> str:
                return "新擴充遊戲 (Custom New Game)"

            def extract_telemetry(self, image, visual_context=""):
                return TelemetryData(timestamp=time.time(), game_type=GameType.GENERAL)

            def build_jev_questions(self, capability, context):
                return {"action": Choice(instructions="自訂遊戲動作", criteria={"jump": None})}

            def build_jev_state(self, telemetry, gemini_directive, user_demand, capability):
                return "[Custom Game State]"

            def interpret_decision(self, jev_response, telemetry, capability):
                return StrategyDecision(
                    primary_action="jump",
                    confidence=1.0,
                    urgency=0.5,
                    should_evade=False,
                    guidance_text="跳躍！",
                    telemetry=telemetry,
                    raw_jev=jev_response
                )

            def execute_action(self, decision, actuator):
                return ActionResult("jump", "space", True)

            def format_analysis(self, history):
                return "Custom Analysis"

        # 註冊新遊戲
        try:
            StrategyRegistry.register("CustomNewGame", CustomNewGameStrategy())
            retrieved = StrategyRegistry.get("CustomNewGame")
            self.assertEqual(retrieved.name, "新擴充遊戲 (Custom New Game)")
        finally:
            StrategyRegistry.initialize_default_strategies()


class TestUniversalGameAgent(unittest.TestCase):
    """測試 UniversalGameAgent 整合管線與 0.25 秒迴圈步驟"""

    def setUp(self):
        self.dummy_img = Image.new("RGB", (320, 240), color="green")
        self.agent = UniversalGameAgent(
            game_type=GameType.GENSHIN,
            capability=AssistCapability.GUIDANCE
        )

    def test_agent_initialization(self):
        self.assertEqual(self.agent.game_type, GameType.GENSHIN)
        self.assertEqual(self.agent.capability, AssistCapability.GUIDANCE)
        self.assertFalse(self.agent.actuator.is_enabled)

    def test_user_demand_and_directive(self):
        self.agent.set_user_demand("幫我打過這隻Boss，注意閃避")
        self.assertEqual(self.agent.current_user_demand, "幫我打過這隻Boss，注意閃避")
        self.assertTrue(len(self.agent.current_gemini_directive) > 0)

    def test_0_25s_step_pipeline(self):
        """測試 0.25 秒固定迴圈之執行步驟"""
        decision = self.agent.step(image=self.dummy_img)
        self.assertIsInstance(decision, StrategyDecision)
        self.assertIsNotNone(decision.primary_action)
        self.assertGreater(decision.confidence, 0.0)
        self.assertIsNotNone(decision.guidance_text)

    def test_autonomous_takeover_step(self):
        """測試代替操作模式下的螢幕自動操作"""
        self.agent.set_capability(AssistCapability.AUTONOMOUS)
        self.assertTrue(self.agent.actuator.is_enabled)

        decision = self.agent.step(image=self.dummy_img)
        self.assertIsNotNone(decision.action_result)
        self.assertTrue(decision.action_result.executed)

    def test_emergency_stop(self):
        """測試 F8 緊急急停中斷"""
        self.agent.set_capability(AssistCapability.AUTONOMOUS)
        self.assertTrue(self.agent.actuator.is_enabled)

        self.agent.emergency_stop()
        self.assertFalse(self.agent.actuator.is_enabled)
        self.assertEqual(self.agent.capability, AssistCapability.GUIDANCE)

    def test_data_analysis_generation(self):
        # 執行幾次 step 產生遙測取樣
        for _ in range(5):
            self.agent.step(image=self.dummy_img)
        report = self.agent.generate_data_analysis_report()
        self.assertIn("實時戰況遙測分析", report)


class TestEdgeCasesAndRobustness(unittest.TestCase):
    """邊界情境與強健性測試"""

    def setUp(self):
        self.agent = UniversalGameAgent()

    def test_empty_state_and_empty_questions(self):
        engine = JevDecisionEngine()
        res_empty = engine.evaluate(state="", questions={})
        self.assertIsInstance(res_empty, JevResponse)
        self.assertEqual(len(res_empty.choices), 0)
        self.assertEqual(len(res_empty.nouls), 0)

    def test_unknown_game_fallback_to_general(self):
        strat = StrategyRegistry.get("NonExistentGame_12345")
        self.assertIsInstance(strat, GeneralGameStrategy)
        self.assertEqual(strat.game_type, GameType.GENERAL)

    def test_empty_user_demand(self):
        self.agent.set_user_demand("")
        self.assertEqual(self.agent.current_user_demand, "")
        self.assertEqual(self.agent.current_gemini_directive, "")

    def test_consecutive_emergency_stops(self):
        self.agent.set_capability(AssistCapability.AUTONOMOUS)
        self.agent.emergency_stop()
        self.assertFalse(self.agent.actuator.is_enabled)
        # 連續多次急停不應報錯
        self.agent.emergency_stop()
        self.agent.emergency_stop()
        self.assertFalse(self.agent.actuator.is_enabled)

    def test_custom_prompt_empty(self):
        img = Image.new("RGB", (100, 100))
        # 離線狀態下應傳回友善提示而非 crash
        res = self.agent.trigger_deep_analysis(img, custom_prompt="")
        self.assertIsInstance(res, str)
        self.assertTrue(len(res) > 0)

    def test_emergency_stop_releases_held_keys(self):
        """測試 F8 急停能確實釋放所有記錄中的按鍵與滑鼠狀態"""
        actuator = ScreenActuator()
        actuator.enable()
        actuator._held_keys.add("shift")
        actuator._held_keys.add("space")
        self.assertEqual(len(actuator._held_keys), 2)

        actuator.emergency_stop()
        self.assertFalse(actuator.is_enabled)
        self.assertEqual(len(actuator._held_keys), 0, "急停後 held_keys 必須被清空")

    def test_screen_actuator_cooldown_enforcement(self):
        """測試致動器在冷卻時間內不會發送重複按鍵"""
        actuator = ScreenActuator(action_cooldown=0.5)
        actuator.enable()
        first_act = actuator.press_key("e")
        self.assertTrue(first_act)
        # 立即再次調用，應受限於 0.5s 冷卻而拒絕
        second_act = actuator.press_key("e")
        self.assertFalse(second_act, "未過冷卻期應拒絕操作")

    def test_data_analysis_questions_for_all_strategies(self):
        """測試所有策略在 DATA_ANALYSIS 模式下皆注入專屬遙測問題"""
        strategies = [
            GenshinStrategy(),
            StarRailStrategy(),
            ZZZStrategy(),
            GeneralGameStrategy()
        ]
        for strat in strategies:
            questions = strat.build_jev_questions(AssistCapability.DATA_ANALYSIS, {})
            self.assertIn("combat_phase", questions, f"{strat.name} 應包含 combat_phase 問題")
            self.assertIn("rotation_efficiency", questions, f"{strat.name} 應包含 rotation_efficiency 問題")
            self.assertIn("needs_optimization", questions, f"{strat.name} 應包含 needs_optimization 問題")

    def test_user_demand_pipeline_with_image(self):
        """測試 Requirement 4: 由 Gemini 處理使用者需求(含影像)後無縫傳遞給 Jev 決策"""
        dummy_img = Image.new("RGB", (320, 240), color="red")
        self.agent.set_user_demand("幫我打過這隻怪物，注意黃光招架", image=dummy_img)
        self.assertIn("招架", self.agent.current_gemini_directive)

        # 緊接著接入 Jev 決策迴圈
        decision = self.agent.step(image=dummy_img)
        self.assertIsNotNone(decision)
        self.assertIsNotNone(decision.guidance_text)

    def test_tts_engine_stop_safe_call(self):
        """測試 TTSEngine.stop() 可安全呼叫且不崩潰"""
        from game_assistant.audio.tts_engine import TTSEngine
        tts = TTSEngine()
        tts.stop()  # 無作用時不應拋錯
        self.assertIsNone(tts._current_engine)

    def test_jev_primitives_dual_compatibility(self):
        """測試 Choice/Noul/Score 同時相容 options 列表與 criteria 字典"""
        c1 = Choice(instructions="動作", criteria={"atk": None, "def": None})
        self.assertIn("atk", c1.options)
        self.assertEqual(c1.to_dict()["type"], "choice")

        c2 = Choice(instructions="動作2", options=["dodge", "parry"])
        self.assertIn("dodge", c2.criteria)
        self.assertEqual(c2.to_dict()["options"], ["dodge", "parry"])

        s = Score(instructions="評分", criteria=["低", "高"])
        self.assertEqual(s.to_dict()["type"], "score")


class TestPackageStructureAndExports(unittest.TestCase):
    """測試重構後 src/ layout 與各 Package 之匯出介面與跨模組引用完整性"""

    def test_package_root_metadata(self):
        self.assertEqual(game_assistant.__version__, "0.2.0")
        self.assertTrue(hasattr(game_assistant, "UniversalGameAgent"))
        self.assertTrue(hasattr(game_assistant, "JevDecisionEngine"))
        self.assertTrue(hasattr(game_assistant, "GeminiAuxiliaryEngine"))
        self.assertTrue(hasattr(game_assistant, "ScreenCapturer"))
        self.assertTrue(hasattr(game_assistant, "ScreenActuator"))
        self.assertTrue(hasattr(game_assistant, "TTSEngine"))
        self.assertTrue(hasattr(game_assistant, "STTEngine"))
        self.assertIn("UniversalGameAgent", game_assistant.__all__)

    def test_cli_console_scripts_entrypoint(self):
        from game_assistant.cli import main as cli_main
        self.assertTrue(callable(cli_main))

    def test_app_controller_exports(self):
        from game_assistant.app import (
            GameAssistantController,
            JevLoopWorker,
            GeminiIntentWorker,
            DeepVisionWorker,
            STTWorker,
            TTSWorker,
        )
        self.assertIsNotNone(GameAssistantController)
        self.assertIsNotNone(JevLoopWorker)
        self.assertIsNotNone(GeminiIntentWorker)
        self.assertIsNotNone(DeepVisionWorker)
        self.assertIsNotNone(STTWorker)
        self.assertIsNotNone(TTSWorker)

    def test_core_package_exports(self):
        from game_assistant import core
        self.assertTrue(hasattr(core, "UniversalGameAgent"))
        self.assertTrue(hasattr(core, "GameType"))
        self.assertTrue(hasattr(core, "AnalysisMode"))
        self.assertTrue(hasattr(core, "AssistCapability"))
        self.assertTrue(hasattr(core, "DEFAULT_POLL_INTERVAL"))
        self.assertTrue(hasattr(core, "POLL_INTERVAL"))
        self.assertTrue(hasattr(core, "DEFAULT_OPACITY"))
        self.assertTrue(hasattr(core, "MAX_IMAGE_SIZE"))
        self.assertTrue(hasattr(core, "HOTKEY_EMERGENCY_STOP"))
        self.assertTrue(hasattr(core, "HOTKEY_TOGGLE_POLL"))
        self.assertTrue(hasattr(core, "HOTKEY_MANUAL_TRIGGER"))
        self.assertTrue(hasattr(core, "HOTKEY_CAPTURE_NOW"))
        self.assertTrue(hasattr(core, "HOTKEY_VOICE_PROMPT"))
        self.assertTrue(hasattr(core, "TTS_ENABLED"))
        self.assertTrue(hasattr(core, "TTS_RATE"))
        self.assertTrue(hasattr(core, "TTS_VOLUME"))
        self.assertTrue(hasattr(core, "STT_LANGUAGE"))
        self.assertTrue(hasattr(core, "STT_TIMEOUT"))
        self.assertTrue(hasattr(core, "STT_PHRASE_TIME_LIMIT"))
        self.assertTrue(hasattr(core, "PROMPTS"))
        # 驗證 __all__ 包含核心成員
        self.assertIn("HOTKEY_MANUAL_TRIGGER", core.__all__)
        self.assertIn("DEFAULT_OPACITY", core.__all__)
        self.assertIn("UniversalGameAgent", core.__all__)

    def test_engines_package_exports(self):
        from game_assistant import engines
        self.assertTrue(hasattr(engines, "Choice"))
        self.assertTrue(hasattr(engines, "Noul"))
        self.assertTrue(hasattr(engines, "Score"))
        self.assertTrue(hasattr(engines, "JevDecisionEngine"))
        self.assertTrue(hasattr(engines, "GeminiAuxiliaryEngine"))
        self.assertTrue(hasattr(engines, "GeminiAIEngine"))
        self.assertTrue(hasattr(engines, "OFFICIAL_SDK_AVAILABLE"))
        self.assertIn("JevDecisionEngine", engines.__all__)
        self.assertIn("GeminiAuxiliaryEngine", engines.__all__)

    def test_audio_package_exports(self):
        from game_assistant import audio
        self.assertTrue(hasattr(audio, "TTSEngine"))
        self.assertTrue(hasattr(audio, "clean_markdown_for_tts"))
        self.assertTrue(hasattr(audio, "STTEngine"))
        self.assertIn("TTSEngine", audio.__all__)
        self.assertIn("clean_markdown_for_tts", audio.__all__)
        self.assertIn("STTEngine", audio.__all__)

    def test_utils_package_exports(self):
        from game_assistant import utils
        self.assertTrue(hasattr(utils, "ScreenCapturer"))
        self.assertTrue(hasattr(utils, "ScreenActuator"))
        self.assertIn("ScreenCapturer", utils.__all__)
        self.assertIn("ScreenActuator", utils.__all__)

    def test_ui_package_exports(self):
        from game_assistant import ui
        self.assertTrue(hasattr(ui, "GameAssistantOverlay"))
        self.assertTrue(hasattr(ui, "HotkeyListener"))
        self.assertIn("GameAssistantOverlay", ui.__all__)
        self.assertIn("HotkeyListener", ui.__all__)

    def test_strategies_package_exports(self):
        from game_assistant import strategies
        self.assertTrue(hasattr(strategies, "BaseGameStrategy"))
        self.assertTrue(hasattr(strategies, "GenshinStrategy"))
        self.assertTrue(hasattr(strategies, "StarRailStrategy"))
        self.assertTrue(hasattr(strategies, "ZZZStrategy"))
        self.assertTrue(hasattr(strategies, "GeneralGameStrategy"))
        self.assertTrue(hasattr(strategies, "StrategyRegistry"))
        self.assertTrue(hasattr(strategies, "get_game_strategy"))

    def test_main_entrypoint_imports(self):
        from main import (
            GameAssistantController,
            JevLoopWorker,
            GeminiIntentWorker,
            DeepVisionWorker,
            STTWorker,
            TTSWorker,
            main as main_entry
        )
        self.assertTrue(callable(main_entry))
        self.assertIsNotNone(GameAssistantController)
        self.assertIsNotNone(STTWorker)
        self.assertIsNotNone(TTSWorker)

    def test_cli_argparse_parser(self):
        from game_assistant.cli import build_parser
        parser = build_parser()
        self.assertIsNotNone(parser)
        # 測試 --version 參數解析
        with self.assertRaises(SystemExit) as cm:
            parser.parse_args(["--version"])
        self.assertEqual(cm.exception.code, 0)

        # 測試 --help 參數解析
        with self.assertRaises(SystemExit) as cm_help:
            parser.parse_args(["--help"])
        self.assertEqual(cm_help.exception.code, 0)

    def test_pyproject_toml_configuration(self):
        toml_path = _PROJECT_ROOT / "pyproject.toml"
        self.assertTrue(toml_path.exists())
        content = toml_path.read_text(encoding="utf-8")
        self.assertIn('name = "game-assistant"', content)
        self.assertIn('game-assistant = "game_assistant.cli:main"', content)
        self.assertIn('where = ["src"]', content)
        self.assertIn("sys_platform == 'win32'", content)


if __name__ == "__main__":
    unittest.main()


