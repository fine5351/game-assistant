# 專案代理規則與工程指引 (AGENTS.md)

本文件定義 AI Agent 在此專案庫 (`game-assistant`) 進行開發、維護、除錯與協同作業時所必須嚴格遵守的架構規範、工程原則與工作流程。

---

## 1. 專案概觀與技術架構 (Project Architecture)

### 1.1 專案定位
本專案為基於 **Google Gemini 3.6 Flash** 的 Windows 桌面即時遊戲視覺與語音輔助助手。專為米哈遊系列遊戲（《原神》、《崩壞：星穹鐵道》、《絕區零》）及泛用遊戲模式提供低延遲即時戰況分析、角色養成與裝備評估以及地圖解謎通關指引，並完整整合雙向語音互動功能（STT 語音發問 + TTS 離線朗讀）。

### 1.2 核心技術棧 (Tech Stack)
- **語言環境**：Python 3.10+
- **核心 AI**：`google-genai` SDK (`gemini-3.6-flash`)
- **圖形介面**：PyQt6（置頂透明懸浮面板、無邊框滑鼠拖曳、Markdown 即時渲染）
- **視覺擷取**：`mss` 硬體加速螢幕快照 + `Pillow` 雙線性縮放預處理
- **全域熱鍵**：`pynput` 背景熱鍵監聽（F9 輪詢切換 / F10 快照分析 / F11 語音發問）
- **離線語音朗讀 (TTS)**：`pyttsx3` (Windows SAPI5) + Markdown 語法符號過濾 + COM 執行緒安全防護
- **語音指令辨識 (STT)**：`SpeechRecognition` + `PyAudio`（麥克風環境噪音自動校正、繁中辨識）
- **環境設定**：`python-dotenv` 載入設定

### 1.3 核心模組職責劃分 (Module Responsibilities)
- `main.py`：應用程式進入點與多執行緒排程中心。負責實例化各引擎與介面，並以 `QThread` 隔離 `AnalysisWorker`、`STTWorker`、`TTSWorker`，確保 UI 主執行緒保持 60 FPS 零卡頓與無死鎖。
- `gui.py`：PyQt6 置頂懸浮視窗介面 (`GameAssistantOverlay`) 與全域熱鍵訊號橋接器 (`HotkeyListener`)。負責即時 Markdown 渲染、透明度調節、收合展開與狀態指示。
- `config.py`：系統組態、熱鍵設定、TTS/STT 參數設定，以及各遊戲與分析模式之專屬 Prompt 範本庫 (`PROMPTS`)。
- `screen_capture.py`：封裝 `mss` 與 `Pillow`，提供超低延遲（< 50ms）之螢幕區域或全螢幕擷取與尺寸縮放預處理。
- `ai_engine.py`：封裝 `GeminiAIEngine`，串接 `google-genai` 呼叫 `gemini-3.6-flash`，支援標準模式 Prompt 與玩家語音自訂問答 (`custom_prompt`)。
- `tts_engine.py`：`TTSEngine` 與 `clean_markdown_for_tts`。提供 Windows SAPI5 語音合成、Markdown 標點符號與代碼清理、繁中語音包選擇與 COM 執行緒初始化生命週期管理。
- `stt_engine.py`：`STTEngine`。提供麥克風收音、環境噪音自動校準與 Google 語音辨識，包含設備缺失與超時等嚴密異常處理。

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

- **語法編譯驗證**：
  ```bash
  python -m py_compile main.py gui.py config.py screen_capture.py ai_engine.py tts_engine.py stt_engine.py
  ```
- **單元/模組自測**：
  ```bash
  python screen_capture.py
  python ai_engine.py
  python tts_engine.py
  python stt_engine.py
  ```
- **啟動應用程式**：
  ```bash
  python main.py
  ```
