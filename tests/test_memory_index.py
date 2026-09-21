import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import unittest

from game_assistant.core.config import GameType, AssistCapability
from game_assistant.core.memory_index import (
    MemoryDomain, MemoryClusterNode, DomainNode,
    HierarchicalMemoryIndex, JevMemoryRouter
)
from game_assistant.core.nervous_system import (
    MemoryTrace, ReflexMemoryStore, NoveltyDetector, ReflexArcRegistry,
    NervousSystemCoordinator
)
from game_assistant.engines.jev_engine import JevDecisionEngine
from game_assistant.strategies.base import TelemetryData


class TestHierarchicalMemoryRouting(unittest.TestCase):
    """測試 Jev 驅動的多層索引記憶檢索與路由系統"""

    def setUp(self):
        self.temp_index_path = "data/memory/test_hierarchical_index.json"
        self.temp_mem_path = "data/memory/test_mem_store.json"
        self.index = HierarchicalMemoryIndex(storage_path=self.temp_index_path)
        self.index.clear()
        self.jev_engine = JevDecisionEngine()
        self.router = JevMemoryRouter(index=self.index, jev_engine=self.jev_engine)
        self.mem_store = ReflexMemoryStore(storage_path=self.temp_mem_path, router=self.router)
        self.mem_store.clear()

    def tearDown(self):
        self.index.clear()
        self.mem_store.clear()
        for p in [Path(self.temp_index_path), Path(self.temp_mem_path)]:
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    def test_default_hierarchy_initialization(self):
        """驗證預設領域與機制聚類桶已完整建立"""
        self.assertIn(MemoryDomain.GENSHIN_COMBAT, self.index.domains)
        self.assertIn(MemoryDomain.STAR_RAIL_COMBAT, self.index.domains)
        self.assertIn(MemoryDomain.ZZZ_COMBAT, self.index.domains)
        self.assertIn(MemoryDomain.EQUIPMENT_BUILD, self.index.domains)

        genshin_domain = self.index.get_domain(MemoryDomain.GENSHIN_COMBAT)
        self.assertIsNotNone(genshin_domain)
        self.assertIn("elemental_reaction", genshin_domain.clusters)
        self.assertIn("burst_ult", genshin_domain.clusters)
        self.assertIn("evade_parry", genshin_domain.clusters)

    def test_level_1_domain_routing(self):
        """驗證 Level 1 領域路由器能夠根據上下文、遊戲類型與關鍵字精準導航"""
        # 1. 遊戲類型快速通道
        dom1 = self.router.route_domain("隨意文字", game_type=GameType.GENSHIN, capability=AssistCapability.GUIDANCE)
        self.assertEqual(dom1, MemoryDomain.GENSHIN_COMBAT)

        dom2 = self.router.route_domain("隨意文字", game_type=GameType.GENSHIN, capability=AssistCapability.EXPLORATION)
        self.assertEqual(dom2, MemoryDomain.GENSHIN_EXPLORE)

        dom3 = self.router.route_domain("隨意文字", game_type=GameType.STAR_RAIL, capability=AssistCapability.GUIDANCE)
        self.assertEqual(dom3, MemoryDomain.STAR_RAIL_COMBAT)

        dom4 = self.router.route_domain("隨意文字", game_type=GameType.ZZZ, capability=AssistCapability.GUIDANCE)
        self.assertEqual(dom4, MemoryDomain.ZZZ_COMBAT)

        # 2. 文本關鍵字啟發判定
        dom5 = self.router.route_domain("幫我看看這件聖遺物詞條好不好，要不要強化停損")
        self.assertEqual(dom5, MemoryDomain.EQUIPMENT_BUILD)

        dom6 = self.router.route_domain("請把這句英文對話翻譯成繁體中文")
        self.assertEqual(dom6, MemoryDomain.TRANSLATION)

    def test_level_2_cluster_routing(self):
        """驗證 Level 2 意圖機制路由器能精準路由至正確聚類桶"""
        # 原神戰鬥領域下的意圖路由
        cls1 = self.router.route_cluster("幫我切換角色打出水火蒸發反應", domain_id=MemoryDomain.GENSHIN_COMBAT)
        self.assertEqual(cls1, "elemental_reaction")

        cls2 = self.router.route_cluster("雷神滿能量了，準備開大招元素爆發！", domain_id=MemoryDomain.GENSHIN_COMBAT)
        self.assertEqual(cls2, "burst_ult")

        cls3 = self.router.route_cluster("看到紅光提示，趕快按 Shift 極限閃避", domain_id=MemoryDomain.GENSHIN_COMBAT)
        self.assertEqual(cls3, "evade_parry")

        # 絕區零戰鬥領域下的意圖路由
        cls4 = self.router.route_cluster("敵人黃光一閃，按空格極限招架支援", domain_id=MemoryDomain.ZZZ_COMBAT)
        self.assertEqual(cls4, "yellow_flash_parry")

        # 星鐵領域下的意圖路由
        cls5 = self.router.route_cluster("敵人弱點已暴露，集中火力削韌破韌", domain_id=MemoryDomain.STAR_RAIL_COMBAT)
        self.assertEqual(cls5, "weakness_break")

    def test_automatic_indexing_and_leaf_retrieval(self):
        """驗證新記憶寫入時自動分層索引，且葉節點能精準召回，消除大海撈針"""
        # 1. 寫入多筆不同領域與意圖的記憶
        t1 = MemoryTrace(
            memory_id="mem_genshin_evade_1",
            timestamp=time.time(),
            game_type="原神",
            user_demand="Boss紅光前搖，按Shift閃避",
            visual_context="原神狂風之核",
            state_text="敵方紅光閃避",
            primary_action="dash_dodge",
            guidance_text="立即閃避"
        )
        self.mem_store.record_trace(t1, game_type=GameType.GENSHIN, capability=AssistCapability.GUIDANCE)

        t2 = MemoryTrace(
            memory_id="mem_hsr_break_1",
            timestamp=time.time(),
            game_type="崩壞：星穹鐵道",
            user_demand="敵方雷弱點，集中削韌破韌",
            visual_context="星鐵可可利亞",
            state_text="雷弱點破韌",
            primary_action="skill_e",
            guidance_text="戰技削韌"
        )
        self.mem_store.record_trace(t2, game_type=GameType.STAR_RAIL, capability=AssistCapability.GUIDANCE)

        t3 = MemoryTrace(
            memory_id="mem_gear_cv_1",
            timestamp=time.time(),
            game_type="原神",
            user_demand="分析這件雙暴聖遺物詞條，CV評分",
            visual_context="聖遺物背包",
            state_text="雙暴詞條精算",
            primary_action="lock_and_keep",
            guidance_text="鎖定保留"
        )
        self.mem_store.record_trace(t3, game_type=GameType.GENSHIN, capability=AssistCapability.EQUIPMENT_BUILD)

        # 2. 驗證分層索引桶中的痕跡 ID 登記
        genshin_evade_traces = self.index.get_cluster_traces(MemoryDomain.GENSHIN_COMBAT, "evade_parry")
        self.assertIn("mem_genshin_evade_1", genshin_evade_traces)

        hsr_break_traces = self.index.get_cluster_traces(MemoryDomain.STAR_RAIL_COMBAT, "weakness_break")
        self.assertIn("mem_hsr_break_1", hsr_break_traces)

        gear_traces = self.index.get_cluster_traces(MemoryDomain.EQUIPMENT_BUILD, "substat_cv_rating")
        self.assertIn("mem_gear_cv_1", gear_traces)

        # 3. 測試 Level 3 葉節點精準檢索 (只在目標聚類桶搜尋，不遍歷全庫)
        detector = NoveltyDetector()
        query_text = "Boss有紅光危險，準備閃避無敵幀"
        query_tokens = detector.tokenize(query_text)

        domain_id, cluster_id = self.router.route(query_text, game_type=GameType.GENSHIN, capability=AssistCapability.GUIDANCE)
        self.assertEqual(domain_id, MemoryDomain.GENSHIN_COMBAT)
        self.assertEqual(cluster_id, "evade_parry")

        leaf_results = self.router.query_leaf_traces(
            input_tokens=query_tokens,
            domain_id=domain_id,
            cluster_id=cluster_id,
            memory_store=self.mem_store,
            compute_similarity_fn=detector.compute_similarity,
            tokenize_fn=detector.tokenize,
            top_k=2
        )

        self.assertGreaterEqual(len(leaf_results), 1)
        matched_trace, sim = leaf_results[0]
        self.assertEqual(matched_trace.memory_id, "mem_genshin_evade_1")
        self.assertGreater(sim, 0.2)


    def test_novelty_detector_with_hierarchical_router(self):
        """驗證 NoveltyDetector 在接入 Jev 記憶路由器後能精準辨識相似問題"""
        detector = NoveltyDetector()
        registry = ReflexArcRegistry()

        # 寫入歷史記憶
        trace = MemoryTrace(
            memory_id="mem_zzz_parry",
            timestamp=time.time(),
            game_type="絕區零",
            user_demand="黃光出現按空格招架支援",
            visual_context="絕區零戰鬥",
            state_text="黃光空格招架",
            primary_action="parry_assist_space",
            guidance_text="極限招架"
        )
        self.mem_store.record_trace(trace, game_type=GameType.ZZZ, capability=AssistCapability.GUIDANCE)

        # 進行評估
        novelty, effort, score, matched_id = detector.evaluate(
            state="敵方出現黃光提示",
            user_demand="按空格進行極限招架",
            memory_store=self.mem_store,
            reflex_registry=registry,
            memory_router=self.router,
            game_type=GameType.ZZZ,
            capability=AssistCapability.GUIDANCE
        )

        self.assertEqual(novelty.value, "similar")
        self.assertEqual(effort.value, "medium")
        self.assertIn("mem_zzz_parry", matched_id)


if __name__ == "__main__":
    unittest.main()
