import sys
import time
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal, QTimer, QObject

from game_assistant.core.config import (
    GEMINI_API_KEY, TYPESAFE_API_KEY, DEFAULT_POLL_INTERVAL,
    GameType, AssistCapability, AnalysisMode, TTS_ENABLED,
    CONSOLIDATION_AUTO_ENABLED, CONSOLIDATION_INTERVAL_SECONDS
)
from game_assistant.utils.screen_capture import ScreenCapturer
from game_assistant.core.agent import UniversalGameAgent
from game_assistant.ui.gui import GameAssistantOverlay, HotkeyListener, FloatingSubtitleOverlay
from game_assistant.audio.tts_engine import TTSEngine
from game_assistant.audio.stt_engine import STTEngine


class JevLoopWorker(QThread):
    """
    非同步 0.25 秒高頻 Jev 決策 Worker 執行緒 (4 Hz)
    執行畫面擷取、遙測抽取、Jev System 1 決策與螢幕代替操作
    確保 UI 執行緒 60 FPS 零卡頓與無死鎖
    """
    decision_ready = pyqtSignal(object, float)
    loop_error = pyqtSignal(str)

    def __init__(self, agent: UniversalGameAgent):
        super().__init__()
        self.agent = agent
        self._is_busy = False

    def is_busy(self) -> bool:
        return self._is_busy

    def request_step(self) -> bool:
        if self._is_busy:
            return False
        self.start()
        return True

    def run(self):
        self._is_busy = True
        try:
            start_t = time.perf_counter()
            image, capture_ms = ScreenCapturer.capture(monitor_index=1)
            decision = self.agent.step(image=image)
            total_elapsed = (time.perf_counter() - start_t) * 1000.0
            self.decision_ready.emit(decision, capture_ms)
        except Exception as e:
            self.loop_error.emit(f"❌ Jev 決策迴圈異常：{str(e)}")
        finally:
            self._is_busy = False


class GeminiIntentWorker(QThread):
    """
    Gemini 3.8 Flash 輔助認知 Worker 執行緒 (System 2)
    負責在背景將玩家語音/文字需求 (User Demand) 拆解為戰術指示 (Directive)
    完全不阻塞 Jev 0.25 秒的高頻反應
    """
    intent_started = pyqtSignal()
    intent_finished = pyqtSignal(str)
    intent_error = pyqtSignal(str)

    def __init__(self, agent: UniversalGameAgent):
        super().__init__()
        self.agent = agent
        self.user_demand = ""
        self._is_running = False

    def is_running(self) -> bool:
        return self._is_running

    def request_intent_decomposition(self, demand: str) -> bool:
        if self._is_running or not demand:
            return False
        self.user_demand = demand
        self.start()
        return True

    def run(self):
        self._is_running = True
        self.intent_started.emit()
        try:
            image, _ = ScreenCapturer.capture(monitor_index=1)
            self.agent.set_user_demand(self.user_demand, image=image)
            directive = self.agent.current_gemini_directive
            self.intent_finished.emit(directive)
        except Exception as e:
            self.intent_error.emit(f"❌ Gemini 意圖拆解異常：{str(e)}")
        finally:
            self._is_running = False


class DeepVisionWorker(QThread):
    """
    Gemini 3.8 Flash 深度多模態視覺分析 Worker (F10 快照分析 / 遺器養成 / 解謎)
    """
    deep_analysis_started = pyqtSignal()
    deep_analysis_finished = pyqtSignal(str, float)
    deep_analysis_error = pyqtSignal(str)

    def __init__(self, agent: UniversalGameAgent):
        super().__init__()
        self.agent = agent
        self.custom_prompt = ""
        self._is_busy = False

    def is_busy(self) -> bool:
        return self._is_busy

    def request_deep_analysis(self, custom_prompt: str = "") -> bool:
        if self._is_busy:
            return False
        self.custom_prompt = custom_prompt
        self.start()
        return True

    def run(self):
        self._is_busy = True
        self.deep_analysis_started.emit()
        try:
            image, capture_ms = ScreenCapturer.capture(monitor_index=1)
            result_md = self.agent.trigger_deep_analysis(image=image, custom_prompt=self.custom_prompt)
            self.deep_analysis_finished.emit(result_md, capture_ms)
        except Exception as e:
            self.deep_analysis_error.emit(f"❌ 深度分析異常：{str(e)}")
        finally:
            self._is_busy = False


