import sys
import time
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal, QTimer, QObject
from PyQt6.QtWidgets import QApplication, QMessageBox

from config import (
    GEMINI_API_KEY, DEFAULT_POLL_INTERVAL, GameType, AnalysisMode, TTS_ENABLED
)
from screen_capture import ScreenCapturer
from ai_engine import GeminiAIEngine
from gui import GameAssistantOverlay, HotkeyListener
from tts_engine import TTSEngine
from stt_engine import STTEngine


class AnalysisWorker(QThread):
    """
    非同步 AI 分析 Worker 執行緒
    將「畫面擷取」與「Gemini 多模態 API 請求」移至背景執行
    絕不卡頓或阻塞 PyQt UI 主執行緒
    """
    analysis_started = pyqtSignal()
    analysis_finished = pyqtSignal(str, float)
    analysis_error = pyqtSignal(str)

    def __init__(self, ai_engine: GeminiAIEngine):
        super().__init__()
        self.ai_engine = ai_engine
        self.game_type = GameType.GENSHIN
        self.mode = AnalysisMode.COMBAT
        self.custom_prompt = ""
        self._is_busy = False

    def is_busy(self) -> bool:
        return self._is_busy

    def request_analysis(self, game_type: GameType, mode: AnalysisMode, custom_prompt: str = ""):
        if self._is_busy:
            return False
        self.game_type = game_type
        self.mode = mode
        self.custom_prompt = custom_prompt
        self.start()
        return True

    def run(self):
        self._is_busy = True
        self.analysis_started.emit()
        try:
            # 1. 超低延遲畫面擷取 (ms)
            image, capture_ms = ScreenCapturer.capture(monitor_index=1)

            # 2. Gemini 多模態分析
            result_markdown = self.ai_engine.analyze_screen(
                image=image,
                game_type=self.game_type,
                mode=self.mode,
                custom_prompt=self.custom_prompt
            )

            self.analysis_finished.emit(result_markdown, capture_ms)
        except Exception as e:
            self.analysis_error.emit(f"❌ 執行過程拋出異常：{str(e)}")
        finally:
            self._is_busy = False


class STTWorker(QThread):
    """
    非同步語音指令辨識 (STT) Worker 執行緒
    獨立執行麥克風錄音與語音轉文字辨識，防止死鎖或 UI 卡頓
    """
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
            self.stt_error.emit(f"❌ 語音辨識過程拋出異常：{str(e)}")
        finally:
            self._is_running = False


class TTSWorker(QThread):
    """
    非同步離線語音播報 (TTS) Worker 執行緒
    獨立在 COM 線程中進行語音朗讀，避免主 UI 線程與分析線程卡頓
    """
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
            print(f"[TTSWorker] 播報過程異常: {e}")
        finally:
            self.tts_finished.emit()


