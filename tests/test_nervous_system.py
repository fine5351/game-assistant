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
from PIL import Image

from game_assistant.core.config import (
    GameType, AssistCapability, AnalysisMode,
    ThinkingEffortLevel, REFLEX_CONFIDENCE_THRESHOLD, NOVELTY_SIMILARITY_THRESHOLD
)
from game_assistant.core.nervous_system import (
    NoveltyLevel, ThinkingEffort, ReflexArc, MemoryTrace,
    ReflexMemoryStore, NoveltyDetector, ReflexArcRegistry,
    ConsolidationPipeline, NervousSystemCoordinator
)
from game_assistant.engines.jev_engine import (
    Choice, Noul, Score, JevDecisionEngine, JevResponse,
    ChoiceResult, NoulResult, ScoreResult
)
from game_assistant.engines.ai_engine import GeminiAuxiliaryEngine
from game_assistant.strategies.base import TelemetryData, StrategyDecision
from game_assistant.strategies.genshin import GenshinStrategy
from game_assistant.core.agent import UniversalGameAgent


class TestNervousSystemComponents(unittest.TestCase):
    """測試人類神經系統核心元件：反射弧、記憶庫、新穎度評估器與固化管線"""

    def setUp(self):
        self.temp_mem_path = "data/memory/test_traces.json"
        self.temp_arc_path = "data/memory/test_arcs.json"
        self.memory_store = ReflexMemoryStore(storage_path=self.temp_mem_path)
        self.memory_store.clear()
        self.registry = ReflexArcRegistry(storage_path=self.temp_arc_path)
        self.registry.clear()
        self.novelty_detector = NoveltyDetector()
        self.pipeline = ConsolidationPipeline(min_traces=2)

    def tearDown(self):
        self.memory_store.clear()
        self.registry.clear()
        # 清理測試暫存檔
        for p in [Path(self.temp_mem_path), Path(self.temp_arc_path)]:
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    def test_novelty_and_thinking_effort_classification(self):
        """測試新穎度評估：未見過的新問題為 MAX (深度思考)，相似問題為 MEDIUM (快速思考)"""
        # 1. 未曾遇過的全新問題 -> NOVEL, MAX effort
        novel_demand = "請問艾爾登法環裡面的碎星拉塔恩要怎麼騎馬躲流星"
        novelty, effort, score, matched = self.novelty_detector.evaluate(
            state="[State]: 一般大世界",
            user_demand=novel_demand,
            memory_store=self.memory_store,
            reflex_registry=self.registry
        )
        self.assertEqual(novelty, NoveltyLevel.NOVEL)
        self.assertEqual(effort, ThinkingEffort.MAX)

        # 2. 記錄一筆記憶
        trace = MemoryTrace(
            memory_id="mem_test_1",
            timestamp=time.time(),
            game_type="原神 (Genshin Impact)",
            user_demand="幫我躲避Boss紅光攻擊與紅圈範圍傷害",
            visual_context="敵方前搖紅光",
            state_text="危險！紅光前搖",
            telemetry_features={"danger_detected": True},
            novelty_level="novel",
            thinking_effort="max",
            gemini_directive="立即按下 Shift 閃避無敵幀",
            primary_action="dash_dodge",
            guidance_text="立即閃避",
            suggested_questions={}
        )
        self.memory_store.record_trace(trace)

        # 3. 相似問題再次提出 -> SIMILAR, MEDIUM effort
        similar_demand = "Boss又出現紅光與紅圈攻擊了，快幫我閃避"
        novelty_sim, effort_sim, score_sim, matched_sim = self.novelty_detector.evaluate(
            state="紅光前搖危險！",
            user_demand=similar_demand,
            memory_store=self.memory_store,
            reflex_registry=self.registry
        )
        self.assertEqual(novelty_sim, NoveltyLevel.SIMILAR)
        self.assertEqual(effort_sim, ThinkingEffort.MEDIUM)
        self.assertGreaterEqual(score_sim, NOVELTY_SIMILARITY_THRESHOLD)

    def test_reflex_arc_serialization_and_matching(self):
        """測試 Jev 反射弧規格之匹配與序列化"""
        arc = ReflexArc(
            arc_id="test_arc_1",
            name="測試閃避反射弧",
            game_type="原神",
            trigger_keywords=["紅光", "閃避"],
            trigger_predicates={"danger_detected": True},
            questions={
                "action": Choice(instructions="選擇動作", options=["dash_dodge", "idle"]),
                "danger": Noul(instructions="是否有危險")
            },
            decision_mapping={"dash_dodge": "⚡ 測試閃避反射！"},
            deterministic_output={"primary_action": "dash_dodge", "confidence": 0.99}
        )

        # 測試匹配成功
        telemetry = TelemetryData(
            timestamp=time.time(),
            game_type=GameType.GENSHIN,
            danger_detected=True
        )
        self.assertTrue(arc.matches(state="敵方紅光閃爍", telemetry=telemetry, user_demand="快閃避"))

        # 測試條件不符不匹配 (無危險)
        telemetry_safe = TelemetryData(
            timestamp=time.time(),
            game_type=GameType.GENSHIN,
            danger_detected=False
        )
        self.assertFalse(arc.matches(state="敵方紅光閃爍", telemetry=telemetry_safe, user_demand="快閃避"))

        # 測試序列化
        d = arc.to_dict()
        restored = ReflexArc.from_dict(d)
        self.assertEqual(restored.arc_id, arc.arc_id)
        self.assertEqual(restored.name, arc.name)
        self.assertEqual(restored.trigger_keywords, arc.trigger_keywords)

    def test_consolidation_pipeline_solidification(self):
        """測試記憶固化管線：分析記憶並固化為 Jev input、output、flow"""
        # 1. 寫入兩筆相同情境的大腦思考記憶痕跡
        trace1 = MemoryTrace(
            memory_id="trace_1",
            timestamp=time.time(),
            game_type="原神 (Genshin Impact)",
            user_demand="幫我打水火蒸發反應",
            visual_context="敵人頭頂有水元素",
            state_text="敵人附著水元素，推薦切火系打蒸發",
            telemetry_features={"in_combat": True},
            novelty_level="novel",
            thinking_effort="max",
            gemini_directive="切換 2 號位火系角色，施放戰技觸發蒸發增傷",
            primary_action="switch_2",
            guidance_text="切換 2 號位打蒸發反應",
            suggested_questions={}
        )
        trace2 = MemoryTrace(
            memory_id="trace_2",
            timestamp=time.time(),
            game_type="原神 (Genshin Impact)",
            user_demand="現在切換打蒸發元素反應",
            visual_context="敵人水元素附著",
            state_text="水元素持續，切火角色打反應",
            telemetry_features={"in_combat": True},
            novelty_level="similar",
            thinking_effort="medium",
            gemini_directive="切換 2 號位火系觸發蒸發",
            primary_action="switch_2",
            guidance_text="切換 2 號位打蒸發",
            suggested_questions={}
        )
        self.memory_store.record_trace(trace1)
        self.memory_store.record_trace(trace2)

        unconsolidated = self.memory_store.get_unconsolidated_traces()
        self.assertEqual(len(unconsolidated), 2)

        # 2. 執行固化整理
        new_arcs = self.pipeline.consolidate(
            memory_store=self.memory_store,
            reflex_registry=self.registry,
            force=True
        )

        self.assertEqual(len(new_arcs), 1)
        arc = new_arcs[0]
        self.assertIn("switch_2", arc.arc_id)
        self.assertIn("switch_2", arc.decision_mapping)
        self.assertTrue(len(arc.trigger_keywords) > 0)

        # 3. 驗證記憶已被標記為已固化
        remaining = self.memory_store.get_unconsolidated_traces()
        self.assertEqual(len(remaining), 0)

        # 4. 驗證反射弧已自動註冊至 Registry
        found_arc = self.registry.find_matching_arc(
            state="敵人水元素附著，打蒸發反應",
            user_demand="幫我切換打蒸發"
        )
        self.assertIsNotNone(found_arc)
        self.assertEqual(found_arc.arc_id, arc.arc_id)