class ScreenTranslationWorker(QThread):
    """
    Gemini 3.8 Flash 遊戲畫面與字幕即時多模態翻譯 Worker (F7)
    負責非同步擷取畫面並翻譯畫面中所有外文 UI、選單、對話與任務
    """
    translation_started = pyqtSignal()
    translation_finished = pyqtSignal(str, list, float)  # markdown, subtitles, elapsed_ms
    translation_error = pyqtSignal(str)

    def __init__(self, agent: UniversalGameAgent):
        super().__init__()
        self.agent = agent
        self.target_lang = "繁體中文"
        self._is_busy = False

    def is_busy(self) -> bool:
        return self._is_busy

    def request_translation(self, target_lang: str = "繁體中文") -> bool:
        if self._is_busy:
            return False
        self.target_lang = target_lang
        self.start()
        return True

    def run(self):
        self._is_busy = True
        self.translation_started.emit()
        try:
            start_t = time.perf_counter()
            image, capture_ms = ScreenCapturer.capture(monitor_index=1)
            report_md, subtitles = self.agent.translate_screen(
                image=image,
                target_lang=self.target_lang
            )
            total_elapsed = (time.perf_counter() - start_t) * 1000.0
            self.translation_finished.emit(report_md, subtitles, total_elapsed)
        except Exception as e:
            self.translation_error.emit(f"❌ 畫面翻譯異常：{str(e)}")
        finally:
            self._is_busy = False


class VoiceTranslationWorker(QThread):
    """
    雙向語音對話翻譯 Worker (F6)
    負責錄製玩家中文語音 (STT) -> 翻譯為目標外語 -> 代替操作自動貼上輸入至遊戲聊天框
    """
    voice_trans_started = pyqtSignal()
    voice_trans_finished = pyqtSignal(str, str, bool)  # original_zh, translated_foreign, was_typed
    voice_trans_error = pyqtSignal(str)

    def __init__(self, agent: UniversalGameAgent, stt_engine: STTEngine):
        super().__init__()
        self.agent = agent
        self.stt_engine = stt_engine
        self.target_lang = "英文"
        self.auto_submit = True
        self.enter_chat_key = "enter"
        self._is_running = False

    def is_running(self) -> bool:
        return self._is_running

    def request_voice_translation(
        self,
        target_lang: str = "英文",
        auto_submit: bool = True,
        enter_chat_key: Optional[str] = "enter"
    ) -> bool:
        if self._is_running:
            return False
        self.target_lang = target_lang
        self.auto_submit = auto_submit
        self.enter_chat_key = enter_chat_key
        self.start()
        return True

    def run(self):
        self._is_running = True
        self.voice_trans_started.emit()
        try:
            # 1. 麥克風擷取並辨識玩家中文語音
            success, text_or_err = self.stt_engine.listen_and_recognize()
            if not success:
                self.voice_trans_error.emit(text_or_err)
                return

            chinese_text = text_or_err.strip()

            # 2. 翻譯為目標外語並自動輸入至遊戲聊天框
            foreign_text, was_typed = self.agent.translate_voice_to_chat(
                chinese_voice_text=chinese_text,
                target_lang=self.target_lang,
                auto_submit=self.auto_submit,
                enter_chat_key=self.enter_chat_key
            )
            self.voice_trans_finished.emit(chinese_text, foreign_text, was_typed)
        except Exception as e:
            self.voice_trans_error.emit(f"❌ 語音翻譯輸入異常：{str(e)}")
        finally:
            self._is_running = False


class STTWorker(QThread):
    """非同步語音指令辨識 (STT) Worker 執行緒"""
    stt_started = pyqtSignal()
    stt_finished = pyqtSignal(str)
    stt_error = pyqtSignal(str)

    def __init__(self, stt_engine: STTEngine):
        super().__init__()
        self.stt_engine = stt_engine
        self._is_running = False

    def is_running(self) -> bool:
        return self._is_running

    def request_stt(self) -> bool:
        if self._is_running:
            return False
        self.start()
        return True

    def run(self):
        self._is_running = True
        self.stt_started.emit()
        try:
            success, text_or_err = self.stt_engine.listen_and_recognize()
            if success:
                self.stt_finished.emit(text_or_err)
            else:
                self.stt_error.emit(text_or_err)
        except Exception as e:
            self.stt_error.emit(f"❌ 語音辨識異常：{str(e)}")
        finally:
            self._is_running = False