class GameAssistantController(QObject):
    """
    主控制器：整合 GUI, AI 引擎, TTS/STT 語音模組, 畫面擷取, 全域熱鍵與非同步 Worker
    """
    def __init__(self):
        super().__init__()

        # 初始化 AI 引擎與語音引擎
        self.ai_engine = GeminiAIEngine(GEMINI_API_KEY)
        self.tts_engine = TTSEngine()
        self.stt_engine = STTEngine()

        # 初始化 GUI 與熱鍵
        self.overlay = GameAssistantOverlay()
        self.hotkey_listener = HotkeyListener()

        # 初始化 Worker 執行緒
        self.worker = AnalysisWorker(self.ai_engine)
        self.stt_worker = STTWorker(self.stt_engine)
        self.tts_worker = TTSWorker(self.tts_engine)

        self.tts_enabled = TTS_ENABLED

        # 輪詢 Timer
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(int(DEFAULT_POLL_INTERVAL * 1000))
        self.poll_timer.timeout.connect(self._on_poll_timer_tick)

        self._bind_signals()
        self.hotkey_listener.start()

        # 啟動時檢查 API Key
        self._check_api_key_status()

    def _bind_signals(self):
        # GUI 觸發訊號
        self.overlay.manual_analyze_signal.connect(self.trigger_manual_analysis)
        self.overlay.toggle_poll_signal.connect(self.toggle_polling)
        self.overlay.voice_prompt_signal.connect(self.trigger_voice_prompt)
        self.overlay.tts_toggle_signal.connect(self._on_tts_toggled)

        # 熱鍵觸發訊號
        self.hotkey_listener.toggle_poll_signal.connect(self.toggle_polling)
        self.hotkey_listener.manual_trigger_signal.connect(self.trigger_manual_analysis)
        self.hotkey_listener.voice_prompt_signal.connect(self.trigger_voice_prompt)

        # Analysis Worker 狀態與回傳訊號
        self.worker.analysis_started.connect(self._on_analysis_started)
        self.worker.analysis_finished.connect(self._on_analysis_finished)
        self.worker.analysis_error.connect(self._on_analysis_error)

        # STT Worker 訊號
        self.stt_worker.stt_started.connect(self._on_stt_started)
        self.stt_worker.stt_finished.connect(self._on_stt_finished)
        self.stt_worker.stt_error.connect(self._on_stt_error)

        # TTS Worker 訊號
        self.tts_worker.tts_started.connect(self._on_tts_started)
        self.tts_worker.tts_finished.connect(self._on_tts_finished)

    def _check_api_key_status(self):
        if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
            warning_msg = (
                "### ⚠️ 尚未設定 Gemini API Key\n\n"
                "請於專案根目錄下建立 `.env` 檔案並填入您的 API 金鑰：\n"
                "```env\n"
                "GEMINI_API_KEY=your_actual_api_key_here\n"
                "```\n\n"
                "設定完成後重新啟動本助手即可使用 AI 視覺分析功能。"
            )
            self.overlay.update_result(warning_msg)

    def trigger_manual_analysis(self):
        """觸發單次快照分析 (預設 Prompt 模式)"""
        if self.worker.is_busy() or self.stt_worker.is_running():
            return

        game_type = self.overlay.combo_game.currentData()
        mode = self.overlay.combo_mode.currentData()

        # 若目前正在 TTS 播報，停止舊播報
        self.tts_worker.stop_speaking()

        success = self.worker.request_analysis(game_type, mode)
        if not success:
            self.overlay.status_footer.setText("狀態: 上次請求尚未完成，跳過過載請求...")

    def trigger_voice_prompt(self):
        """觸發麥克風語音指令提問 (F11)"""
        if self.stt_worker.is_running() or self.worker.is_busy():
            return

        # 停止正在播放的 TTS
        self.tts_worker.stop_speaking()

        self.stt_worker.request_stt()

    def _on_tts_toggled(self, enabled: bool):
        self.tts_enabled = enabled
        if not enabled:
            self.tts_worker.stop_speaking()

    def toggle_polling(self):
        """切換背景自動輪詢"""
        if self.poll_timer.isActive():
            self.poll_timer.stop()
            self.overlay.set_poll_status(False)
        else:
            self.poll_timer.start()
            self.overlay.set_poll_status(True)
            self.trigger_manual_analysis()

    def _on_poll_timer_tick(self):
        if not self.worker.is_busy() and not self.stt_worker.is_running():
            self.trigger_manual_analysis()

    def _on_stt_started(self):
        self.overlay.set_status_listening()

    def _on_stt_finished(self, recognized_text: str):
        self.overlay.reset_voice_button()
        self.overlay.status_footer.setText(f"狀態: 🎤 辨識成功：「{recognized_text}」，正在進行 AI 視覺分析...")

        game_type = self.overlay.combo_game.currentData()
        mode = self.overlay.combo_mode.currentData()

        # 發送 Gemini AI 分析請求 (帶入語音 Prompt)
        self.worker.request_analysis(game_type, mode, custom_prompt=recognized_text)

    def _on_stt_error(self, error_msg: str):
        self.overlay.reset_voice_button()
        self.overlay.update_result(f"⚠️ **語音辨識提醒**：\n\n{error_msg}")

    def _on_analysis_started(self):
        self.overlay.set_status_loading()

    def _on_analysis_finished(self, markdown_text: str, capture_ms: float):
        self.overlay.update_result(markdown_text, capture_ms)
        # 若開啓 TTS 則進行背景語音朗讀
        if self.tts_enabled:
            self.tts_worker.speak_text(markdown_text)

    def _on_analysis_error(self, error_msg: str):
        self.overlay.update_result(error_msg, 0.0)

    def _on_tts_started(self):
        current_txt = self.overlay.status_footer.text()
        self.overlay.status_footer.setText(f"{current_txt} | 🔊 語音朗讀中...")

    def _on_tts_finished(self):
        pass

    def show(self):
        self.overlay.show()

    def stop(self):
        self.poll_timer.stop()
        self.hotkey_listener.stop()
        self.tts_worker.stop_speaking()
        if self.stt_worker.isRunning():
            self.stt_worker.quit()
            self.stt_worker.wait(1000)
        if self.tts_worker.isRunning():
            self.tts_worker.quit()
            self.tts_worker.wait(1000)
        if self.worker.isRunning():
            self.worker.quit()
            self.worker.wait(1000)


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
