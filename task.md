# Gemini 米哈遊遊戲即時視覺輔助助手實作任務列表 (task.md)

- [x] 任務 1: 建立 `requirements.txt` 與 `.env.example`
- [x] 任務 2: 實作 `config.py` (載入環境變數、熱鍵、遊戲與模式 Prompt 範本)
- [x] 任務 3: 實作 `screen_capture.py` (mss 與 Pillow 畫面擷取與縮放預處理)
- [x] 任務 4: 實作 `ai_engine.py` (google-genai SDK 整合與米哈遊三款遊戲分析)
- [x] 任務 5: 實作 `gui.py` (PyQt6 懸浮視窗、無邊框拖動、透明度滑桿、收合按鈕、Markdown 面板、pynput 熱鍵信號)
- [x] 任務 6: 實作 `main.py` (QThread 背景執行擷取與 AI 分析、主程式進入點與啟動)
- [x] 任務 7: 建立 `README.md` (繁體中文完整使用說明)
- [x] 任務 8: 執行語法與單元/模組驗證 (Python 語法檢查與基本測試)
- [x] 任務 9: 更新 `requirements.txt` 加入語音套件 (`pyttsx3`, `SpeechRecognition`, `PyAudio`, `pywin32`)
- [x] 任務 10: 擴充 `config.py` 加入 F11 熱鍵、TTS/STT 設定參數
- [x] 任務 11: 實作 `tts_engine.py` (Windows SAPI5 離線 TTS 與 Markdown 文字淨化)
- [x] 任務 12: 實作 `stt_engine.py` (SpeechRecognition 麥克風擷取與繁中 STT)
- [x] 任務 13: 擴充 `ai_engine.py` 支援語音自訂 Prompt 提問
- [x] 任務 14: 擴充 `gui.py` 新增 🔊 TTS 開關與 🎤 語音指令 [F11] 按鈕及狀態顯示
- [x] 任務 15: 擴充 `main.py` 建立 `STTWorker` 與 `TTSWorker` (QThread 獨立防死鎖)
- [x] 任務 16: 更新 `README.md` 說明語音功能與 F11 熱鍵操作
- [x] 任務 17: 執行系統功能與語法驗證


