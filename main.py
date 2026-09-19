#!/usr/bin/env python3
"""
Game Assistant 啟動入口 (相容性啟動器)
支援直接以 `python main.py` 執行，同時相容現代 src/ layout 與 console_scripts。
"""
import sys
from pathlib import Path

# 將 src 目錄注入 sys.path，確保未經 pip 安裝時亦能直接運行
_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from game_assistant.cli import main
from game_assistant.app import (
    GameAssistantController,
    JevLoopWorker,
    GeminiIntentWorker,
    DeepVisionWorker,
    STTWorker,
    TTSWorker,
    ScreenTranslationWorker,
    VoiceTranslationWorker,
)

__all__ = [
    "main",
    "GameAssistantController",
    "JevLoopWorker",
    "GeminiIntentWorker",
    "DeepVisionWorker",
    "STTWorker",
    "TTSWorker",
    "ScreenTranslationWorker",
    "VoiceTranslationWorker",
]

if __name__ == "__main__":
    sys.exit(main())
