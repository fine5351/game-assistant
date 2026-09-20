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


class UniversalGameAgent:
    """
    通用遊戲 Agent 核心架構 (Universal Game Agent)
    結合 Dual-System 架構：
    - System 1 (Jev)：0.25 秒高頻反應迴圈，專注於動作選擇、信心評估與毫秒級螢幕操作。
    - System 2 (Gemini 3.8 Flash)：輔助認知層，負責使用者意圖拆解、戰術規劃與深度視覺分析。
    - Strategy Pattern：支援《原神》、《星穹鐵道》、《絕區零》、《泛用遊戲》及未來任意新遊戲之無縫擴充。
    - 全方位輔助能力：操作指導 (Guidance)、代替操作 (Screen Actuation)、即時資料分析 (Telemetry Stats)。
    """

    def __init__(
        self,
        game_type: GameType = GameType.GENSHIN,
        capability: AssistCapability = AssistCapability.GUIDANCE,
        jev_engine: Optional[JevDecisionEngine] = None,
        gemini_engine: Optional[GeminiAuxiliaryEngine] = None,
        actuator: Optional[ScreenActuator] = None
    ):
        self.game_type = game_type
        self.capability = capability
        self.jev_engine = jev_engine or JevDecisionEngine()
        self.gemini_engine = gemini_engine or GeminiAuxiliaryEngine()
        self.actuator = actuator or ScreenActuator()

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
        """設定玩家需求，並以 Gemini 優先解析為戰術指令"""
        self.current_user_demand = demand
        if demand and demand.strip():
            # 優先由 Gemini (System 2) 解析需求
            directive = self.gemini_engine.decompose_user_demand(
                user_demand=demand,
                game_type=self.game_type,
                capability=self.capability,
                image=image
            )
            self.current_gemini_directive = directive
        else:
            self.current_gemini_directive = ""

    def emergency_stop(self):
        """緊急安全熔斷開關 (F8)"""
        self.actuator.emergency_stop()
        self.set_capability(AssistCapability.GUIDANCE)

    def step(self, image: Optional[Image.Image] = None) -> StrategyDecision:
        """
        0.25 秒固定高頻決策主迴圈核心步驟 (Loop Step, 4 Hz)
        1. 獲取畫面 (若無傳入則自動擷取)
        2. 透過當前 Strategy 抽取輕量遙測數據
        3. 建構 Jev Question Schema 與 State
        4. 呼叫 Jev 進行毫秒級單 pass 決策
        5. 解釋 Jev 決策並產出 StrategyDecision
        6. 若為代替操作模式 (AUTONOMOUS)，直接執行螢幕操作
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

        # 4. Jev System 1 決策
        jev_response = self.jev_engine.evaluate(state_str, questions)

        # 5. 決策轉譯
        decision = strategy.interpret_decision(
            jev_response=jev_response,
            telemetry=telemetry,
            capability=self.capability
        )

        # 6. 代替操作螢幕執行 (若為 AUTONOMOUS 模式)
        if self.capability == AssistCapability.AUTONOMOUS:
            action_result = strategy.execute_action(decision, self.actuator)
            decision.action_result = action_result

        return decision

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



if __name__ == "__main__":
    agent = UniversalGameAgent(game_type=GameType.GENSHIN, capability=AssistCapability.GUIDANCE)
    dummy_img = Image.new("RGB", (320, 240), color="blue")
    decision = agent.step(image=dummy_img)
    print("UniversalGameAgent 初始化與 Step 測試成功:")
    print(f"  策略: {agent.current_strategy.name}")
    print(f"  決策動作: {decision.primary_action} (置信度: {decision.confidence})")
    print(f"  戰術提示: {decision.guidance_text}")