class TestNervousSystemCoordinatorAndAgent(unittest.TestCase):
    """測試神經系統協調器、反射優先路徑、大腦升級思考與自我進化"""

    def setUp(self):
        self.temp_mem_path = "data/memory/test_agent_traces.json"
        self.temp_arc_path = "data/memory/test_agent_arcs.json"
        self.memory_store = ReflexMemoryStore(storage_path=self.temp_mem_path)
        self.memory_store.clear()
        self.registry = ReflexArcRegistry(storage_path=self.temp_arc_path)
        self.registry.clear()
        self.jev_engine = JevDecisionEngine()
        self.gemini_engine = GeminiAuxiliaryEngine()
        self.ns = NervousSystemCoordinator(
            jev_engine=self.jev_engine,
            gemini_engine=self.gemini_engine,
            memory_store=self.memory_store,
            reflex_registry=self.registry
        )
        self.agent = UniversalGameAgent(
            game_type=GameType.GENSHIN,
            capability=AssistCapability.GUIDANCE,
            jev_engine=self.jev_engine,
            gemini_engine=self.gemini_engine,
            nervous_system=self.ns
        )

    def tearDown(self):
        self.memory_store.clear()
        self.registry.clear()
        for p in [Path(self.temp_mem_path), Path(self.temp_arc_path)]:
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    def test_instinct_reflex_fast_path(self):
        """測試原生本能反射神經 (危險閃避)：直接以 Jev 毫秒級反射輸出，不進大腦"""
        dummy_img = Image.new("RGB", (320, 240), color="red")
        # 設定為紅光前搖危險遙測
        strategy = self.agent.current_strategy
        telemetry = strategy.extract_telemetry(dummy_img, visual_context="敵方紅光前搖警示！危險！")

        decision, jev_resp, source = self.agent.nervous_system.process_step(
            state="敵方紅光前搖警示！危險！",
            telemetry=telemetry,
            strategy=strategy,
            capability=AssistCapability.GUIDANCE,
            user_demand="快幫我閃避"
        )

        self.assertEqual(source, "reflex", "已知危險特徵應直接由 Jev 反射弧輸出")
        self.assertTrue(jev_resp.is_reflex)
        self.assertEqual(decision.primary_action, "dash_dodge")
        self.assertTrue(decision.should_evade)
        self.assertIn("Jev 反射", decision.guidance_text)

    def test_escalation_to_gemini_brain_when_unhandled(self):
        """測試升級路徑：若 Jev 置信度不足或無匹配反射弧，自動上升至大腦思考並留存記憶"""
        novel_demand = "請問這座神廟的元素方碑要按照什麼順序點亮"
        dummy_img = Image.new("RGB", (320, 240), color="blue")
        telemetry = TelemetryData(timestamp=time.time(), game_type=GameType.GENSHIN)

        decision, jev_resp, source = self.agent.nervous_system.process_step(
            state="解謎神廟方碑機關面前",
            telemetry=telemetry,
            strategy=self.agent.current_strategy,
            capability=AssistCapability.GUIDANCE,
            user_demand=novel_demand,
            force_escalate=True  # 強制升級大腦測試
        )

        self.assertIn("brain_", source)
        self.assertFalse(jev_resp.is_reflex)
        self.assertIn("大腦思考", decision.guidance_text)

        # 驗證每次大腦思考皆留下記憶痕跡
        traces = self.agent.nervous_system.memory_store.get_all_traces()
        self.assertGreaterEqual(len(traces), 1)
        last_trace = traces[-1]
        self.assertEqual(last_trace.user_demand, novel_demand)
        self.assertEqual(last_trace.thinking_effort, "max")  # 新問題深度思考

    def test_self_evolution_closed_loop(self):
        """
        測試完整自我進化閉環 (Self-Evolution Loop):
        1. 遭遇新問題 -> 大腦深度思考 (max effort) -> 留存記憶
        2. 遭遇相似問題 -> 大腦快速思考 (medium effort) -> 留存記憶
        3. 觸發記憶固化管線 (Consolidation Pipeline) -> 提煉出全新 Jev 反射弧 (input, output, flow)
        4. 再次遭遇相同情境 -> 直接透過 Jev 毫秒級反射輸出 (source='reflex')，命中率上升！
        """
        target_demand = "新型敵人出現，請使用二號位雷元素破盾"

        # 步驟 1: 首次遭遇新問題，透過 set_user_demand 調用大腦深度思考
        self.agent.set_user_demand(target_demand)
        self.assertTrue("2 號位" in self.agent.current_gemini_directive or "二號位" in self.agent.current_gemini_directive)

        # 驗證記錄了記憶痕跡
        traces = self.agent.nervous_system.memory_store.get_all_traces()
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0].thinking_effort, "max")

        # 步驟 2: 再次遇到相似問題
        similar_demand = "敵人有水護盾，快切換二號位雷元素打感電破盾"
        self.agent.set_user_demand(similar_demand)
        traces_after_second = self.agent.nervous_system.memory_store.get_all_traces()
        self.assertEqual(len(traces_after_second), 2)
        # 相似問題採用快速思考 (medium effort)
        self.assertEqual(traces_after_second[-1].thinking_effort, "medium")

        # 步驟 3: 執行自我進化記憶固化
        new_arcs = self.agent.consolidate_memories(force=True)
        self.assertGreaterEqual(len(new_arcs), 1)
        solidified_arc = new_arcs[0]

        # 步驟 4: 往後再次遭遇相同 input 時，Jev 直接毫秒級反射出答案！
        dummy_img = Image.new("RGB", (320, 240), color="blue")
        telemetry = TelemetryData(timestamp=time.time(), game_type=GameType.GENSHIN)

        decision, jev_resp, source = self.agent.nervous_system.process_step(
            state="水護盾敵人 二號位雷元素破盾",
            telemetry=telemetry,
            strategy=self.agent.current_strategy,
            capability=AssistCapability.GUIDANCE,
            user_demand=target_demand
        )

        self.assertEqual(source, "reflex", "固化後遭遇相同 input 必須直接由 Jev 反射輸出！")
        self.assertTrue(jev_resp.is_reflex)
        self.assertEqual(jev_resp.matched_arc_id, solidified_arc.arc_id)

        # 步驟 5: 驗證神經統計指標
        stats = self.agent.get_nervous_system_stats()
        self.assertGreater(stats["reflex_hit_count"], 0)
        self.assertGreater(stats["solidified_arcs_count"], 0)
        self.assertIn("突觸建立", stats["current_evolution_stage"])

    def test_gemini_engine_thinking_effort_configurations(self):
        """測試 GeminiAuxiliaryEngine 的思考深度分級參數與結構提煉"""
        engine = GeminiAuxiliaryEngine()

        # 測試 decompose_user_demand 支援 medium 與 max
        res_med = engine.decompose_user_demand(
            user_demand="幫我閃避紅光",
            game_type=GameType.GENSHIN,
            capability=AssistCapability.GUIDANCE,
            thinking_effort="medium"
        )
        self.assertIn("閃避", res_med)

        res_max = engine.decompose_user_demand(
            user_demand="從未見過的奇特機制解謎",
            game_type=GameType.GENSHIN,
            capability=AssistCapability.GUIDANCE,
            thinking_effort="max"
        )
        self.assertTrue(len(res_max) > 0)

        # 測試從指示提煉 Jev 固化 Schema
        schema = engine.extract_reflex_schema_from_directive(
            directive="【戰術指示】：1. 核心目標：極限閃避防禦\n2. 推薦操作：按下 Shift 閃避",
            user_demand="危險紅光閃避"
        )
        self.assertEqual(schema["primary_action"], "dash_dodge")
        self.assertIn("紅光", schema["keywords"])
        self.assertIn("tactical_action", schema["suggested_questions"])
        self.assertIn("urgency", schema["suggested_questions"], "suggested_questions 應包含 Score 緊迫程度評級")

    def test_cross_game_arc_isolation(self):
        """測試跨遊戲反射弧隔離性：星鐵反射弧嚴格不可被原神需求觸發"""
        # 註冊一個星穹鐵道的破盾反射弧
        arc_sr = ReflexArc(
            arc_id="arc_sr_break_shield",
            name="星穹鐵道破盾戰技反射",
            game_type="崩壞：星穹鐵道 (Honkai: Star Rail)",
            trigger_keywords=["破盾"],
            decision_mapping={"skill_e": "⚡ 星鐵戰技破盾！"},
            deterministic_output={"primary_action": "skill_e", "guidance_text": "⚡ 星鐵戰技破盾！"}
        )
        self.registry.register_arc(arc_sr)

        # 1. 透過 find_matching_arc 指定 game_type=GENSHIN，應回傳 None
        matched = self.registry.find_matching_arc(
            state="敵方有護盾，需要破盾",
            user_demand="幫我破盾",
            game_type=GameType.GENSHIN
        )
        self.assertIsNone(matched, "原神情境不應命中星鐵反射弧")

        # 2. 透過 agent.set_user_demand (原神模式)
        self.agent.set_user_demand("幫我破盾")
        self.assertNotIn("星鐵", self.agent.current_gemini_directive)

        # 3. 指定 STAR_RAIL 時，應正確命中
        matched_sr = self.registry.find_matching_arc(
            state="敵方有護盾，需要破盾",
            user_demand="幫我破盾",
            game_type=GameType.STAR_RAIL
        )
        self.assertIsNotNone(matched_sr, "星鐵情境應正確命中星鐵反射弧")
        self.assertEqual(matched_sr.arc_id, "arc_sr_break_shield")

    def test_semantic_subclustering_preserves_distinct_intents(self):
        """測試語意細分聚類：同動作 switch_2 但不同意圖 (水火蒸發 vs 冰雷超導) 應分別固化為獨立反射弧"""
        t1 = MemoryTrace(
            memory_id="trace_evap",
            timestamp=time.time(),
            game_type="原神 (Genshin Impact)",
            user_demand="幫我打水火蒸發反應",
            visual_context="水元素附著",
            state_text="敵方附著水元素，推薦切火系角色",
            telemetry_features={"in_combat": True},
            novelty_level="novel",
            thinking_effort="max",
            gemini_directive="切換 2 號位火系角色打蒸發",
            primary_action="switch_2",
            guidance_text="切換 2 號位打蒸發反應",
            suggested_questions={}
        )
        t2 = MemoryTrace(
            memory_id="trace_superconduct",
            timestamp=time.time(),
            game_type="原神 (Genshin Impact)",
            user_demand="敵人有物抗，快切冰雷超導破防",
            visual_context="冰元素附著",
            state_text="敵方高物抗，推薦打超導降低物抗",
            telemetry_features={"in_combat": True},
            novelty_level="novel",
            thinking_effort="max",
            gemini_directive="切換 2 號位雷系打超導破防",
            primary_action="switch_2",
            guidance_text="切換 2 號位打超導破防",
            suggested_questions={}
        )
        self.memory_store.record_trace(t1)
        self.memory_store.record_trace(t2)

        pipeline = ConsolidationPipeline(min_traces=1)
        new_arcs = pipeline.consolidate(self.memory_store, self.registry, force=True)

        # 驗證兩筆不同意圖各自固化為獨立反射弧，無互相吞噬覆蓋
        self.assertEqual(len(new_arcs), 2, "不同語意意圖應固化為 2 個獨立反射弧")
        arc_evap = next(a for a in new_arcs if "蒸發" in a.name or "蒸發" in a.trigger_keywords)
        arc_super = next(a for a in new_arcs if "超導" in a.name or "超導" in a.trigger_keywords)

        self.assertIn("蒸發", arc_evap.deterministic_output["guidance_text"])
        self.assertIn("超導", arc_super.deterministic_output["guidance_text"])

    def test_tokenizer_and_keyword_boundaries(self):
        """測試中英混雜按鍵分詞與單詞邊界比對，杜絕單字母誤判"""
        detector = NoveltyDetector()
        tokens = detector.tokenize("按Shift閃避，按Q開大招，切換2號位釋放E技能，打Boss")
        self.assertIn("shift", tokens)
        self.assertIn("q", tokens)
        self.assertIn("e", tokens)
        self.assertIn("2", tokens)
        self.assertIn("boss", tokens)
        self.assertIn("閃避", tokens)
        self.assertIn("技能", tokens)

        # 測試反射弧 trigger_keywords 單字母邊界檢查
        arc = ReflexArc(
            arc_id="arc_key_e",
            name="戰技E反射",
            game_type="ALL",
            trigger_keywords=["e"],
            decision_mapping={"skill_e": "按E釋放戰技"}
        )
        # 不應命中僅包含含有 'e' 之單字的句子 (如 'danger_detected')
        self.assertFalse(arc.matches(state="status: danger_detected=true, hp=100%", user_demand=""))
        # 應命中包含單獨 E 鍵之文字
        self.assertTrue(arc.matches(state="按下 E 鍵充能", user_demand=""))

    def test_high_frequency_step_escalation_debounce(self):
        """測試 4 Hz 高頻輪詢時的大腦升級防洪冷卻：避免重複狀態每 0.25 秒狂打 API 與寫記憶庫"""
        telemetry = TelemetryData(timestamp=time.time(), game_type=GameType.GENSHIN)

        initial_traces = len(self.agent.nervous_system.memory_store.get_all_traces())

        # 連續呼叫 4 次 step (模擬 1 秒內高頻輪詢未被反射弧處理的同一未知狀態)
        for _ in range(4):
            self.agent.nervous_system.process_step(
                state="未知神秘機關雕像面前，無任何已知反射弧",
                telemetry=telemetry,
                strategy=self.agent.current_strategy,
                capability=AssistCapability.GUIDANCE,
                user_demand="",  # 輪詢背景 tick
                force_escalate=False
            )

        final_traces = len(self.agent.nervous_system.memory_store.get_all_traces())
        # 在 1.5 秒冷卻防洪下，4 次連續呼叫僅應產生 1 筆記憶痕跡，而非 4 筆狂寫
        self.assertEqual(final_traces - initial_traces, 1, "高頻相同狀態輪詢應受到防洪冷卻保護，只記錄 1 次大腦記憶")

    def test_matched_arc_custom_guidance_preserved(self):
        """測試固化反射弧專屬決策映射 (decision_mapping) 完整保留，不被 strategy 預設字串覆蓋"""
        custom_arc = ReflexArc(
            arc_id="arc_custom_reaction",
            name="自訂水雷感電反射",
            game_type="原神 (Genshin Impact)",
            trigger_keywords=["感電"],
            questions={
                "tactical_action": Choice(instructions="評估動作", options=["switch_2", "idle"])
            },
            decision_mapping={"switch_2": "⚡ 專屬神經反射：立即切換 2 號位雷屬性引爆全場感電！"},
            deterministic_output={"primary_action": "switch_2", "guidance_text": "⚡ 專屬神經反射：立即切換 2 號位雷屬性引爆全場感電！"}
        )
        self.registry.register_arc(custom_arc)

        telemetry = TelemetryData(timestamp=time.time(), game_type=GameType.GENSHIN)
        decision, jev_resp, source = self.agent.nervous_system.process_step(
            state="敵方潮濕，立即打感電",
            telemetry=telemetry,
            strategy=self.agent.current_strategy,
            capability=AssistCapability.GUIDANCE,
            user_demand="打感電"
        )

        self.assertEqual(source, "reflex")
        self.assertEqual(decision.primary_action, "switch_2")
        self.assertIn("引爆全場感電", decision.guidance_text, "反射弧專屬決策映射文字應被完全保留")


if __name__ == "__main__":
    unittest.main()