class TTSWorker(QThread):
    """非同步離線語音播報 (TTS) Worker 執行緒"""
    tts_started = pyqtSignal()
    tts_finished = pyqtSignal()

    def __init__(self, tts_engine: TTSEngine):
        super().__init__()
        self.tts_engine = tts_engine
        self.text_to_speak = ""

    def speak_text(self, text: str):
        if not text:
            return
        if self.isRunning():
            self.tts_engine.stop()
            self.wait(300)
        self.text_to_speak = text
        self.start()

    def stop_speaking(self):
        if self.isRunning():
            self.tts_engine.stop()

    def run(self):
        self.tts_started.emit()
        try:
            self.tts_engine.speak(self.text_to_speak)
        except Exception as e:
            print(f"[TTSWorker] 播報異常: {e}")
        finally:
            self.tts_finished.emit()


class ConsolidationWorker(QThread):
    """
    非同步神經記憶固化 Worker 執行緒 (Consolidation Worker)
    在背景分析累積之 Gemini 大腦思考記憶，提煉共通模式並固化為 Jev 反射弧 (input, output, flow)
    完全不阻塞 Jev 0.25s 實時反射與 UI 60 FPS 渲染
    """
    consolidation_started = pyqtSignal()
    consolidation_finished = pyqtSignal(list, dict)  # new_arcs, stats
    consolidation_error = pyqtSignal(str)

    def __init__(self, agent: UniversalGameAgent):
        super().__init__()
        self.agent = agent
        self.force = False
        self._is_busy = False

    def is_busy(self) -> bool:
        return self._is_busy

    def request_consolidation(self, force: bool = False) -> bool:
        if self._is_busy:
            return False
        self.force = force
        self.start()
        return True

    def run(self):
        self._is_busy = True
        self.consolidation_started.emit()
        try:
            new_arcs = self.agent.consolidate_memories(force=self.force)
            stats = self.agent.get_nervous_system_stats()
            self.consolidation_finished.emit(new_arcs, stats)
        except Exception as e:
            self.consolidation_error.emit(f"❌ 記憶固化異常：{str(e)}")
        finally:
            self._is_busy = False


