import sys
import threading
from typing import Optional

from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QPalette, QCursor
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QSlider, QTextBrowser, QFrame,
    QGraphicsDropShadowEffect, QSizePolicy
)
from pynput import keyboard

from config import (
    GameType, AssistCapability, DEFAULT_OPACITY,
    HOTKEY_EMERGENCY_STOP, HOTKEY_TOGGLE_POLL, HOTKEY_MANUAL_TRIGGER, HOTKEY_VOICE_PROMPT,
    TTS_ENABLED
)


class HotkeyListener(QObject):
    """
    全域熱鍵監聽器 (採用 pynput)
    透過 Qt Signal 將熱鍵事件非同步通知 GUI 主執行緒
    支援 F8 (急停), F9 (0.25s 輪詢), F10 (快照分析), F11 (語音指令)
    """
    emergency_stop_signal = pyqtSignal()
    toggle_poll_signal = pyqtSignal()
    manual_trigger_signal = pyqtSignal()
    voice_prompt_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._listener: Optional[keyboard.Listener] = None

    def start(self):
        def on_press(key):
            try:
                if key == keyboard.Key.f8:
                    self.emergency_stop_signal.emit()
                elif key == keyboard.Key.f9:
                    self.toggle_poll_signal.emit()
                elif key == keyboard.Key.f10:
                    self.manual_trigger_signal.emit()
                elif key == keyboard.Key.f11:
                    self.voice_prompt_signal.emit()
            except Exception:
                pass

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        if self._listener:
            self._listener.stop()


