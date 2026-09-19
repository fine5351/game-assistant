import os
from typing import Optional
from PIL import Image
from google import genai
from config import GEMINI_API_KEY, MODEL_NAME, GameType, AnalysisMode, PROMPTS


class GeminiAIEngine:
    """
    Gemini 3.6 Flash 多模態遊戲視覺分析引擎
    使用 google-genai SDK 進行影像與 Prompt 分析
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.client = None
        self._init_client()

    def _init_client(self):
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def update_api_key(self, api_key: str):
        """動態更新 API Key"""
        self.api_key = api_key
        self._init_client()

    def analyze_screen(
        self,
        image: Image.Image,
        game_type: GameType,
        mode: AnalysisMode,
        custom_prompt: Optional[str] = None
    ) -> str:
        """
        對遊戲螢幕截圖進行多模態 AI 視覺分析
        :param image: PIL Image 物件
        :param game_type: 遊戲類型 (原神、崩鐵、絕區零、泛用)
        :param mode: 分析模式 (戰力/機制、養成/裝備、地圖/解謎)
        :param custom_prompt: 玩家自訂語音或文字發問提示詞
        :return: AI 分析出的 Markdown 戰術與建議文字
        """
        if not self.client:
            return "⚠️ **錯誤**：未檢測到 Gemini API Key。請在 `.env` 中設定 `GEMINI_API_KEY` 或於介面設定。"

        # 組合 Prompt：若有語音發問 custom_prompt 則優先將其作為核心問題
        if custom_prompt and custom_prompt.strip():
            game_name = game_type.value if hasattr(game_type, 'value') else str(game_type)
            final_prompt = (
                f"玩家提出了關於畫面的具體問題：【{custom_prompt.strip()}】。\n"
                f"請結合當前遊戲畫面與遊戲類型 ({game_name})，給出精準且直接的解答與戰術指引。請以繁體中文回答。"
            )
        else:
            final_prompt = PROMPTS.get(game_type, {}).get(
                mode,
                PROMPTS[GameType.GENERAL][AnalysisMode.COMBAT]
            )

        try:
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=[image, final_prompt]
            )
            if response and response.text:
                return response.text
            else:
                return "⚠️ API 未返回任何文字結果。"
        except Exception as e:
            return f"❌ **AI 分析發生異常**：\n```\n{str(e)}\n```"


if __name__ == "__main__":
    # 測試 init
    engine = GeminiAIEngine()
    print("Gemini AI Engine Initialized. API key present:", bool(engine.api_key))

