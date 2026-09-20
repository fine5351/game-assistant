"""
Game Assistant 命令行與 Console Script 進入點 (console_scripts entrypoint)
支援直接啟動 PyQt6 桌面置頂輔助面板與命令行參數解析
"""
import os
import sys
import argparse
from PyQt6.QtCore import QLoggingCategory
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication
from game_assistant import __version__
from game_assistant.app import GameAssistantController

# 壓制 Windows DirectWrite 對舊版點陣字型 (如 MS Sans Serif) 拋出的無害載入警告
QLoggingCategory.setFilterRules("qt.qpa.fonts.warning=false")
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts.warning=false")


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

    # 明確配置全域現代 TrueType/OpenType 向量字型，徹底杜絕 DirectWrite 回退至 MS Sans Serif 點陣字型
    global_font = QFont("Microsoft JhengHei UI", 9)
    global_font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(global_font)

    controller = GameAssistantController()
    controller.show()

    def cleanup():
        controller.stop()

    app.aboutToQuit.connect(cleanup)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
