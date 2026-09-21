if __name__ == "__main__" and not __package__:
    import sys
    from pathlib import Path
    _src = str(Path(__file__).resolve().parents[2])
    if _src not in sys.path:
        sys.path.insert(0, _src)

import time
from typing import Optional, Dict, Any, List
from PIL import Image

from game_assistant.core.config import (
    GameType, AssistCapability, AnalysisMode, DEFAULT_POLL_INTERVAL
)
from game_assistant.utils.screen_capture import ScreenCapturer
from game_assistant.engines.jev_engine import JevDecisionEngine, JevResponse
from game_assistant.engines.ai_engine import GeminiAuxiliaryEngine
from game_assistant.utils.input_actuator import ScreenActuator
from game_assistant.strategies.base import (
    BaseGameStrategy, TelemetryData, StrategyDecision, ActionResult
)
from game_assistant.strategies.registry import StrategyRegistry, get_game_strategy
from game_assistant.core.nervous_system import (
    NervousSystemCoordinator, ReflexArc, MemoryTrace, NoveltyLevel, ThinkingEffort
)
from game_assistant.sensory.web_sensory import WebSensoryGatherer
from game_assistant.organs.base import OrganType, BaseOrganTool
from game_assistant.organs.registry import OrganRegistry


class UniversalGameAgent:
    """
    通用遊戲 Agent 核心架構 (Universal Game Agent)
    以人類神經系統為藍本的自我進化綜合輔助架構：
    - Jev 為反射神經 (Reflex / System 1)：毫秒級快反應，負責已知模式與固化反射弧的直接輸出。
    - Gemini / Antigravity CLI 為大腦 (Brain / System 2)：
      - 簡單相似問題: 快速思考 (effort: medium)
      - 從未遇過的新問題: 深度慢思考 (effort: max / Deep Thinking)
    - 升級路徑 (Escalation Path)：Jev 無法得出確定結果或置信度不足時，自動上升大腦思考。
    - 記憶與固化系統 (Memory & Consolidation)：多層樹狀記憶索引與 Jev 逐層路由，定期提煉固化為 Jev input、output、flow。
    - 自律感官與器官生長 (Sensory Ears/Eyes & Dynamic Organs)：主動聯網查詢百科攻略，自主編寫程式碼生長出眼睛耳朵與手腳。
    - 自我進化 (Self-Evolution)：固化後相同情境直接由 Jev 反射輸出，達成神經系統般的肌肉記憶。
    - Strategy Pattern：支援《原神》、《星穹鐵道》、《絕區零》、《泛用遊戲》及未來任意新遊戲之無縫擴充。
    - 全方位輔助能力：操作指導 (Guidance)、代替操作 (Screen Actuation)、即時資料分析 (Telemetry Stats)。
    """

    def __init__(
        self,
        game_type: GameType = GameType.GENSHIN,
        capability: AssistCapability = AssistCapability.GUIDANCE,
        jev_engine: Optional[JevDecisionEngine] = None,
        gemini_engine: Optional[GeminiAuxiliaryEngine] = None,
        actuator: Optional[ScreenActuator] = None,
        nervous_system: Optional[NervousSystemCoordinator] = None,
        web_sensory: Optional[WebSensoryGatherer] = None,
        organ_registry: Optional[OrganRegistry] = None
    ):
        self.game_type = game_type
        self.capability = capability
        self.jev_engine = jev_engine or JevDecisionEngine()
        self.gemini_engine = gemini_engine or GeminiAuxiliaryEngine()
        self.actuator = actuator or ScreenActuator()
        self.nervous_system = nervous_system or NervousSystemCoordinator(
            jev_engine=self.jev_engine,
            gemini_engine=self.gemini_engine
        )
        self.web_sensory = web_sensory or WebSensoryGatherer()
        self.organ_registry = organ_registry or OrganRegistry(
            actuator=self.actuator,
            gatherer=self.web_sensory
        )

        self.current_user_demand = ""
        self.current_gemini_directive = ""
        self.telemetry_history: List[TelemetryData] = []
        self._max_history = 120  # 保留 30 秒 (每秒 4 幀) 的歷史遙測

    @property
    def current_strategy(self) -> BaseGameStrategy:
        return StrategyRegistry.get(self.game_type)

    def set_game_type(self, game_type: GameType):
        self.game_type = game_type

    def set_capability(self, capability: AssistCapability):
        self.capability = capability
        if capability == AssistCapability.AUTONOMOUS:
            self.actuator.enable()
        else:
            self.actuator.disable()

    def set_user_demand(self, demand: str, image: Optional[Image.Image] = None):
        """
        設定玩家需求：
        優先比對是否已存在固化反射弧；若無或需大腦拆解，評估新穎度分級思考
        (相似問題 medium 快速思考，新問題 max 深度思考)，並留下 Jev 固化所需記憶痕跡。
        """
        self.current_user_demand = demand
        if demand and demand.strip():
            # 1. 優先檢查是否已命中固化反射弧 (依據當前遊戲模式過濾)
            matched_arc = self.nervous_system.reflex_registry.find_matching_arc(
                state=f"[Demand]: {demand}",
                user_demand=demand,
                game_type=self.game_type
            )
            if matched_arc and matched_arc.deterministic_output:
                # ⚡ 命中已固化反射神經，毫秒級直接反射戰術指示
                self.current_gemini_directive = matched_arc.deterministic_output.get(
                    "guidance_text",
                    f"⚡ Jev 固化反射：針對【{demand}】執行【{matched_arc.name}】。"
                )
                return

            # 2. 評估問題新穎度與思考深度
            novelty, effort, sim_score, matched_ref = self.nervous_system.novelty_detector.evaluate(
                state=f"需求: {demand}",
                user_demand=demand,
                memory_store=self.nervous_system.memory_store,
                reflex_registry=self.nervous_system.reflex_registry
            )

            # 3. Gemini 大腦思考 (依據 effort 動態配置)
            directive = self.gemini_engine.decompose_user_demand(
                user_demand=demand,
                game_type=self.game_type,
                capability=self.capability,
                image=image,
                thinking_effort=effort.value
            )
            self.current_gemini_directive = directive

            # 4. 留下神經突觸記憶痕跡 (供後續定期固化管線提煉)
            schema = self.gemini_engine.extract_reflex_schema_from_directive(
                directive=directive,
                user_demand=demand,
                game_type=self.game_type
            )
            mem_id = f"mem_{int(time.time() * 1000)}"
            trace = MemoryTrace(
                memory_id=mem_id,
                timestamp=time.time(),
                game_type=self.game_type.value if hasattr(self.game_type, "value") else str(self.game_type),
                user_demand=demand,
                visual_context=directive[:100],
                state_text=f"需求: {demand}",
                telemetry_features={},
                novelty_level=novelty.value,
                thinking_effort=effort.value,
                gemini_directive=directive,
                primary_action=schema.get("primary_action", "idle"),
                guidance_text=schema.get("guidance_text", directive[:80]),
                suggested_questions=schema.get("suggested_questions", {})
            )
            self.nervous_system.memory_store.record_trace(trace)
        else:
            self.current_gemini_directive = ""

    def emergency_stop(self):
        """緊急安全熔斷開關 (F8)"""
        self.actuator.emergency_stop()
        self.set_capability(AssistCapability.GUIDANCE)

    def step(self, image: Optional[Image.Image] = None) -> StrategyDecision:
        """
        0.25 秒固定高頻決策主迴圈核心步驟 (Loop Step, 4 Hz)
        神經系統雙向流轉：
        1. 畫面快照
        2. 遙測抽取
        3. 建構 Jev Schema 與 State
        4. NervousSystemCoordinator 協同決策：
           - Jev (System 1) 反射神經優先評估，置信度達標立即毫秒級輸出
           - 置信度不足或無對應反射弧時，自動上升至 Gemini (System 2) 大腦思考
           - 每次大腦思考皆沉澱記憶痕跡，為自我進化累積神經突觸
        5. 代替操作螢幕執行 (若為 AUTONOMOUS 模式)
        :return: StrategyDecision
        """
        start_step = time.perf_counter()

        # 1. 畫面快照
        if image is None:
            image, _ = ScreenCapturer.capture(monitor_index=1)

        strategy = self.current_strategy

        # 2. 遙測抽取
        telemetry = strategy.extract_telemetry(
            image=image,
            visual_context=self.current_gemini_directive
        )
        self.telemetry_history.append(telemetry)
        if len(self.telemetry_history) > self._max_history:
            self.telemetry_history.pop(0)

        # 3. 建構 Jev Schema 與 State
        questions = strategy.build_jev_questions(
            capability=self.capability,
            context={"directive": self.current_gemini_directive}
        )
        state_str = strategy.build_jev_state(
            telemetry=telemetry,
            gemini_directive=self.current_gemini_directive,
            user_demand=self.current_user_demand,
            capability=self.capability
        )

        # 4. 神經系統決策：Jev 反射優先，未果時上升 Gemini 大腦思考並留存記憶
        decision, jev_response, source_label = self.nervous_system.process_step(
            state=state_str,
            telemetry=telemetry,
            strategy=strategy,
            capability=self.capability,
            questions=questions,
            user_demand=self.current_user_demand,
            game_type=self.game_type
        )

        # 5. 代替操作螢幕執行 (若為 AUTONOMOUS 模式)
        if self.capability == AssistCapability.AUTONOMOUS:
            action_result = strategy.execute_action(decision, self.actuator)
            decision.action_result = action_result

        return decision

    def consolidate_memories(self, force: bool = False) -> List[ReflexArc]:
        """
        手動或定期觸發記憶固化整理管線
        分析累積的大腦記憶，提煉穩定模式並固化為 Jev input、output、flow
        固化後相同 input 即可直接由 Jev 反射出答案！
        :param force: 是否強制固化 (未滿閾值亦執行)
        :return: 本次新固化之反射弧列表
        """
        return self.nervous_system.consolidate(force=force)

    def get_nervous_system_stats(self) -> Dict[str, Any]:
        """獲取神經系統運作統計（反射命中率、大腦思考次數、固化反射弧數、進化階段）"""
        return self.nervous_system.get_stats()

    def generate_data_analysis_report(self) -> str:
        """產生實時資料分析報告"""
        return self.current_strategy.format_analysis(self.telemetry_history)

    def trigger_deep_analysis(self, image: Image.Image, custom_prompt: Optional[str] = None) -> str:
        """觸發深度多模態視覺分析 (Gemini 3.8 Flash 快照分析)"""
        # 將當前模式映射到 AnalysisMode
        mode = AnalysisMode.COMBAT
        if self.capability == AssistCapability.DATA_ANALYSIS:
            mode = AnalysisMode.BUILD
        elif self.capability == AssistCapability.VOICE_QA:
            mode = AnalysisMode.VOICE_QA
        elif self.capability == AssistCapability.TRANSLATION:
            mode = AnalysisMode.TRANSLATION
        elif self.capability == AssistCapability.EQUIPMENT_BUILD:
            mode = AnalysisMode.EQUIPMENT_ENHANCE
        elif self.capability == AssistCapability.EXPLORATION:
            mode = AnalysisMode.EXPLORATION_MAP

        return self.gemini_engine.analyze_screen(
            image=image,
            game_type=self.game_type,
            mode=mode,
            custom_prompt=custom_prompt or self.current_user_demand
        )

    def evaluate_equipment(self, image: Optional[Image.Image] = None) -> str:
        """專屬裝備與強化深度分析"""
        if image is None:
            image, _ = ScreenCapturer.capture(monitor_index=1)
        return self.gemini_engine.evaluate_equipment_screen(
            image=image,
            game_type=self.game_type
        )

    def guide_exploration(self, image: Optional[Image.Image] = None) -> str:
        """專屬大地圖探索與素材採集指引"""
        if image is None:
            image, _ = ScreenCapturer.capture(monitor_index=1)
        return self.gemini_engine.guide_exploration_screen(
            image=image,
            game_type=self.game_type
        )

    def translate_screen(
        self,
        image: Optional[Image.Image] = None,
        target_lang: str = "繁體中文"
    ) -> tuple[str, list[dict]]:
        """
        外文遊戲畫面多模態視覺翻譯
        解析畫面中所有外文 (UI, 選單, 任務, 對話字幕, 聊天訊息)
        :param image: 可選傳入 PIL 圖像，若無則自動快照
        :param target_lang: 目標語言
        :return: (markdown_translation_report, list_of_subtitles)
        """
        if image is None:
            image, _ = ScreenCapturer.capture(monitor_index=1)

        report_md = self.gemini_engine.translate_screen(
            image=image,
            game_type=self.game_type,
            target_lang=target_lang
        )
        # 優先由單次多模態報告中直接抽取字幕與對話，避免重複發起二次全圖 API 請求以降低延遲與 Token 消耗
        subtitles = self.gemini_engine._extract_subtitles_from_json(report_md)
        if not subtitles:
            _, subtitles = self.gemini_engine.translate_chat_subtitles(
                image=image,
                game_type=self.game_type,
                target_lang=target_lang
            )
        return report_md, subtitles

    def translate_voice_to_chat(
        self,
        chinese_voice_text: str,
        target_lang: str = "英文",
        auto_submit: bool = True,
        enter_chat_key: Optional[str] = "enter"
    ) -> tuple[str, bool]:
        """
        將玩家中文語音翻譯為目標外語並自動輸入至遊戲文字聊天框
        :param chinese_voice_text: 玩家語音辨識出之中文
        :param target_lang: 目標翻譯外語
        :param auto_submit: 是否自動發送 (按 Enter 提交)
        :param enter_chat_key: 開啟聊天框之按鍵 (預設 'enter'，若 None 則直接貼上)
        :return: (translated_foreign_text, was_typed)
        """
        if not chinese_voice_text or not chinese_voice_text.strip():
            return "", False

        translated_text = self.gemini_engine.translate_voice_text(
            chinese_text=chinese_voice_text,
            target_lang=target_lang
        )

        # 透過 ScreenActuator 代替操作貼上至遊戲文字輸入框
        typed = self.actuator.paste_text_to_chat(
            text=translated_text,
            enter_chat_key=enter_chat_key,
            submit=auto_submit,
            force=True
        )
        return translated_text, typed

    # ================= 自律器官生長與網路感官接口 =================

    def grow_organ(
        self,
        requirement: str,
        organ_type: OrganType,
        name: str,
        organ_id: Optional[str] = None
    ) -> BaseOrganTool:
        """
        自律建置全新器官工具 (眼睛、耳朵、手、腳)
        調用大腦編寫代碼、AST 安全審查門禁並熱掛載至神經系統
        """
        return self.organ_registry.grow_organ(
            requirement=requirement,
            organ_type=organ_type,
            name=name,
            organ_id=organ_id
        )

    def fetch_game_knowledge(self, query: str) -> List[Dict[str, Any]]:
        """透過網路感官查詢遊戲即時攻略與百科條目"""
        return self.web_sensory.search_game_knowledge(query, self.game_type)

    def fetch_character_build(self, character_name: str) -> Dict[str, Any]:
        """查詢特定角色培育與裝備配裝推薦"""
        return self.web_sensory.fetch_character_build_guide(character_name, self.game_type)

    def fetch_exploration_guide(self, location_name: str) -> Dict[str, Any]:
        """查詢大地圖特產採集點位與解謎路線導引"""
        return self.web_sensory.fetch_exploration_targets(location_name, self.game_type)

    def fetch_boss_strategy(self, boss_name: str) -> Dict[str, Any]:
        """查詢首領戰鬥機制與危險大招應對策略"""
        return self.web_sensory.fetch_boss_mechanics(boss_name, self.game_type)

    def get_evolution_report(self) -> Dict[str, Any]:
        """
        獲取綜合神經系統進化報告
        包含大腦引擎模式、多層記憶索引深度、器官生長總量與固化反射弧統計
        """
        brain_provider = getattr(self.gemini_engine, "current_provider_name", "UNKNOWN")
        memory_stats = self.nervous_system.memory_index.get_index_stats()
        organ_summary = self.organ_registry.get_summary()
        nervous_stats = self.nervous_system.get_stats()

        return {
            "brain_engine": brain_provider,
            "memory_index": memory_stats,
            "organs": organ_summary,
            "nervous_stats": nervous_stats,
            "status_line": (
                f"🧠 大腦: {brain_provider} | "
                f"⚡ 索引: {memory_stats.get('domain_count', 0)}領域/{memory_stats.get('cluster_count', 0)}聚類 | "
                f"👁️ 器官: {organ_summary.get('total_count', 0)} (生長:{organ_summary.get('dynamic_grown_count', 0)}) | "
                f"🎯 反射弧: {nervous_stats.get('consolidated_arcs_count', 0)}"
            )
        }



if __name__ == "__main__":
    agent = UniversalGameAgent(game_type=GameType.GENSHIN, capability=AssistCapability.GUIDANCE)
    dummy_img = Image.new("RGB", (320, 240), color="blue")
    decision = agent.step(image=dummy_img)
    print("UniversalGameAgent 初始化與 Step 測試成功:")
    print(f"  策略: {agent.current_strategy.name}")
    print(f"  決策動作: {decision.primary_action} (置信度: {decision.confidence})")
    print(f"  戰術提示: {decision.guidance_text}")

