# 專案代理規則與工程指引 (AGENTS.md)

本文件定義 AI Agent 在此專案庫 (`game-assistant`) 進行開發、維護、除錯與協同作業時所必須嚴格遵守的架構規範、工程原則與工作流程。

---

## 1. 專案概觀與技術架構 (Project Architecture)

### 1.1 專案定位
本專案為基於 **TypeSafe AI Jev (System 1)** 與 **Google Gemini 3.8 Flash (System 2)** 的 Windows 桌面即時遊戲視覺與語音輔助助手。專為米哈遊系列遊戲（《原神》、《崩壞：星穹鐵道》、《絕區零》）及泛用遊戲模式提供低延遲即時戰況分析、角色養成與裝備評估以及地圖解謎通關指引，並完整整合雙向語音互動功能（STT 語音發問 + TTS 離線朗讀）。

### 1.2 核心技術棧 (Tech Stack)
- **語言環境**：Python 3.10+
- **核心 AI**：`typesafe-sdk` (Jev System 1) + `google-genai` SDK (`gemini-3.8-flash` System 2)
- **圖形介面**：PyQt6（置頂透明懸浮面板、無邊框滑鼠拖曳、Markdown 即時渲染）
- **視覺擷取**：`mss` 硬體加速螢幕快照 + `Pillow` 雙線性縮放預處理
- **全域熱鍵**：`pynput` 背景熱鍵監聽（F9 輪詢切換 / F10 快照分析 / F11 語音發問）
- **離線語音朗讀 (TTS)**：`pyttsx3` (Windows SAPI5) + Markdown 語法符號過濾 + COM 執行緒安全防護
- **語音指令辨識 (STT)**：`SpeechRecognition` + `PyAudio`（麥克風環境噪音自動校正、繁中辨識）
- **環境設定**：`python-dotenv` 載入設定

### 1.3 核心模組與 Package 職責劃分 (Package & Module Responsibilities)
- `main.py`：專案根目錄相容啟動器。自動注入 `src/` 至 `sys.path`，並調用 `game_assistant.cli:main`。
- `pyproject.toml`：遵循 PEP 517/518/621 標準之現代化專案建置、相依套件與 `game-assistant` console_scripts 進入點配置。
- `src/game_assistant/`：主要套件命名空間（Python Standard `src/` Layout）。
  - `src/game_assistant/__init__.py`：套件版本號 (`0.2.0`) 與核心 API 統一匯出。
  - `src/game_assistant/__main__.py`：支援 `python -m game_assistant` 執行。
  - `src/game_assistant/cli.py`：CLI 與 console_scripts 進入點函式 `main()`。
  - `src/game_assistant/app.py`：`GameAssistantController` 與背景 Worker 執行緒群 (`JevLoopWorker`, `GeminiIntentWorker`, `DeepVisionWorker`, `STTWorker`, `TTSWorker`)。
  - `src/game_assistant/core/`：核心 Agent 協調器與系統組態。
    - `src/game_assistant/core/agent.py`：`UniversalGameAgent` 整合感知、認知、決策、策略與致動。
    - `src/game_assistant/core/config.py`：系統組態、熱鍵設定、能力列舉、TTS/STT 參數設定與 Prompt 範本庫 (`PROMPTS`)。
  - `src/game_assistant/engines/`：決策與輔助認知 AI 引擎層。
    - `src/game_assistant/engines/jev_engine.py`：封裝 `JevDecisionEngine` (Choice / Noul / Score，支援 SDK、REST API 與確定性本地啟發降級)。
    - `src/game_assistant/engines/ai_engine.py`：封裝 `GeminiAuxiliaryEngine` (Gemini 3.8 Flash)，支援意圖拆解與深度多模態視覺剖析。
  - `src/game_assistant/ui/`：使用者介面與熱鍵監聽。
    - `src/game_assistant/ui/gui.py`：PyQt6 置頂懸浮視窗介面 (`GameAssistantOverlay`) 與全域熱鍵訊號橋接器 (`HotkeyListener`)。
  - `src/game_assistant/audio/`：語音處理模組。
    - `src/game_assistant/audio/tts_engine.py`：`TTSEngine` 與 `clean_markdown_for_tts` (Windows SAPI5 語音合成、Markdown 符號清理、COM 執行緒管理)。
    - `src/game_assistant/audio/stt_engine.py`：`STTEngine` (麥克風收音、環境噪音自動校準與繁中辨識)。
  - `src/game_assistant/utils/`：畫面擷取與輸入致動周邊工具。
    - `src/game_assistant/utils/screen_capture.py`：封裝 `mss` 與 `Pillow`，提供超低延遲（< 50ms）螢幕快照擷取與縮放，具備 BitBlt 異常安全防禦降級。
    - `src/game_assistant/utils/input_actuator.py`：封裝 `ScreenActuator`，支援實體鍵盤與滑鼠操作模擬、F8 安全熔斷急停與冷卻防洪。
  - `src/game_assistant/strategies/`：遊戲策略模式庫 (`BaseGameStrategy`, `GenshinStrategy`, `StarRailStrategy`, `ZZZStrategy`, `GeneralGameStrategy`, `StrategyRegistry`)。
