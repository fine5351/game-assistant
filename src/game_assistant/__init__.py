"""
Game Assistant - Windows 即時遊戲視覺與語音輔助助手
基於 TypeSafe AI Jev (System 1) 與 Google Gemini 3.8 Flash (System 2)
"""

from game_assistant.core.config import (
    GameType,
    AssistCapability,
    AnalysisMode,
    MODEL_NAME,
    JEV_MODEL_NAME,
    DEFAULT_POLL_INTERVAL,
    POLL_INTERVAL,
    HOTKEY_EMERGENCY_STOP,
    HOTKEY_TOGGLE_POLL,
    HOTKEY_MANUAL_TRIGGER,
    HOTKEY_VOICE_PROMPT,
)
from game_assistant.core.agent import UniversalGameAgent
from game_assistant.engines.jev_engine import (
    JevDecisionEngine,
    JevResponse,
    Choice,
    Noul,
    Score,
    ChoiceResult,
    NoulResult,
    ScoreResult,
)
from game_assistant.engines.ai_engine import GeminiAuxiliaryEngine
from game_assistant.utils.screen_capture import ScreenCapturer
from game_assistant.utils.input_actuator import ScreenActuator
from game_assistant.audio.tts_engine import TTSEngine, clean_markdown_for_tts
from game_assistant.audio.stt_engine import STTEngine
from game_assistant import core
from game_assistant import engines
from game_assistant import audio
from game_assistant import utils
from game_assistant import ui
from game_assistant import strategies

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "core",
    "engines",
    "audio",
    "utils",
    "ui",
    "strategies",
    "UniversalGameAgent",
    "GameType",
    "AssistCapability",
    "AnalysisMode",
    "MODEL_NAME",
    "JEV_MODEL_NAME",
    "DEFAULT_POLL_INTERVAL",
    "POLL_INTERVAL",
    "HOTKEY_EMERGENCY_STOP",
    "HOTKEY_TOGGLE_POLL",
    "HOTKEY_MANUAL_TRIGGER",
    "HOTKEY_VOICE_PROMPT",
    "JevDecisionEngine",
    "JevResponse",
    "Choice",
    "Noul",
    "Score",
    "ChoiceResult",
    "NoulResult",
    "ScoreResult",
    "GeminiAuxiliaryEngine",
    "ScreenCapturer",
    "ScreenActuator",
    "TTSEngine",
    "clean_markdown_for_tts",
    "STTEngine",
]
