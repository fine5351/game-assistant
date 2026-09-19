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