- `tests/`：單元與整合測試套件 (`tests/test_universal_agent.py`)，獨立於 `src/` 外。

---

## 2. 核心工程準則 (Karpathy Guidelines)

所有在此專案進行的變更必須落實以下四大核心工程原則：

1. **動手前先思考 (Think Before Coding)**：
   - 實作前明確理解現有架構與資料流向。若需求不明確或存在架構疑慮，主動提問確認，不盲目臆測。
2. **簡潔至上 (Simplicity First & YAGNI)**：
   - 僅撰寫滿足當前需求的最精簡程式碼。嚴禁過度設計、過度抽象化或加入未經要求的推測性功能。
3. **精準修改 (Surgical Changes)**：
   - 異動範圍嚴格限制於任務目標檔案與函式。嚴禁隨意重構、重新格式化或變動無關程式碼，維持最小乾淨 diff。
4. **目標導向執行 (Goal-Driven Execution)**：
   - 每一項修改均需設定可客觀檢驗的成功標準（例如語法編譯檢查、特定例外捕捉驗證、執行緒生命週期測試）。

---

## 3. 多執行緒與並行安全性規範 (Concurrency & Threading Rules)

本專案高度依賴 PyQt6 事件循環與多執行緒並行運作，任何程式碼變更必須恪守以下安全性規則：

1. **UI 主執行緒嚴禁阻塞 (Non-Blocking UI)**：
   - 螢幕擷取、網路 API 呼叫、語音錄音與音訊播放等 I/O 密集或耗時操作，**嚴禁在 UI 主執行緒中直接執行**。
   - 所有耗時操作一律透過 `QThread` 背景執行緒執行，並使用 PyQt 信號（`pyqtSignal`）與槽（Slot）機制通知 UI 更新。
2. **Windows COM 執行緒安全 (COM Threading Safety)**：
   - 於 `QThread` 內調用 Windows SAPI5 (`pyttsx3`) 或相關 COM 組件前，必須在該執行緒執行 `pythoncom.CoInitialize()`，並在 `finally` 區塊中執行 `pythoncom.CoUninitialize()`，杜絕 `RPC_E_WRONG_THREAD` 執行階段崩潰。
3. **防重入狀態鎖 (Re-entrancy Protection)**：
   - 背景 Worker 執行緒必須具備狀態保護旗標（如 `_is_busy`、`_is_running`）。熱鍵連打或重複觸發時應安全忽略，防止並行重疊與 API 請求洪水。
4. **資源優雅釋放 (Resource Cleanup)**：
   - 確保應用程式關閉或 Worker 終止時，妥善釋放 `mss` 實例、麥克風音訊串流與背景執行緒。

