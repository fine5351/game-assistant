import sys
import time
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal, QTimer, QObject
from PyQt6.QtWidgets import QApplication

from config import (
    GEMINI_API_KEY, TYPESAFE_API_KEY, DEFAULT_POLL_INTERVAL,
    GameType, AssistCapability, AnalysisMode, TTS_ENABLED
)
from screen_capture import ScreenCapturer
from agent import UniversalGameAgent
from gui import GameAssistantOverlay, HotkeyListener
from tts_engine import TTSEngine
from stt_engine import STTEngine


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


class GameAssistantController(QObject):
    """
    通用遊戲 Agent 主控制器
    整合 Jev 0.25s 實時決策迴圈、Gemini 3.8 Flash 輔助認知、多遊戲 Strategy、
    螢幕代替操作、GUI 懸浮面板、全域熱鍵與非同步 Worker。
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
        self.hotkey_listener = HotkeyListener()

        # 初始化背景 Worker
        self.jev_worker = JevLoopWorker(self.agent)
        self.intent_worker = GeminiIntentWorker(self.agent)
        self.deep_worker = DeepVisionWorker(self.agent)
        self.stt_worker = STTWorker(self.stt_engine)
        self.tts_worker = TTSWorker(self.tts_engine)

        self.tts_enabled = TTS_ENABLED

        # 0.25 秒高頻輪詢定時器 (250ms, 4 Hz)
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(int(DEFAULT_POLL_INTERVAL * 1000))
        self.poll_timer.timeout.connect(self._on_poll_timer_tick)

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

        # 全域熱鍵訊號
        self.hotkey_listener.emergency_stop_signal.connect(self.emergency_stop)
        self.hotkey_listener.toggle_poll_signal.connect(self.toggle_polling)
        self.hotkey_listener.manual_trigger_signal.connect(self.trigger_deep_analysis)
        self.hotkey_listener.voice_prompt_signal.connect(self.trigger_voice_prompt)

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

        # STT Worker 訊號
        self.stt_worker.stt_started.connect(self._on_stt_started)
        self.stt_worker.stt_finished.connect(self._on_stt_finished)
        self.stt_worker.stt_error.connect(self._on_stt_error)

        # TTS Worker 訊號
        self.tts_worker.tts_started.connect(self._on_tts_started)
        self.tts_worker.tts_finished.connect(self._on_tts_finished)

    def _check_api_keys(self):
        info_lines = []
        if not TYPESAFE_API_KEY:
            info_lines.append("- **TypeSafe Jev API Key**: 未設定（啟用本地確定性啟發決策器）")
        else:
            info_lines.append("- **TypeSafe Jev API Key**: 🟢 已就緒")

        if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
            info_lines.append("- **Gemini 3.8 Flash Key**: ⚠️ 未設定（Gemini 輔助意圖解析處於離線狀態）")
        else:
            info_lines.append("- **Gemini 3.8 Flash Key**: 🟢 已就緒")

        msg = (
            "### 🎮 Jev 通用遊戲 Agent 引擎狀態\n\n" +
            "\n".join(info_lines) +
            "\n\n按下 **F9** 即可開始每 0.25 秒高頻戰況分析與操作！"
        )
        self.overlay.update_result(msg)

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
            elif capability in (AssistCapability.GUIDANCE, AssistCapability.AUTONOMOUS):
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

        # 若判定危險閃避且開啟 TTS，進行即時語音告警
        if self.tts_enabled and decision.should_evade and not self.tts_worker.isRunning():
            self.tts_worker.speak_text("注意閃避！")

    def _on_jev_error(self, error_msg: str):
        self.overlay.update_result(error_msg)

    def trigger_deep_analysis(self):
        """手動觸發 Gemini 3.8 Flash 深度多模態視覺快照分析 (F10)"""
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
        self.overlay.status_footer.setText(f"狀態: 🎤 辨識成功：「{recognized_text}」，Gemini 拆解意圖中...")
        # 階段 1：交由 Gemini 處理使用者需求
        self.intent_worker.request_intent_decomposition(recognized_text)

    def _on_stt_error(self, error_msg: str):
        self.overlay.reset_voice_button()
        self.overlay.update_result(f"⚠️ **語音辨識提醒**：\n\n{error_msg}")

    def _on_intent_started(self):
        self.overlay.status_footer.setText("狀態: 🧠 Gemini 3.8 Flash 正在將需求拆解為戰術指示...")

    def _on_intent_finished(self, directive: str):
        self.overlay.status_footer.setText("狀態: 🟢 戰術意圖已傳入 Jev 決策迴圈！")
        display_md = (
            f"### 🎤 玩家語音需求解析完成\n\n"
            f"**原始需求**：`{self.agent.current_user_demand}`\n\n"
            f"**Gemini (System 2) 戰術指示**：\n\n{directive}\n\n"
            f"---\n*已即刻接入 Jev 0.25 秒高頻決策迴圈，即刻執行微觀操作或指導。*"
        )
        self.overlay.show_intent_result(display_md)
        if self.tts_enabled:
            self.tts_worker.speak_text(directive)

        # 關鍵銜接 (Requirement 4)：先由 gemini 處理使用者需求，再接入 jev 處理
        self._trigger_jev_step()

    def _on_intent_error(self, err_msg: str):
        self.overlay.update_result(err_msg)

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
        self.hotkey_listener.stop()
        self.tts_worker.stop_speaking()
        for worker in (self.jev_worker, self.intent_worker, self.deep_worker, self.stt_worker, self.tts_worker):
            if worker.isRunning():
                worker.quit()
                worker.wait(500)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    controller = GameAssistantController()
    controller.show()

    def cleanup():
        controller.stop()

    app.aboutToQuit.connect(cleanup)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
