# Jev 通用遊戲 Agent 升級實作任務列表 (task.md)

## 第一階段：核心模型與設定重構
- [x] 任務 1: 研究 TypeSafe AI 新發布之 Jev (System 1) 基礎決策模型特性與即時遊戲輔助實現路徑 (Dual-System 架構)
- [x] 任務 2: 升級 `config.py`，配置 Jev 相關參數 (`TYPESAFE_API_KEY`, `JEV_MODEL_NAME`, `JEV_API_URL`)、將 Gemini 升級至 `gemini-3.8-flash`、固定每 0.25 秒畫面決策輪詢 (`DEFAULT_POLL_INTERVAL = 0.25`)、配置 `AssistCapability` 與 `F8` 急停熱鍵
- [x] 任務 3: 實作 `jev_engine.py`，提供 Jev System 1 決策引擎 (支援 Choice, Noul, Score 結構化決策、官方 SDK、REST API 與本地啟發式決策器三重降級)
- [x] 任務 4: 實作 `input_actuator.py`，封裝 `ScreenActuator` 支援實體鍵盤與滑鼠模擬、F8 安全熔斷急停與操作冷卻防洪

## 第二階段：策略模式重構 (Strategy Pattern)
- [x] 任務 5: 建立 `strategies/base.py`，定義 `BaseGameStrategy` 抽象類別、`TelemetryData`、`StrategyDecision` 與 `ActionResult`
- [x] 任務 6: 實作 `strategies/genshin.py`，建立《原神》策略 (元素反應鏈、四人循環切人 E/Q/A、無敵幀閃避)
- [x] 任務 7: 實作 `strategies/star_rail.py`，建立《崩壞：星穹鐵道》策略 (戰技點 SP 配額、1-4 終結技插隊破韌)
- [x] 任務 8: 實作 `strategies/zzz.py`，建立《絕區零》策略 (黃光招架 Space/C、紅光閃避 Shift、失衡連攜技 QTE)
- [x] 任務 9: 實作 `strategies/general.py`，建立《泛用遊戲》策略 (通用 WASD、滑鼠操作與技能)
- [x] 任務 10: 實作 `strategies/registry.py`，建立 `StrategyRegistry` 支援動態註冊與未來任意新遊戲的無縫擴充
- [x] 任務 11: 建立 `strategies/__init__.py` 統一匯出

## 第三階段：通用遊戲 Agent 與雙系統認知整合
- [x] 任務 12: 重構 `ai_engine.py` 為 `GeminiAuxiliaryEngine`，擔當 System 2 輔助認知層，優先處理玩家需求意圖拆解 (`decompose_user_demand`) 與深度視覺分析
- [x] 任務 13: 實作 `agent.py`，建立 `UniversalGameAgent` 整合感知 (ScreenCapturer)、認知 (Gemini 3.8 Flash)、決策 (Jev System 1)、策略 (Strategy Pattern) 與致動 (ScreenActuator)
- [x] 任務 14: 升級 `gui.py`，呈現 Jev System 1 實時決策 HUD 卡片、0.25 秒高頻決策控制、輔助能力切換 (操作指導/代替操作/資料分析) 與 F8 急停按鈕
- [x] 任務 15: 重構 `main.py`，建立 0.25s `JevLoopWorker`、非同步 `GeminiIntentWorker`、`DeepVisionWorker`，實現 4 Hz 高頻決策與無阻塞 UI
- [x] 任務 16: 強化 `screen_capture.py`，增加 BitBlt 異常防禦與安全降級畫面，杜絕無授權會話下崩潰

## 第四階段：驗證、審查修正與說明文件
- [x] 任務 17: 實作 `test_universal_agent.py`，撰寫 32 個覆蓋 Jev、Gemini、各遊戲策略、動態擴充、代替操作、急停鍵位釋放、冷卻防洪、資料分析與邊界情境的自動化單元測試，全部驗證通過
- [x] 任務 18: 審查修正與防禦強化：
  - 修正 F8 急停開關 (Killswitch) 真實按鍵與滑鼠釋放邏輯，杜絕按鍵卡死在 Windows 系統
  - 修正致動器冷卻時間多執行緒競態條件 (Race Condition)
  - 修正 GUI 面板在 0.25 秒高頻下 setMarkdown 重繪閃爍與滾動條頻繁重設問題，支援深度分析與語音解析鎖定展示
  - 完整串接 `DATA_ANALYSIS` 輔助能力至 0.25 秒實時迴圈與所有策略遙測問題
  - 強化 Gemini 意圖拆解 Worker，於呼叫前擷取即時螢幕畫面注入視覺上下文
  - 強化語音需求處理流程，於 Gemini 完成意圖拆解後立即自動接入 Jev 觸發決策
  - 修正 `TTSEngine.stop()` 支援即時中止語音播報
  - 強化 `Choice`、`Noul`、`Score` 同時完整相容 TypeSafe 官方 SDK 與 REST API Schema
