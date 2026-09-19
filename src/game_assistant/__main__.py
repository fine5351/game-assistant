"""
允許使用者透過 `python -m game_assistant` 直接啟動應用程式
"""
import sys
from game_assistant.cli import main

if __name__ == "__main__":
    sys.exit(main())
