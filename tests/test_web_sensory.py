"""
測試自律網路情報採集器 (WebSensoryGatherer)
"""

import unittest
import os
import shutil
from game_assistant.core.config import GameType
from game_assistant.sensory.web_sensory import WebSensoryGatherer


class TestWebSensoryGatherer(unittest.TestCase):
    """測試 WebSensoryGatherer 的情報採集、快取與 Jev 特徵化摘要"""

    def setUp(self):
        self.test_cache_dir = "tests/temp_knowledge_cache"
        if os.path.exists(self.test_cache_dir):
            shutil.rmtree(self.test_cache_dir, ignore_errors=True)
        self.gatherer = WebSensoryGatherer(cache_dir=self.test_cache_dir, enable_network=False)

    def tearDown(self):
        if os.path.exists(self.test_cache_dir):
            shutil.rmtree(self.test_cache_dir, ignore_errors=True)

    def test_search_game_knowledge_hit(self):
        results = self.gatherer.search_game_knowledge("那維萊特 逐影獵人", GameType.GENSHIN)
        self.assertTrue(len(results) > 0)
        top = results[0]
        self.assertIn("那維萊特", top["title"])
        self.assertTrue(top["score"] > 0)

    def test_fetch_character_build_genshin(self):
        guide = self.gatherer.fetch_character_build_guide("那維萊特", GameType.GENSHIN)
        self.assertEqual(guide["character"], "那維萊特")
        self.assertIn("逐影獵人 4件套", guide["best_equipment"])
        self.assertIn("sand", guide["stat_priority"])
        self.assertIn("芙寧娜", str(guide["team_recommendations"]))

    def test_fetch_character_build_star_rail(self):
        guide = self.gatherer.fetch_character_build_guide("黃泉", GameType.STAR_RAIL)
        self.assertEqual(guide["character"], "黃泉")
        self.assertIn("死水深潛的先驅 4件套", guide["best_equipment"])
        self.assertIn("終結技", guide["skill_priority"][0])

    def test_fetch_character_build_zzz(self):
        guide = self.gatherer.fetch_character_build_guide("艾蓮·喬", GameType.ZZZ)
        self.assertEqual(guide["character"], "艾蓮·喬")
        self.assertIn("極地重金屬 4件套", guide["best_equipment"])

    def test_fetch_exploration_targets(self):
        explore = self.gatherer.fetch_exploration_targets("納塔 燃素", GameType.GENSHIN)
        self.assertIn("納塔", explore["target"])
        self.assertTrue(len(explore["routes"]) > 0)
        self.assertIn("燃素", explore["mechanism"])

    def test_fetch_boss_mechanics(self):
        boss_data = self.gatherer.fetch_boss_mechanics("吞星之鯨", GameType.GENSHIN)
        self.assertEqual(boss_data["boss"], "吞星之鯨")
        self.assertTrue(len(boss_data["dangerous_skills"]) > 0)
        self.assertTrue(len(boss_data["warning_cues"]) > 0)

    def test_cache_persistence_and_hit(self):
        # 第一次查詢產生快取
        data1 = self.gatherer.fetch_character_build_guide("芙寧娜", GameType.GENSHIN)
        # 檢查磁碟檔案是否存在
        cache_file = self.gatherer._get_cache_path(f"build_{GameType.GENSHIN.name}_芙寧娜")
        self.assertTrue(os.path.exists(cache_file))

        # 第二次讀取應命中快取
        data2 = self.gatherer.fetch_character_build_guide("芙寧娜", GameType.GENSHIN)
        self.assertEqual(data1["character"], data2["character"])

    def test_summarize_for_jev(self):
        guide = self.gatherer.fetch_character_build_guide("那維萊特", GameType.GENSHIN)
        summary_predicate = self.gatherer.summarize_for_jev(guide)
        self.assertIn("角色:那維萊特", summary_predicate)
        self.assertIn("推薦裝備:", summary_predicate)


if __name__ == "__main__":
    unittest.main()