- [x] 任務 19: 執行全專案 17 個 Python 模組 `python -m py_compile` 語法編譯檢查零錯誤
- [x] 任務 20: 更新 `requirements.txt` 加入 `typesafe-sdk>=0.1.0`
- [x] 任務 21: 更新 `README.md`，提供完整架構說明、0.25s 實時操作指南與全域熱鍵說明

## 第五階段：專案目錄結構 Package 化重構 (Package Modularization)
- [x] 任務 22: 建立 `core/`、`engines/`、`ui/`、`audio/`、`utils/`、`tests/` 套件目錄與 `__init__.py`
- [x] 任務 23: 透過 `git mv` 遷移根目錄平鋪之模組至各職責套件：
  - `agent.py`, `config.py` -> `core/`
  - `jev_engine.py`, `ai_engine.py` -> `engines/`
  - `gui.py` -> `ui/`
  - `tts_engine.py`, `stt_engine.py` -> `audio/`
  - `screen_capture.py`, `input_actuator.py` -> `utils/`
  - `test_universal_agent.py` -> `tests/`
- [x] 任務 24: 更新全專案跨模組 import 引用（包含 `main.py`、`tests/`、`strategies/`、各子套件），並加入模組獨立執行路徑備援
- [x] 任務 25: 執行完整 32 項單元測試、模組語法檢查與各子模組獨立執行驗證，確認 100% 通過
- [x] 任務 26: 同步更新 `README.md` 與 `AGENTS.md` 之架構說明與驗證指令清單

## 第六階段：現代 Python 最佳實踐結構重構 (Modern Python Best Practice & `src/` Layout)
- [x] 任務 27: 建立標準 `src/` layout 結構 (`src/game_assistant/`) 並透過 `git mv` 將子套件遷移至主要套件命名空間：
  - `src/game_assistant/core/`
  - `src/game_assistant/engines/`
  - `src/game_assistant/ui/`
  - `src/game_assistant/audio/`
  - `src/game_assistant/utils/`
  - `src/game_assistant/strategies/`
- [x] 任務 28: 建立 `src/game_assistant/__init__.py`，定義套件版本號 (`0.2.0`) 並統一匯出核心 API 與子模組
- [x] 任務 29: 實作 `src/game_assistant/app.py`，完整封裝 `GameAssistantController` 與 5 組非同步 `QThread` Worker 執行緒群
- [x] 任務 30: 建立 `src/game_assistant/cli.py` 提供 `main()` 進入點，並建立 `src/game_assistant/__main__.py` 支援 `python -m game_assistant` 啟動
- [x] 任務 31: 配置現代化 `pyproject.toml`，遵循 PEP 517/518/621 標準，配置相依套件、`setuptools` `src` layout 套件發現與 `game-assistant` console_scripts 進入點
- [x] 任務 32: 重構根目錄 `main.py` 為輕量相容性啟動器，注入 `src/` 至 `sys.path` 並轉發調用 `game_assistant.cli:main`，確保直接執行 `python main.py` 100% 相容
- [x] 任務 33: 全面更新全專案所有模組 import 引用為 `game_assistant.*` 標準絕對路徑引用，並保留各子模組獨立執行路徑備援防護
- [x] 任務 34: 更新 `tests/` 單元測試套件路徑與匯出介面測試，擴充至 42 個測試案例（新增套件元資料、CLI 進入點、Controller 匯出等），全部 100% 通過
- [x] 任務 35: 驗證 `pip install -e .` 可編輯安裝成功，產生 `game-assistant.exe` console_scripts 執行檔並測試各子模組獨立執行皆正常
- [x] 任務 36: 同步更新 `README.md` 與 `AGENTS.md` 架構圖、安裝模式與指令說明

## 第七階段：審查修正、強健性強化與最佳實踐深度驗證 (Review Fixes & Deep Robustness)
- [x] 任務 37: 修正 `StrategyRegistry.get()` 比對自訂字串 key 時的 `AttributeError`，並在測試中增加 `finally` 恢復註冊中心預設狀態，徹底修復 `pytest` 下測試失敗問題
- [x] 任務 38: 修正 `pyproject.toml` 與 `requirements.txt` 中 `pywin32` 依賴缺少 PEP 508 環境標記問題（加入 `; sys_platform == 'win32'`），確保跨平台打包與安裝相容性
- [x] 任務 39: 為 `src/game_assistant/cli.py` 整合標準 `argparse`，支援 `-v/--version` 與 `-h/--help` 命令行標準輸出與優雅退出，避免命令行參數錯誤啟動 GUI
- [x] 任務 40: 消除 7 個內部套件模組中全域侵入性 `sys.path.insert(0, ...)`，加入 `if __name__ == "__main__" and not __package__:` 防護，維護標準函式庫隔離性
- [x] 任務 41: 全面強化策略模式與 Gemini 引擎中對 `capability` 為字串或枚舉時的相容處理 (`getattr(capability, "value", str(capability))`)
- [x] 任務 42: 擴充單元測試至 44 項，涵蓋 CLI argparse、`pyproject.toml` PEP 621 設定與未知遊戲降級機制，`pytest` 與 `unittest` 雙測試套件 100% 通過

