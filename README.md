# Gemini 米哈遊遊戲即時視覺輔助助手 (Real-time Vision AI Game Assistant)

基於 **Google Gemini 3.6 Flash** 的超低延遲、輕量級 Windows 桌面遊戲視覺輔助工具。專為米哈遊旗艦遊戲（**原神**、**崩壞：星穹鐵道**、**絕區零**）與通用遊戲模式設計，提供即時戰況提示、裝備與聖遺物評估以及地圖解謎通關指引，並完整支援雙向語音互動功能 (pyttsx3 離線 TTS 播報 + SpeechRecognition 語音發問)。

---

## 🌟 核心特色 (Key Features)

- ⚡ **Gemini 3.6 Flash 多模態 AI**：利用最新的 `google-genai` SDK (`gemini-3.6-flash`) 進行強大且快速的視覺圖像分析。
- 🎙️ **雙向語音互動 (Voice Interaction)**：
  - **🎤 離線/線上語音指令發問 (STT)**：按下 **`F11`** 或點擊 🎤 按鈕，即可透過麥克風口述問題（如：「這隻 Boss 的招式怎麼躲？」），系統自動語音轉文字並結合當前遊戲畫面傳送給 Gemini AI 分析。
  - **🔊 離線語音戰術播報 (TTS)**：基於 Windows SAPI5 (`pyttsx3`)，當 AI 戰術報告回傳時，自動過濾 Markdown 標點與代碼符號，進行語音朗讀，讓玩家「用聽的」掌握戰況。面板提供一鍵 🔊 朗讀 ON/OFF 切換按鈕。
- 🎮 **米哈遊三大遊戲專屬 Prompts**：
  - **原神 (Genshin Impact)**：元素反應組合提示（蒸發/超綻放/超激化等）、技能施放時機與 Boss 機制警告。
  - **崩壞：星穹鐵道 (Honkai: Star Rail)**：敵方弱點與韌性條破韌分析、戰技點 (SP) 餘額控管與終結技插隊提示。
  - **絕區零 (Zenless Zone Zero)**：敵方攻擊黃/紅光前搖警示、極限閃避與招架 (Parry) 時機、失衡值與連攜技切換。
  - **泛用遊戲模式 (General)**：適用於魂類、RPG 或其他各類遊戲。
- 💎 **Windows 透明置頂懸浮面板 (Always-On-Top Overlay)**：
  - 支援無邊框滑鼠拖曳移動與透明度滑桿調節 (20% ~ 100%)。
  - 一鍵收合/展開視窗，不佔用遊戲畫面。
  - 原生 Markdown 語法高亮顯示戰術報告。
- ⌨️ **全域無縫熱鍵綁定 (Global Hotkeys)**：
  - **`F9`**：一鍵切換「自動即時背景輪詢」與「暫停」。
  - **`F10`**：手動快照觸發一次 AI 視覺分析。
  - **`F11`**：觸發麥克風錄音與語音轉文字指令發問。
- 🚀 **極致流暢與超低延遲**：
  - 使用 `mss` 硬體加速擷取畫面，單次截圖與預處理耗時小於 50ms。
  - 採用 PyQt6 `QThread` 背景非同步獨立線程 (分離 `STTWorker` 與 `TTSWorker`)，主 UI 維持 60 FPS 且零卡頓。

---

## 📁 專案檔案結構 (Project Architecture)

```
game-assistant/
├── config.py              # 系統設定、熱鍵、TTS/STT 參數、遊戲與模式 Prompt 範本庫
├── screen_capture.py      # mss 與 Pillow 高效畫面擷取與尺寸預處理
├── ai_engine.py           # google-genai SDK 與 Gemini 多模態語音 Prompt 分析介面
├── tts_engine.py          # Windows SAPI5 離線 TTS 朗讀與 Markdown 文字淨化
├── stt_engine.py          # SpeechRecognition 麥克風擷取與繁中 STT 語音辨識
├── gui.py                 # PyQt6 置頂懸浮 Overlay 視窗 (含 🔊/🎤 按鈕與熱鍵信號)
├── main.py                # 主程式入口點與 QThread 異步 Worker 調度器 (STT/TTS 防死鎖)
├── requirements.txt       # Python 套件依賴清單
├── .env.example           # API Key 環境變數設定檔範本
└── README.md              # 繁體中文使用說明
```

---

## 🛠️ 安裝與快速開始 (Installation & Quick Start)

### 1. 環境要求
- 操作系統：Windows 10 / 11
- Python 版本：Python 3.10 或更高版本
- 硬體設備：可用麥克風與喇叭/耳機

### 2. 安裝依賴套件
開啟 PowerShell 或 CMD 終端機，執行以下指令：
```bash
pip install -r requirements.txt
```

### 3. 配置 Gemini API Key
複製 `.env.example` 並重新命名為 `.env`：
```bash
copy .env.example .env
```
編輯 `.env` 檔案，將 `GEMINI_API_KEY` 替換為您的真實 API 金鑰：
```env
GEMINI_API_KEY=AIzaSy...your_gemini_api_key...
```

### 4. 啟動助手
執行 `main.py` 啟動置頂懸浮面板：
```bash
python main.py
```

---

## 🎮 使用說明與熱鍵操作 (Usage & Controls)

1. **選擇遊戲與模式**：
   - 於懸浮面板上方下拉選單切換【遊戲】（原神 / 崩鐵 / 絕區零 / 泛用）。
   - 切換【模式】（即時戰況與操作建議 / 角色養成與裝備評估 / 地圖解謎與探索指引）。
2. **手動觸發分析 (`F10`)**：
   - 在遊戲過程中隨時按下全域熱鍵 `F10` 或點擊【⚡ 快照分析】，助手將立即擷取畫面並返回 AI 戰術報告。
3. **語音指令發問 (`F11`)**：
   - 按下 **`F11`** 鍵或點擊面板上的【🎤 語音發問】，對麥克風口述問題（例如：「這隻怪物有什麼弱點？」）。
   - 系統將自動進行語音轉文字，並結合當前遊戲畫面送交 Gemini 分析解答。
4. **語音朗讀切換 (`🔊 朗讀: ON/OFF`)**：
   - 點擊【🔊 朗讀】按鈕可即時開啟或關閉 AI 報告的背景語音播報。
5. **自動即時輪詢 (`F9`)**：
   - 按下 `F9` 鍵開啟背景輪詢（預設每 2 秒輪詢一次），面板標誌將變更為 `🔄 輪詢中`。再按一次 `F9` 即可暫停輪詢。
6. **介面調整**：
   - 拖曳頂部標題列可隨意調整懸浮面板位置。
   - 滑動【透明度】滑桿調整視窗遮擋程度。
   - 點擊【`─`】按鈕可將面板收合為頂部精簡條。

---

## ⚠️ 免責聲明 (Disclaimer)

本工具為外掛式畫面讀取與語音輔助工具，僅透過 OS 螢幕擷取 API (`mss`) 讀取圖像進行視覺 AI 分析，**不包含**任何記憶體修改、封包改寫或遊戲數據注入行為。請合理使用本工具，尊重遊戲規範。