class GameAssistantController(QObject):
    """
    通用遊戲 Agent 主控制器
    整合 Jev 0.25s 實時決策迴圈、Gemini 3.8 Flash 輔助認知、多遊戲 Strategy、
    人類神經系統自我進化 (反射神經 + 大腦 + 記憶固化管線)、螢幕代替操作、GUI 與全域熱鍵。
    """
    def __init__(self):
        super().__init__()

        # 初始化 Universal Game Agent
        self.agent = UniversalGameAgent(
            game_type=GameType.GENSHIN,
            capability=AssistCapability.GUIDANCE
        )

        # 初始化語音模組與介面
        self.tts_engine = TTSEngine()
        self.stt_engine = STTEngine()
        self.overlay = GameAssistantOverlay()
        self.floating_subtitle = FloatingSubtitleOverlay()
        self.hotkey_listener = HotkeyListener()

        # 初始化背景 Worker
        self.jev_worker = JevLoopWorker(self.agent)
        self.intent_worker = GeminiIntentWorker(self.agent)
        self.deep_worker = DeepVisionWorker(self.agent)
        self.stt_worker = STTWorker(self.stt_engine)
        self.tts_worker = TTSWorker(self.tts_engine)
        self.trans_worker = ScreenTranslationWorker(self.agent)
        self.voice_trans_worker = VoiceTranslationWorker(self.agent, self.stt_engine)
        self.consolidation_worker = ConsolidationWorker(self.agent)

        self.tts_enabled = TTS_ENABLED

        # 0.25 秒高頻輪詢定時器 (250ms, 4 Hz)
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(int(DEFAULT_POLL_INTERVAL * 1000))
        self.poll_timer.timeout.connect(self._on_poll_timer_tick)

        # 定時自動自我進化固化管線 (預設每 30 秒整理一次記憶)
        self.consolidation_timer = QTimer(self)
        self.consolidation_timer.setInterval(int(CONSOLIDATION_INTERVAL_SECONDS * 1000))
        self.consolidation_timer.timeout.connect(self._on_consolidation_timer_tick)
        if CONSOLIDATION_AUTO_ENABLED:
            self.consolidation_timer.start()

        self._bind_signals()
        self.hotkey_listener.start()

        # 檢查金鑰狀態
        self._check_api_keys()

    def _bind_signals(self):
        # GUI 觸發訊號
        self.overlay.game_changed_signal.connect(self._on_game_changed)
        self.overlay.capability_changed_signal.connect(self._on_capability_changed)
        self.overlay.manual_analyze_signal.connect(self.trigger_deep_analysis)
        self.overlay.toggle_poll_signal.connect(self.toggle_polling)
        self.overlay.emergency_stop_signal.connect(self.emergency_stop)
        self.overlay.voice_prompt_signal.connect(self.trigger_voice_prompt)
        self.overlay.tts_toggle_signal.connect(self._on_tts_toggled)
        self.overlay.screen_translate_signal.connect(self.trigger_screen_translation)
        self.overlay.voice_translate_signal.connect(self.trigger_voice_translation)
        self.overlay.consolidate_signal.connect(lambda: self.trigger_consolidation(force=True))

        # 全域熱鍵訊號
        self.hotkey_listener.emergency_stop_signal.connect(self.emergency_stop)
        self.hotkey_listener.toggle_poll_signal.connect(self.toggle_polling)
        self.hotkey_listener.manual_trigger_signal.connect(self.trigger_deep_analysis)
        self.hotkey_listener.voice_prompt_signal.connect(self.trigger_voice_prompt)
        self.hotkey_listener.screen_translate_signal.connect(self.trigger_screen_translation)
        self.hotkey_listener.voice_translate_signal.connect(self.trigger_voice_translation)
        self.hotkey_listener.consolidate_signal.connect(lambda: self.trigger_consolidation(force=True))


        # Jev 0.25s 決策迴圈訊號
        self.jev_worker.decision_ready.connect(self._on_jev_decision_ready)
        self.jev_worker.loop_error.connect(self._on_jev_error)

        # Gemini 意圖 Worker 訊號
        self.intent_worker.intent_started.connect(self._on_intent_started)
        self.intent_worker.intent_finished.connect(self._on_intent_finished)
        self.intent_worker.intent_error.connect(self._on_intent_error)

        # 深度分析 Worker 訊號
        self.deep_worker.deep_analysis_started.connect(self._on_deep_started)
        self.deep_worker.deep_analysis_finished.connect(self._on_deep_finished)
        self.deep_worker.deep_analysis_error.connect(self._on_deep_error)

        # 畫面翻譯 Worker 訊號
        self.trans_worker.translation_started.connect(self._on_trans_started)
        self.trans_worker.translation_finished.connect(self._on_trans_finished)
        self.trans_worker.translation_error.connect(self._on_trans_error)

        # 語音翻譯 Worker 訊號
        self.voice_trans_worker.voice_trans_started.connect(self._on_voice_trans_started)
        self.voice_trans_worker.voice_trans_finished.connect(self._on_voice_trans_finished)
        self.voice_trans_worker.voice_trans_error.connect(self._on_voice_trans_error)

        # STT Worker 訊號
        self.stt_worker.stt_started.connect(self._on_stt_started)
        self.stt_worker.stt_finished.connect(self._on_stt_finished)
        self.stt_worker.stt_error.connect(self._on_stt_error)

        # TTS Worker 訊號
        self.tts_worker.tts_started.connect(self._on_tts_started)
        self.tts_worker.tts_finished.connect(self._on_tts_finished)

        # 神經固化 Worker 訊號
        self.consolidation_worker.consolidation_started.connect(self._on_consolidation_started)
        self.consolidation_worker.consolidation_finished.connect(self._on_consolidation_finished)
        self.consolidation_worker.consolidation_error.connect(self._on_consolidation_error)

    def _check_api_keys(self):
        info_lines = []
        evo_report = self.agent.get_evolution_report()
        brain_provider = evo_report.get("brain_engine", "UNKNOWN")

        if not TYPESAFE_API_KEY:
            info_lines.append("- **TypeSafe Jev (System 1)**: 🟢 本地確定性啟發反射弧已就緒")
        else:
            info_lines.append("- **TypeSafe Jev (System 1)**: 🟢 SDK 連線就緒")

        if "Antigravity" in brain_provider:
            info_lines.append(f"- **大腦認知 (System 2)**: 🟢 **{brain_provider}** (免金鑰本地大腦推論就緒)")
        elif GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
            info_lines.append("- **大腦認知 (System 2)**: 🟢 Google Gemini 3.8 Flash SDK 已就緒")
        else:
            info_lines.append("- **大腦認知 (System 2)**: 🛡️ 本地啟發推論規則保護中")

        mem_stats = evo_report.get("memory_index", {})
        organ_sum = evo_report.get("organs", {})
        nervous_stats = evo_report.get("nervous_stats", {})

        info_lines.append(
            f"- **多層樹狀記憶索引**: ⚡ {mem_stats.get('domain_count', 0)} 大領域 / {mem_stats.get('cluster_count', 0)} 個意圖機制聚類桶"
        )
        info_lines.append(
            f"- **感官與致動器官庫**: 👁️ {organ_sum.get('total_count', 0)} 個已掛載器官 (動態生長: {organ_sum.get('dynamic_grown_count', 0)})"
        )
        info_lines.append(
            f"- **神經反射弧與進化**: 🎯 固化反射弧 {nervous_stats.get('consolidated_arcs_count', 0)} 個 | 命中率: {nervous_stats.get('reflex_hit_rate', 0.0)}%"
        )

        msg = (
            "### 🎮 Jev 自律進化遊戲神經系統已就緒 (Hierarchical Memory & Dynamic Organs)\n\n" +
            "\n".join(info_lines) +
            "\n\n按下 **F9** 即可開始每 0.25 秒高頻戰況分析與操作！"
        )
        self.overlay.update_result(msg)
        self.overlay.update_nervous_hud(evo_report.get("status_line", ""))

    def _on_consolidation_timer_tick(self):
        """定時觸發記憶整理與模式固化"""
        self.trigger_consolidation(force=False)

    def trigger_consolidation(self, force: bool = True):
        """手動或定時觸發記憶固化管線 (將 Gemini 大腦成果固化為 Jev 反射弧)"""
        if not self.consolidation_worker.is_busy():
            self.consolidation_worker.request_consolidation(force=force)

    def _on_consolidation_started(self):
        self.overlay.set_status_consolidating()
        self.overlay.status_footer.setText("狀態: 🧬 神經系統正在整理記憶並固化為 Jev 反射神經...")

    def _on_consolidation_finished(self, new_arcs: list, stats: dict):
        self.overlay.reset_consolidate_button()
        if new_arcs:
            arc_names = "、".join(f"【{a.name}】" for a in new_arcs[:3])
            self.overlay.status_footer.setText(f"狀態: ✨ 成功固化 {len(new_arcs)} 個 Jev 反射神經：{arc_names}！")
            msg = (
                f"### 🧬 神經系統自我進化成功\n\n"
                f"本次成功將大腦思考記憶固化為 **{len(new_arcs)}** 個全新 Jev 反射弧：\n" +
                "\n".join(f"- **{a.name}** (觸發特徵: `{', '.join(a.trigger_keywords)}`)" for a in new_arcs) +
                f"\n\n- **當前進化階段**：`{stats.get('current_evolution_stage')}`\n"
                f"- **固化反射弧總數**：`{stats.get('total_reflex_arcs')}` 個\n"
                f"- **反射命中率**：`{stats.get('reflex_hit_rate')}%`\n\n"
                f"*往後遇到相同或相似情境，系統將直接由 Jev 毫秒級反射輸出，無需進入大腦思考！*"
            )
            self.overlay.update_result(msg)
        else:
            hit_rate = stats.get('reflex_hit_rate', 0.0)
            total_arcs = stats.get('total_reflex_arcs', 0)
            self.overlay.status_footer.setText(f"狀態: 🧬 神經系統運作中 (反射命中率: {hit_rate}%, 固化反射弧: {total_arcs} 個)")

    def _on_consolidation_error(self, err_msg: str):
        self.overlay.reset_consolidate_button()
        print(f"[GameAssistantController] {err_msg}")


    def _on_game_changed(self, game_type):
        if game_type:
            self.agent.set_game_type(game_type)
            self.overlay.status_footer.setText(f"狀態: 已切換遊戲策略 ➔ {self.agent.current_strategy.name}")

    def _on_capability_changed(self, capability):
        if capability:
            self.agent.set_capability(capability)
            cap_name = capability.value if hasattr(capability, "value") else str(capability)
            self.overlay.status_footer.setText(f"狀態: 已切換輔助能力 ➔ {cap_name}")
            if capability == AssistCapability.DATA_ANALYSIS:
                report = self.agent.generate_data_analysis_report()
                self.overlay.show_data_analysis(report)
            elif capability == AssistCapability.TRANSLATION:
                self.trigger_screen_translation()
            elif capability in (
                AssistCapability.GUIDANCE,
                AssistCapability.AUTONOMOUS,
                AssistCapability.EXPLORATION,
                AssistCapability.EQUIPMENT_BUILD
            ):
                self.overlay.set_guidance_display_mode()

    def emergency_stop(self):
        """緊急安全熔斷開關 (F8)"""
        self.agent.emergency_stop()
        self.tts_worker.stop_speaking()
        self.overlay.combo_capability.setCurrentIndex(0)  # 切回操作指導
        self.overlay.set_guidance_display_mode()
        self.overlay.status_footer.setText("狀態: 🛑 已觸發緊急停止！已關閉代替操作！")
        self.overlay.update_result("### 🛑 緊急安全停止已觸發\n\n已立即強制解除所有螢幕鍵盤按鍵與滑鼠模擬操作，系統已安全切回【操作指導】模式。")

    def toggle_polling(self):
        """切換 0.25 秒高頻 Jev 自動決策輪詢"""
        if self.poll_timer.isActive():
            self.poll_timer.stop()
            self.overlay.set_poll_status(False)
        else:
            self.poll_timer.start()
            self.overlay.set_poll_status(True)
            self._trigger_jev_step()

    def _on_poll_timer_tick(self):
        self._trigger_jev_step()

    def _trigger_jev_step(self):
        if not self.jev_worker.is_busy():
            self.jev_worker.request_step()

    def _on_jev_decision_ready(self, decision, capture_ms: float):
        if self.agent.capability == AssistCapability.DATA_ANALYSIS:
            report = self.agent.generate_data_analysis_report()
            self.overlay.update_data_analysis_hud(report, decision, capture_ms)
        else:
            self.overlay.update_decision_hud(decision, capture_ms)

        # 定期同步神經 HUD
        self._step_counter = getattr(self, "_step_counter", 0) + 1
        if self._step_counter % 20 == 0:
            evo_report = self.agent.get_evolution_report()
            self.overlay.update_nervous_hud(evo_report.get("status_line", ""))

        # 若判定危險閃避且開啟 TTS，進行即時語音告警
        if self.tts_enabled and decision.should_evade and not self.tts_worker.isRunning():
            self.tts_worker.speak_text("注意閃避！")

    def _on_jev_error(self, error_msg: str):
        self.overlay.update_result(error_msg)

    def trigger_deep_analysis(self):
        """手動觸發大腦深度多模態視覺快照分析 (F10)"""
        if self.deep_worker.is_busy():
            return
        self.overlay.set_status_loading()
        self.deep_worker.request_deep_analysis()

    def _on_deep_started(self):
        self.overlay.set_status_loading()

    def _on_deep_finished(self, markdown_text: str, capture_ms: float):
        self.overlay.show_deep_analysis(markdown_text, capture_ms)
        if self.tts_enabled:
            self.tts_worker.speak_text(markdown_text)

    def _on_deep_error(self, err_msg: str):
        self.overlay.update_result(err_msg)

    def trigger_voice_prompt(self):
        """觸發麥克風語音需求提問 (F11)"""
        if self.stt_worker.is_running():
            return
        self.tts_worker.stop_speaking()
        self.stt_worker.request_stt()

    def _on_stt_started(self):
        self.overlay.set_status_listening()

    def _on_stt_finished(self, recognized_text: str):
        self.overlay.reset_voice_button()
        self.overlay.status_footer.setText(f"狀態: 🎤 辨識成功：「{recognized_text}」，大腦拆解意圖中...")
        # 階段 1：交由大腦處理使用者需求
        self.intent_worker.request_intent_decomposition(recognized_text)

    def _on_stt_error(self, error_msg: str):
        self.overlay.reset_voice_button()
        self.overlay.update_result(f"⚠️ **語音辨識提醒**：\n\n{error_msg}")

    def _on_intent_started(self):
        self.overlay.status_footer.setText("狀態: 🧠 大腦正在將需求拆解為戰術指示...")

    def _on_intent_finished(self, directive: str):
        self.overlay.status_footer.setText("狀態: 🟢 戰術意圖已傳入 Jev 決策迴圈！")
        display_md = (
            f"### 🎤 玩家語音需求解析完成\n\n"
            f"**原始需求**：`{self.agent.current_user_demand}`\n\n"
            f"**大腦 (System 2) 戰術指示**：\n\n{directive}\n\n"
            f"---\n*已即刻接入 Jev 0.25 秒高頻決策迴圈，即刻執行微觀操作或指導。*"
        )
        self.overlay.show_intent_result(display_md)
        if self.tts_enabled:
            self.tts_worker.speak_text(directive)

        # 同步更新 HUD
        evo_report = self.agent.get_evolution_report()
        self.overlay.update_nervous_hud(evo_report.get("status_line", ""))

        # 關鍵銜接：先由大腦處理使用者需求，再接入 jev 處理
        self._trigger_jev_step()

    def _on_intent_error(self, err_msg: str):
        self.overlay.update_result(err_msg)

    def trigger_screen_translation(self):
        """觸發遊戲畫面與字幕即時外文翻譯 (F7)"""
        if self.trans_worker.is_busy():
            return
        self.overlay.set_status_translating()
        self.trans_worker.request_translation(target_lang="繁體中文")

    def _on_trans_started(self):
        self.overlay.set_status_translating()

    def _on_trans_finished(self, report_md: str, subtitles: list, elapsed_ms: float):
        self.overlay.show_translation_view(report_md, elapsed_ms)
        if subtitles and len(subtitles) > 0:
            self.floating_subtitle.show_subtitles_list(subtitles, duration_ms=8000)
            if self.tts_enabled:
                tts_text = " ".join([s.get("translated", "").strip() for s in subtitles if s.get("translated")])
                if tts_text:
                    self.tts_worker.speak_text(tts_text)

    def _on_trans_error(self, err_msg: str):
        self.overlay.update_result(err_msg)

    def trigger_voice_translation(self, target_lang: Optional[str] = None):
        """觸發語音翻譯並自動輸入至遊戲文字聊天框 (F6)"""
        if self.voice_trans_worker.is_running():
            return
        self.tts_worker.stop_speaking()
        lang = target_lang or self.overlay.get_target_language()
        self.voice_trans_worker.request_voice_translation(target_lang=lang, auto_submit=True)

    def _on_voice_trans_started(self):
        self.overlay.set_status_voice_translating()

    def _on_voice_trans_finished(self, chinese: str, foreign: str, was_typed: bool):
        self.overlay.reset_voice_translate_button()
        target_lang = self.overlay.get_target_language()
        status_msg = f"狀態: 💬 語音已轉為 {target_lang} 並輸入聊天框：「{foreign}」"
        self.overlay.status_footer.setText(status_msg)

        input_status = "✅ 已代替操作自動貼上至遊戲聊天框並發送" if was_typed else "📋 已複製至剪貼簿 (可手動按 Ctrl+V 貼上)"
        md = (
            f"### 💬 語音對話雙向翻譯完成\n\n"
            f"- **中文原音**：`{chinese}`\n"
            f"- **外語翻譯 ({target_lang})**：`{foreign}`\n"
            f"- **聊天框輸入狀態**：{input_status}\n\n"
            f"---\n*可繼續按下 F6 進行下一次語音對話輸入。*"
        )
        self.overlay.output_browser.setMarkdown(md)
        self.floating_subtitle.show_subtitle(
            translated=f"我方發言: {chinese}",
            original=foreign,
            duration_ms=6000
        )

    def _on_voice_trans_error(self, err_msg: str):
        self.overlay.reset_voice_translate_button()
        self.overlay.update_result(f"⚠️ **語音翻譯輸入提醒**：\n\n{err_msg}")

    def _on_tts_toggled(self, enabled: bool):
        self.tts_enabled = enabled
        if not enabled:
            self.tts_worker.stop_speaking()

    def _on_tts_started(self):
        curr = self.overlay.status_footer.text()
        self.overlay.status_footer.setText(f"{curr} | 🔊 語音朗讀中...")

    def _on_tts_finished(self):
        pass

    def show(self):
        self.overlay.show()

    def stop(self):
        self.poll_timer.stop()
        self.consolidation_timer.stop()
        self.hotkey_listener.stop()
        self.tts_worker.stop_speaking()
        self.floating_subtitle.close()
        for worker in (
            self.jev_worker, self.intent_worker, self.deep_worker,
            self.stt_worker, self.tts_worker, self.trans_worker, self.voice_trans_worker,
            self.consolidation_worker
        ):
            if worker.isRunning():
                worker.quit()
                worker.wait(500)