---

## 4. 程式碼規範與安全防護 (Code Standards & Security)

1. **敏感資訊絕對防護**：
   - 嚴格禁止主動讀取、寫入、提交包含 `.env`、API Key 或任何私人金鑰與敏感環境變數之內容。
   - 任何涉及 API Key 的取用一律經由 `config.py`，並確保在無金鑰狀態下介面與系統能友善提示而非崩潰。
2. **路徑規範 (POSIX Relative Paths Only)**：
   - 專案內部所有配置、文檔、註解與程式碼之檔案引用，**一律使用跨平台相對路徑**（以 POSIX 正斜線 `/` 表示，如 `config.py`、`tts_engine.py`），**嚴格禁止硬編碼作業系統本機絕對路徑**（如特定磁碟機代號或絕對目錄）。
3. **語言規範**：
   - 註解、文檔、UI 顯示字串與 AI 回覆輸出**一律使用繁體中文（台灣）**。
4. **型別提示與異常防禦 (Type Hints & Robust Error Handling)**：
   - 函式簽名應標註型別提示（Type Hints）。
   - 涉及硬體操作（麥克風未插入、音訊設備佔用、螢幕擷取失敗）與外部網路 API 呼叫，必須進行精確的例外捕獲（`try-except`），並提供友善錯誤說明。

---

## 5. 協同工作流與角色分工 (Loop Engineering Workflow)

在多代理協同架構下，遵循分工明確之循環閉環流程：
1. **Plan & Critique**：由規劃者起草實作計畫與測試情境，定義 Done Criteria；由批判者嚴格比對規格與架構限制。
2. **Implement**：由實作者遵循核准計畫精準實作，維持簡潔代碼並維護進度紀錄。
3. **Test & Diagnose**：由測試者執行語法編譯檢查（`python -m py_compile`）與無硬體環境下的 Mock/功能驗證。
4. **Verify & Sign-off**：由驗證者獨立檢驗變更是否完全符合 Done Criteria 與無迴歸風險。

---

## 6. 開發與驗證指令常用清單 (Commands Reference)

- **套件可編輯安裝**：
  ```bash
  pip install -e .
  ```
- **語法編譯驗證**：
  ```bash
  python -m py_compile main.py tests/__init__.py tests/test_universal_agent.py src/game_assistant/__init__.py src/game_assistant/__main__.py src/game_assistant/cli.py src/game_assistant/app.py src/game_assistant/core/__init__.py src/game_assistant/core/config.py src/game_assistant/core/agent.py src/game_assistant/engines/__init__.py src/game_assistant/engines/jev_engine.py src/game_assistant/engines/ai_engine.py src/game_assistant/ui/__init__.py src/game_assistant/ui/gui.py src/game_assistant/audio/__init__.py src/game_assistant/audio/tts_engine.py src/game_assistant/audio/stt_engine.py src/game_assistant/utils/__init__.py src/game_assistant/utils/screen_capture.py src/game_assistant/utils/input_actuator.py src/game_assistant/strategies/__init__.py src/game_assistant/strategies/base.py src/game_assistant/strategies/genshin.py src/game_assistant/strategies/star_rail.py src/game_assistant/strategies/zzz.py src/game_assistant/strategies/general.py src/game_assistant/strategies/registry.py
  ```
- **單元測試套件執行**：
  ```bash
  python -m unittest discover -s tests
  # 或指定檔案直接執行
  python tests/test_universal_agent.py
  ```
- **單元/模組獨立自測**：
  ```bash
  python src/game_assistant/utils/screen_capture.py
  python src/game_assistant/engines/jev_engine.py
  python src/game_assistant/utils/input_actuator.py
  ```
- **啟動應用程式（三種模式）**：
  ```bash
  # 模式 1: Console Script 指令
  game-assistant

  # 模式 2: Python 模組模式
  python -m game_assistant

  # 模式 3: 根目錄相容啟動器
  python main.py
  ```
