"""
Test suite package for game-assistant.
確保在未安裝套件環境下執行 pytest 或 unittest 時自動將 src/ 加入 sys.path。
"""
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
