"""
測試器官工具自律生長、感官致動與安全審查門禁 (Organ Tools & Dynamic Synthesis)
"""

import unittest
import os
import shutil
from game_assistant.organs.base import OrganType, BaseOrganTool
from game_assistant.organs.sensory import (
    EnemyStanceWatcherEye,
    BossSoundWarningEar,
    WebIntelligenceEar
)
from game_assistant.organs.actuator import (
    DodgeCancelHand,
    ElementalComboHand,
    AutoLootSprintFoot
)
from game_assistant.organs.synthesizer import (
    OrganSynthesizer,
    OrganSafetyGuard,
    OrganSecurityViolation
)
from game_assistant.organs.registry import OrganRegistry


class TestOrganTools(unittest.TestCase):
    """測試器官工具體系與自律生長能力"""

    def setUp(self):
        self.test_storage_dir = "tests/temp_dynamic_organs"
        if os.path.exists(self.test_storage_dir):
            shutil.rmtree(self.test_storage_dir, ignore_errors=True)
        self.synthesizer = OrganSynthesizer(storage_dir=self.test_storage_dir)
        self.registry = OrganRegistry(storage_dir=self.test_storage_dir, synthesizer=self.synthesizer)

    def tearDown(self):
        if os.path.exists(self.test_storage_dir):
            shutil.rmtree(self.test_storage_dir, ignore_errors=True)

    def test_enemy_stance_watcher_eye(self):
        eye = EnemyStanceWatcherEye()
        # 正常狀態
        res = eye.execute(break_gauge=0.5, is_stunned=False)
        self.assertFalse(res["target_stunned"])
        self.assertEqual(res["status"], "normal")

        # 失衡虛弱狀態
        res_stun = eye.execute(break_gauge=1.0, is_stunned=True)
        self.assertTrue(res_stun["target_stunned"])
        self.assertEqual(res_stun["status"], "stunned_vulnerable")

        preds = eye.extract_predicates()
        self.assertTrue(preds["is_target_stunned"])

    def test_boss_sound_warning_ear(self):
        ear = BossSoundWarningEar()
        # 安全狀態
        res_safe = ear.execute(sound_cue="ambient_wind", danger_level="low")
        self.assertFalse(res_safe["boss_ult_incoming"])
        self.assertEqual(res_safe["suggested_action"], "none")

        # 大招警訊
        res_danger = ear.execute(sound_cue="鐘鳴警報大招蓄力", danger_level="high")
        self.assertTrue(res_danger["boss_ult_incoming"])
        self.assertIn("dodge", res_danger["suggested_action"])

    def test_actuator_hands_and_feet_mock(self):
        hand = DodgeCancelHand(actuator=None)
        res_hand = hand.execute(follow_up="attack")
        self.assertEqual(res_hand["action"], "dodge_cancel_macro")
        self.assertEqual(res_hand["steps"], ["dash_cancel", "follow_up_attack"])

        foot = AutoLootSprintFoot(actuator=None)
        res_foot = foot.execute(duration_sec=0.5)
        self.assertEqual(res_foot["action"], "auto_loot_sprint")

    def test_safety_guard_blocks_malicious_code(self):
        # 1. 嘗試匯入 subprocess
        bad_code_1 = """
import subprocess
class HackTool(BaseOrganTool):
    def execute(self): pass
"""
        with self.assertRaises(OrganSecurityViolation):
            OrganSafetyGuard.inspect_code(bad_code_1)

        # 2. 嘗試呼叫 eval
        bad_code_2 = """
class EvalTool(BaseOrganTool):
    def execute(self):
        return eval("1+1")
"""
        with self.assertRaises(OrganSecurityViolation):
            OrganSafetyGuard.inspect_code(bad_code_2)

        # 3. 嘗試呼叫 os.system
        bad_code_3 = """
import os
class SystemTool(BaseOrganTool):
    def execute(self):
        os.system("dir")
"""
        with self.assertRaises(OrganSecurityViolation):
            OrganSafetyGuard.inspect_code(bad_code_3)

    def test_synthesizer_grow_dynamic_organ(self):
        # 測試自律生長出全新工具：釣魚拉竿手 (Fishing Reel Hand)
        tool = self.synthesizer.synthesize_organ(
            requirement="當浮標下沉出現張力警示時，短按拉竿並維持張力在綠色安全區間",
            organ_type=OrganType.ACTUATOR_HAND,
            name="自動釣魚控竿手",
            organ_id="hand_fishing_reel"
        )
        self.assertIsNotNone(tool)
        self.assertEqual(tool.organ_id, "hand_fishing_reel")
        self.assertEqual(tool.organ_type, OrganType.ACTUATOR_HAND)

        # 執行此動態生長出的工具
        result = tool.execute(fish_bite=True, tension=0.7)
        self.assertEqual(result["status"], "dynamic_executed")
        self.assertEqual(result["params_received"]["tension"], 0.7)

        # 檢查持久化檔案
        saved_file = os.path.join(self.test_storage_dir, "hand_fishing_reel.py")
        self.assertTrue(os.path.exists(saved_file))

    def test_organ_registry_lifecycle(self):
        # 檢查內建器官已裝載
        all_organs = self.registry.list_all_organs()
        self.assertGreaterEqual(len(all_organs), 6)

        eyes = self.registry.get_organs_by_type(OrganType.SENSORY_EYE)
        self.assertTrue(len(eyes) >= 1)

        # 測試透過 Registry 自律生長新器官
        new_eye = self.registry.grow_organ(
            requirement="偵測畫面上的納塔燃素結晶礦脈與特產採集點",
            organ_type=OrganType.SENSORY_EYE,
            name="燃素礦脈探測眼",
            organ_id="eye_phlogiston_miner"
        )
        self.assertEqual(new_eye.organ_id, "eye_phlogiston_miner")
        self.assertIsNotNone(self.registry.get_organ("eye_phlogiston_miner"))

        # 彙整 Predicates 測試
        preds = self.registry.collect_all_predicates()
        self.assertIsInstance(preds, dict)
        self.assertIn("is_target_stunned", preds)

        # 摘要狀態測試
        summary = self.registry.get_summary()
        self.assertGreaterEqual(summary["total_count"], 7)
        self.assertGreaterEqual(summary["dynamic_grown_count"], 1)

    def test_action_sequence_extractor(self):
        """測試動作序列抽取器從文字中解析微觀鍵鼠操作"""
        from game_assistant.organs.action_parser import ActionSequenceExtractor, ActionStep
        from game_assistant.core.config import GameType

        # 測試判定接管需求
        self.assertTrue(ActionSequenceExtractor.is_takeover_or_hand_demand("為什麼你不會長出手"))
        self.assertTrue(ActionSequenceExtractor.is_takeover_or_hand_demand("幫我打，執行連招"))
        self.assertFalse(ActionSequenceExtractor.is_takeover_or_hand_demand("今天天氣真好"))

        directive_text = """
1. 核心目標：核爆輸出
2. 推薦輸入序列：
切 3 號位 (希諾寧) ➔ E 施放戰技 ➔ 普攻 2 次
切 4 號位 (茜特菈莉) ➔ E ➔ Q 施放大招
切 1 號位 (瑪薇卡) ➔ Q 元素爆發融化核爆 ➔ 長按 E 進入驅動模式 ➔ 連續普攻
3. 警戒條件：紅光閃避
"""
        steps = ActionSequenceExtractor.extract_sequence(directive_text, game_type=GameType.GENSHIN)
        self.assertGreaterEqual(len(steps), 6)

        # 驗證步驟解析
        targets = [s.target for s in steps]
        self.assertIn("3", targets)
        self.assertIn("e", targets)
        self.assertIn("left", targets)
        self.assertIn("4", targets)
        self.assertIn("q", targets)
        self.assertIn("1", targets)

    def test_dynamic_action_script_hand(self):
        """測試 DynamicActionScriptHand 生成腳本、執行動作與 AST 安全審查"""
        from game_assistant.organs.actuator import DynamicActionScriptHand
        from game_assistant.organs.action_parser import ActionStep
        from game_assistant.utils.input_actuator import ScreenActuator

        actuator = ScreenActuator()
        steps = [
            ActionStep("key", "3", duration=0.01, post_delay=0.01, description="切 3 號位"),
            ActionStep("key", "e", duration=0.01, post_delay=0.01, description="戰技 E"),
            ActionStep("click", "left", duration=0.01, post_delay=0.01, description="普攻"),
            ActionStep("key", "q", duration=0.01, post_delay=0.01, description="大招 Q")
        ]

        hand = DynamicActionScriptHand(
            organ_id="hand_test_macro",
            name="測試連招手",
            steps=steps,
            actuator=actuator,
            requirement="核爆連招"
        )
        res = hand.execute(actuator=actuator)
        self.assertEqual(res["action"], "dynamic_script_takeover")
        self.assertEqual(res["steps_count"], 4)
        self.assertEqual(len(res["executed_steps"]), 4)

        # 驗證生成的代碼可通過 AST 安全審查
        py_code = hand.generate_python_code()
        OrganSafetyGuard.inspect_code(py_code)
        self.assertIn("DynamicHand_", py_code)
        self.assertIn("BaseOrganTool", py_code)

    def test_universal_agent_hand_growth_and_takeover_flow(self):
        """測試 UniversalGameAgent 在收到長手/接管需求時，自動生長手部器官並接管操作"""
        from game_assistant.core.agent import UniversalGameAgent
        from game_assistant.core.config import GameType, AssistCapability

        agent = UniversalGameAgent(game_type=GameType.GENSHIN, capability=AssistCapability.GUIDANCE)
        # 清除反射弧以測試大腦與生長閉環
        agent.nervous_system.reflex_registry.clear()

        # 玩家語音提問：「為什麼你不會長出手」
        demand = "為什麼你不會長出手"
        agent.set_user_demand(demand)

        # 1. 驗證大腦戰術指示不再宣稱「物理終端缺失」，而是包含操作接管回報
        directive = agent.current_gemini_directive
        self.assertNotIn("物理終端（手）缺失", directive)
        self.assertIn("神經操作接管完成", directive)
        self.assertIn("操作手", directive)

        # 2. 驗證器官註冊中心已成功動態生長出手部器官
        hand_organs = [o for o in agent.organ_registry.list_all_organs() if o.organ_type == OrganType.ACTUATOR_HAND and not o.is_built_in]
        self.assertGreaterEqual(len(hand_organs), 1)
        grown_hand = hand_organs[-1]
        self.assertIn("操作手", grown_hand.name)
        self.assertGreaterEqual(grown_hand.execution_count, 1)

        # 3. 驗證進化報告反映新生長之器官
        report = agent.get_evolution_report()
        self.assertGreaterEqual(report["organs"]["dynamic_grown_count"], 1)


if __name__ == "__main__":
    unittest.main()
