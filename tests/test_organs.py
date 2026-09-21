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


if __name__ == "__main__":
    unittest.main()