class GameAssistantOverlay(QWidget):
    """
    Windows 置頂懸浮面板 (Always-On-Top Overlay)
    通用遊戲 Agent (Jev System 1 + Gemini 3.8 Flash 輔助)
    支援無邊框拖曳、透明度調控、收合/展開、0.25s 決策輪詢與實時操作指導/代替操作
    """
    # 訊號
    game_changed_signal = pyqtSignal(object)
    capability_changed_signal = pyqtSignal(object)
    mode_changed_signal = pyqtSignal(str)
    emergency_stop_signal = pyqtSignal()
    manual_analyze_signal = pyqtSignal()
    toggle_poll_signal = pyqtSignal()
    voice_prompt_signal = pyqtSignal()
    tts_toggle_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()

        self.is_collapsed = False
        self.is_polling = False
        self.tts_enabled = TTS_ENABLED
        self.drag_position = QPoint()
        self._active_display_mode = "guidance"
        self._last_guidance_content = ""
        self._last_analysis_content = ""

        self._init_ui()

    def _init_ui(self):
        # 視窗旗標：置頂、無邊框、Tool視窗
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(440, 620)
        self.setMinimumSize(340, 220)

        # 外層主容器
        self.main_frame = QFrame(self)
        self.main_frame.setObjectName("MainFrame")

        # 陰影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 170))
        shadow.setOffset(0, 4)
        self.main_frame.setGraphicsEffect(shadow)

        # 全域 Layout
        window_layout = QVBoxLayout(self)
        window_layout.setContentsMargins(10, 10, 10, 10)
        window_layout.addWidget(self.main_frame)

        # 內容 Main Layout
        self.content_layout = QVBoxLayout(self.main_frame)
        self.content_layout.setContentsMargins(12, 10, 12, 12)
        self.content_layout.setSpacing(8)

        # --- 1. 標題與拖曳列 ---
        self.header_frame = QFrame()
        self.header_frame.setObjectName("HeaderFrame")
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(6, 4, 6, 4)

        title_label = QLabel("🎮 Jev 通用遊戲 Agent")
        title_label.setFont(QFont("Microsoft JhengHei", 10, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #00E5FF;")

        self.status_badge = QLabel("⏸️ 0.25s 待命 [F9]")
        self.status_badge.setStyleSheet(
            "color: #FFB300; background-color: rgba(255, 179, 0, 0.15); "
            "padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold;"
        )

        self.btn_collapse = QPushButton("─")
        self.btn_collapse.setFixedSize(24, 24)
        self.btn_collapse.setObjectName("HeaderBtn")
        self.btn_collapse.setToolTip("收合/展開面板")
        self.btn_collapse.clicked.connect(self.toggle_collapse)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setObjectName("CloseBtn")
        btn_close.setToolTip("關閉程式")
        btn_close.clicked.connect(QApplication.instance().quit)

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_badge)
        header_layout.addWidget(self.btn_collapse)
        header_layout.addWidget(btn_close)

        self.content_layout.addWidget(self.header_frame)

        # --- 2. 可收合區域 (控制區 + 顯示區) ---
        self.body_container = QWidget()
        body_layout = QVBoxLayout(self.body_container)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)

        # 下拉選單控制列 (遊戲切換 & 輔助能力切換)
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(6)

        self.combo_game = QComboBox()
        for game in GameType:
            self.combo_game.addItem(game.value, game)
        self.combo_game.currentIndexChanged.connect(
            lambda: self.game_changed_signal.emit(self.combo_game.currentData())
        )

        self.combo_capability = QComboBox()
        for cap in AssistCapability:
            self.combo_capability.addItem(cap.value, cap)
        self.combo_capability.currentIndexChanged.connect(
            lambda: self.capability_changed_signal.emit(self.combo_capability.currentData())
        )

        # 保持相容 combo_mode
        self.combo_mode = self.combo_capability

        controls_layout.addWidget(self.combo_game, 3)
        controls_layout.addWidget(self.combo_capability, 3)
        body_layout.addLayout(controls_layout)

        # Jev 決策狀態卡片 (即時顯示 Jev System 1 最新 Choice / 信心 / 螢幕操作)
        self.decision_card = QFrame()
        self.decision_card.setObjectName("DecisionCard")
        card_layout = QHBoxLayout(self.decision_card)
        card_layout.setContentsMargins(8, 6, 8, 6)

        self.lbl_card_icon = QLabel("⚡")
        self.lbl_card_icon.setFont(QFont("Segoe UI Emoji", 14))

        v_card = QVBoxLayout()
        v_card.setSpacing(2)
        self.lbl_card_action = QLabel("決策: 準備中 (待命中)")
        self.lbl_card_action.setStyleSheet("color: #FFFFFF; font-size: 11px; font-weight: bold;")
        self.lbl_card_metrics = QLabel("置信度: --% | 模式: 操作指導 | 執行狀態: 待機")
        self.lbl_card_metrics.setStyleSheet("color: #00E5FF; font-size: 10px;")
        v_card.addWidget(self.lbl_card_action)
        v_card.addWidget(self.lbl_card_metrics)

        card_layout.addWidget(self.lbl_card_icon)
        card_layout.addLayout(v_card)
        card_layout.addStretch()

        body_layout.addWidget(self.decision_card)

        # 按鈕列 (控制：0.25s 輪詢 / 快照分析 / F8 急停 / 語音提問 / 朗讀開關)
        bar_layout = QVBoxLayout()
        bar_layout.setSpacing(6)

        bar_row1 = QHBoxLayout()
        bar_row1.setSpacing(6)

        self.btn_toggle_poll = QPushButton("⚡ 0.25s 決策輪詢 (F9)")
        self.btn_toggle_poll.setObjectName("ActionBtn")
        self.btn_toggle_poll.clicked.connect(lambda: self.toggle_poll_signal.emit())

        self.btn_manual = QPushButton("📸 快照分析 (F10)")
        self.btn_manual.setObjectName("PrimaryBtn")
        self.btn_manual.clicked.connect(lambda: self.manual_analyze_signal.emit())

        self.btn_emergency = QPushButton("🛑 急停 (F8)")
        self.btn_emergency.setObjectName("EmergencyBtn")
        self.btn_emergency.setToolTip("緊急停止代替操作 (F8)")
        self.btn_emergency.clicked.connect(lambda: self.emergency_stop_signal.emit())

        bar_row1.addWidget(self.btn_toggle_poll, 3)
        bar_row1.addWidget(self.btn_manual, 2)
        bar_row1.addWidget(self.btn_emergency, 2)

        bar_row2 = QHBoxLayout()
        bar_row2.setSpacing(6)

        self.btn_voice_prompt = QPushButton("🎤 語音發問 (F11)")
        self.btn_voice_prompt.setObjectName("VoiceBtn")
        self.btn_voice_prompt.setToolTip("按下 F11 或點擊進行麥克風語音提問 (由 Gemini 處理需求再由 Jev 執行)")
        self.btn_voice_prompt.clicked.connect(lambda: self.voice_prompt_signal.emit())

        self.btn_tts_toggle = QPushButton("🔊 朗讀: ON")
        self.btn_tts_toggle.setObjectName("TTSBtn")
        self.btn_tts_toggle.setToolTip("切換 AI 分析結果是否自動語音朗讀")
        self.btn_tts_toggle.clicked.connect(self._on_toggle_tts_clicked)

        bar_row2.addWidget(self.btn_voice_prompt, 3)
        bar_row2.addWidget(self.btn_tts_toggle, 2)

        bar_layout.addLayout(bar_row1)
        bar_layout.addLayout(bar_row2)
        body_layout.addLayout(bar_layout)

        # 透明度滑桿列
        opacity_layout = QHBoxLayout()
        opacity_label = QLabel("透明度:")
        opacity_label.setStyleSheet("color: #AAAAAA; font-size: 11px;")

        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(20, 100)
        self.slider_opacity.setValue(int(DEFAULT_OPACITY * 100))
        self.slider_opacity.valueChanged.connect(self._change_opacity)

        self.lbl_opacity_val = QLabel(f"{int(DEFAULT_OPACITY * 100)}%")
        self.lbl_opacity_val.setStyleSheet("color: #00E5FF; font-size: 11px; font-weight: bold;")

        opacity_layout.addWidget(opacity_label)
        opacity_layout.addWidget(self.slider_opacity)
        opacity_layout.addWidget(self.lbl_opacity_val)
        body_layout.addLayout(opacity_layout)

        # --- 3. Markdown 分析結果展示區 ---
        self.output_browser = QTextBrowser()
        self.output_browser.setObjectName("OutputBrowser")
        self.output_browser.setOpenExternalLinks(True)
        self.output_browser.setHtml(
            "<div style='color: #888888; text-align: center; margin-top: 25px;'>"
            "🚀 <b>Jev 通用遊戲 Agent 已就緒</b><br><br>"
            "核心決策：<b>TypeSafe Jev (System 1)</b><br>"
            "輔助認知：<b>Gemini 3.8 Flash (System 2)</b><br><br>"
            "按下 <b style='color:#00E5FF;'>F9</b> 啟動每 0.25 秒高頻實時決策<br>"
            "按下 <b style='color:#FFB300;'>F10</b> 手動快照分析<br>"
            "按下 <b style='color:#E040FB;'>F11</b> 麥克風語音發問<br>"
            "按下 <b style='color:#FF5252;'>F8</b> 緊急停止代替操作"
            "</div>"
        )
        body_layout.addWidget(self.output_browser)

        # 狀態頁腳
        self.status_footer = QLabel("狀態: 就緒 | 輪詢間隔: 0.25s (4 Hz) | 延遲: -- ms")
        self.status_footer.setStyleSheet("color: #777777; font-size: 10px;")
        body_layout.addWidget(self.status_footer)

        self.content_layout.addWidget(self.body_container)

        # 套用初始 TTS UI 與 QSS 樣式表
        self.update_tts_button_ui(self.tts_enabled)
        self.set_window_opacity(DEFAULT_OPACITY)
        self._apply_stylesheet()

    def _on_toggle_tts_clicked(self):
        self.tts_enabled = not self.tts_enabled
        self.update_tts_button_ui(self.tts_enabled)
        self.tts_toggle_signal.emit(self.tts_enabled)

    def update_tts_button_ui(self, enabled: bool):
        self.tts_enabled = enabled
        if enabled:
            self.btn_tts_toggle.setText("🔊 朗讀: ON")
            self.btn_tts_toggle.setStyleSheet(
                "QPushButton { background-color: rgba(0, 229, 255, 0.15); color: #00E5FF; "
                "border: 1px solid #00E5FF; border-radius: 6px; padding: 6px; font-size: 11px; font-weight: bold; }"
                "QPushButton:hover { background-color: rgba(0, 229, 255, 0.3); }"
            )
        else:
            self.btn_tts_toggle.setText("🔇 朗讀: OFF")
            self.btn_tts_toggle.setStyleSheet(
                "QPushButton { background-color: rgba(255, 255, 255, 0.05); color: #888888; "
                "border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 6px; padding: 6px; font-size: 11px; }"
                "QPushButton:hover { background-color: rgba(255, 255, 255, 0.12); color: #CCCCCC; }"
            )

    def set_status_listening(self):
        """切換為 🎤 聆聽中... 狀態"""
        self.btn_voice_prompt.setText("🎤 聆聽中...")
        self.btn_voice_prompt.setEnabled(False)
        self.status_footer.setText("狀態: 🎤 聆聽中... 請開口提出需求 (由 Gemini 轉為戰術意圖)")

    def set_status_recognizing(self):
        """切換為 語音辨識中... 狀態"""
        self.btn_voice_prompt.setText("⏳ 辨識中...")
        self.status_footer.setText("狀態: 🧠 語音辨識中...")

    def reset_voice_button(self):
        """復原語音按鈕狀態"""
        self.btn_voice_prompt.setText("🎤 語音發問 (F11)")
        self.btn_voice_prompt.setEnabled(True)

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            #MainFrame {
                background-color: rgba(18, 22, 32, 0.94);
                border: 1px solid rgba(0, 229, 255, 0.35);
                border-radius: 12px;
            }
            #HeaderFrame {
                background-color: rgba(255, 255, 255, 0.04);
                border-radius: 8px;
            }
            #DecisionCard {
                background-color: rgba(0, 229, 255, 0.08);
                border: 1px solid rgba(0, 229, 255, 0.25);
                border-radius: 8px;
            }
            #HeaderBtn {
                background: transparent;
                color: #CCCCCC;
                border: none;
                font-size: 14px;
                border-radius: 4px;
            }
            #HeaderBtn:hover {
                background-color: rgba(255, 255, 255, 0.15);
                color: #FFFFFF;
            }
            #CloseBtn {
                background: transparent;
                color: #FF5252;
                border: none;
                font-size: 14px;
                border-radius: 4px;
            }
            #CloseBtn:hover {
                background-color: #FF5252;
                color: #FFFFFF;
            }
            QComboBox {
                background-color: rgba(30, 38, 54, 0.85);
                color: #E0E0E0;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QComboBox:hover {
                border-color: #00E5FF;
            }
            QComboBox QAbstractItemView {
                background-color: #161B26;
                color: #E0E0E0;
                selection-background-color: #00E5FF;
                selection-color: #000000;
            }
            QPushButton#PrimaryBtn {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00B0FF, stop:1 #00E5FF);
                color: #000000;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 6px;
                font-size: 11px;
            }
            QPushButton#PrimaryBtn:hover {
                background-color: #40C4FF;
            }
            QPushButton#EmergencyBtn {
                background-color: rgba(255, 82, 82, 0.25);
                color: #FF5252;
                border: 1px solid #FF5252;
                font-weight: bold;
                border-radius: 6px;
                padding: 6px;
                font-size: 11px;
            }
            QPushButton#EmergencyBtn:hover {
                background-color: rgba(255, 82, 82, 0.5);
                color: #FFFFFF;
            }
            QPushButton#ActionBtn {
                background-color: rgba(255, 255, 255, 0.08);
                color: #E0E0E0;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 6px;
                font-size: 11px;
            }
            QPushButton#ActionBtn:hover {
                background-color: rgba(255, 255, 255, 0.15);
                border-color: #00E5FF;
            }
            QPushButton#VoiceBtn {
                background-color: rgba(156, 39, 176, 0.25);
                color: #E040FB;
                border: 1px solid #E040FB;
                border-radius: 6px;
                padding: 6px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#VoiceBtn:hover {
                background-color: rgba(224, 64, 251, 0.4);
                color: #FFFFFF;
            }
            QPushButton#VoiceBtn:disabled {
                background-color: rgba(100, 100, 100, 0.2);
                color: #777777;
                border-color: #555555;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: rgba(255, 255, 255, 0.2);
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #00E5FF;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 12px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 6px;
            }
            #OutputBrowser {
                background-color: rgba(10, 14, 22, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                color: #E2E8F0;
                padding: 8px;
                font-size: 12px;
                line-height: 1.5;
            }
        """)

    def _change_opacity(self, value: int):
        opacity = value / 100.0
        self.set_window_opacity(opacity)
        self.lbl_opacity_val.setText(f"{value}%")

    def set_window_opacity(self, opacity: float):
        self.setWindowOpacity(opacity)

    def toggle_collapse(self):
        """控制視窗收合與展開"""
        self.is_collapsed = not self.is_collapsed
        if self.is_collapsed:
            self.body_container.hide()
            self.btn_collapse.setText("□")
            self.resize(400, 60)
        else:
            self.body_container.show()
            self.btn_collapse.setText("─")
            self.resize(440, 600)

    def set_poll_status(self, active: bool):
        """更新 0.25s 輪詢狀態標籤"""
        self.is_polling = active
        if active:
            self.status_badge.setText("⚡ 0.25s 決策中 [F9]")
            self.status_badge.setStyleSheet(
                "color: #00E5FF; background-color: rgba(0, 229, 255, 0.2); "
                "padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold;"
            )
            self.btn_toggle_poll.setText("⏸️ 暫停輪詢 (F9)")
        else:
            self.status_badge.setText("⏸️ 待命 [F9]")
            self.status_badge.setStyleSheet(
                "color: #FFB300; background-color: rgba(255, 179, 0, 0.15); "
                "padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold;"
            )
            self.btn_toggle_poll.setText("⚡ 0.25s 決策輪詢 (F9)")

    def update_decision_hud(self, decision, capture_ms: float = 0.0):
        """更新 Jev System 1 實時決策 HUD 與 Markdown 指引 (防抖防重繪優化)"""
        act = decision.primary_action
        conf = int(decision.confidence * 100)
        cap = self.combo_capability.currentData()
        cap_name = cap.value if hasattr(cap, "value") else str(cap)

        exec_status = "未執行"
        if decision.action_result:
            exec_status = f"已發送 [{decision.action_result.target_key_or_button}]" if decision.action_result.executed else "冷卻中"
        elif cap == AssistCapability.GUIDANCE:
            exec_status = "指導中"

        self.lbl_card_action.setText(f"⚡ Jev 決策: 【{act}】 (閃避判定: {decision.should_evade})")
        self.lbl_card_metrics.setText(f"置信度: {conf}% | 延遲: {capture_ms:.1f}ms | 模式: {cap_name} | 操作: {exec_status}")
        self.status_footer.setText(f"狀態: ⚡ 0.25s 實時決策中 | Jev 決策: {act} | 擷取: {capture_ms:.1f} ms")

        # 僅在指導/操作模式且指引內容確實變更時更新輸出區，徹底消除 4 Hz 滾動條重設與閃爍
        if self._active_display_mode == "guidance":
            content = f"### ⚡ Jev 即時戰術指引\n\n{decision.guidance_text}\n\n"
            if decision.action_result and decision.action_result.message:
                content += f"> 🎮 **螢幕操作記錄**：`{decision.action_result.message}` (耗時: {decision.action_result.latency_ms:.1f}ms)\n\n"
            content += f"---\n*0.25s 實時畫面流 (4 Hz) | Jev 延遲: {decision.raw_jev.latency_ms:.1f} ms | 畫面擷取: {capture_ms:.1f} ms*"

            if content != self._last_guidance_content:
                self.output_browser.setMarkdown(content)
                self._last_guidance_content = content

    def update_data_analysis_hud(self, report_markdown: str, decision, capture_ms: float = 0.0):
        """資料分析模式 HUD 與即時遙測報告更新"""
        act = decision.primary_action
        conf = int(decision.confidence * 100)
        self.lbl_card_action.setText(f"📊 遙測採集中: 決策【{act}】")
        self.lbl_card_metrics.setText(f"置信度: {conf}% | 模式: 資料分析 | 延遲: {capture_ms:.1f}ms")
        self.status_footer.setText(f"狀態: 📊 實時資料分析中 | 擷取: {capture_ms:.1f} ms")

        if self._active_display_mode == "analysis":
            if report_markdown != self._last_analysis_content:
                self.output_browser.setMarkdown(report_markdown)
                self._last_analysis_content = report_markdown

    def show_deep_analysis(self, markdown_text: str, capture_ms: float = 0.0):
        """展示 Gemini 3.8 Flash 深度多模態快照分析 (鎖定顯示避免被 0.25s 輪詢洗掉)"""
        self._active_display_mode = "deep_vision"
        self.output_browser.setMarkdown(markdown_text)
        self.status_footer.setText(f"狀態: 📸 深度視覺分析完成 | 耗時: {capture_ms:.1f} ms")

    def show_intent_result(self, markdown_text: str):
        """展示玩家需求意圖拆解結果 (鎖定顯示)"""
        self._active_display_mode = "intent"
        self.output_browser.setMarkdown(markdown_text)

    def show_data_analysis(self, report_markdown: str):
        """切換並展示實時戰況資料分析報告"""
        self._active_display_mode = "analysis"
        self._last_analysis_content = report_markdown
        self.output_browser.setMarkdown(report_markdown)

    def set_guidance_display_mode(self):
        """切回實時戰術指引展示模式"""
        self._active_display_mode = "guidance"
        self._last_guidance_content = ""

    def update_result(self, markdown_text: str, capture_ms: float = 0.0):
        """更新 Markdown 文字與狀態 (相容舊呼叫)"""
        self.output_browser.setMarkdown(markdown_text)
        self.status_footer.setText(f"狀態: 更新完成 | 耗時: {capture_ms:.1f} ms")

    def set_status_loading(self):
        """切換為分析中狀態"""
        self.status_footer.setText("狀態: 🧠 Gemini 3.8 輔助認知分析中...")

    # --- 無邊框拖曳視窗支援 ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GameAssistantOverlay()
    window.show()
    sys.exit(app.exec())
