"""
Game Assistant 命令行與 Console Script 進入點 (console_scripts entrypoint)
支援直接啟動 PyQt6 桌面置頂輔助面板與命令行參數解析
"""
import sys
import argparse
from PyQt6.QtWidgets import QApplication
from game_assistant import __version__
from game_assistant.app import GameAssistantController


def build_parser() -> argparse.ArgumentParser:
    """構建命令行參數解析器"""
    parser = argparse.ArgumentParser(
        prog="game-assistant",
        description="Windows 即時遊戲視覺與語音輔助助手 (Dual-System Jev + Gemini 3.8 Flash)",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="顯示套件版本號並結束",
    )
    return parser


def main(argv=None) -> int:
    """
    主要應用程式執行入口
    """
    if argv is None:
        argv = sys.argv

    parser = build_parser()
    args, qt_args = parser.parse_known_args(argv[1:])

    app = QApplication.instance()
    if app is None:
        app = QApplication([argv[0]] + qt_args)
    app.setQuitOnLastWindowClosed(True)

    controller = GameAssistantController()
    controller.show()

    def cleanup():
        controller.stop()

    app.aboutToQuit.connect(cleanup)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
