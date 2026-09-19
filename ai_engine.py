import os
from typing import Optional
from PIL import Image
from google import genai
from config import GEMINI_API_KEY, MODEL_NAME, GameType, AnalysisMode, AssistCapability, PROMPTS


class GeminiAuxiliaryEngine:
    """
    Gemini 3.8 Flash 輔助認知引擎 (System 2 - Slow Thinking)
    由主決策模型轉為輔助引擎：
    1. 負責深度多模態視覺畫面剖析 (高階戰況、裝備詞條、大地圖解謎)
    2. 負責將玩家語音/文字需求 (User Demand) 拆解為 Jev 可執行的結構化戰術指令 (Strategy Directive)
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.model_name = MODEL_NAME
        self.client = None
        self._init_client()

    def _init_client(self):
        placeholder_keys = ("", "your_gemini_api_key_here", "your_api_key_here")
        key_val = (self.api_key or "").strip()
        if key_val and key_val not in placeholder_keys:
            try:
                self.client = genai.Client(api_key=key_val)
            except Exception as e:
                print(f"[GeminiAuxiliaryEngine] Client 初始化異常: {e}")
                self.client = None
        else:
            self.client = None

    def update_api_key(self, api_key: str):
        """動態更新 API Key"""
        self.api_key = api_key
        self._init_client()

    def decompose_user_demand(
        self,
        user_demand: str,
        game_type: GameType,
        capability: AssistCapability,
        image: Optional[Image.Image] = None
    ) -> str:
        """
        階段 1：由 Gemini 優先處理玩家需求，拆解為供 Jev 即時微觀決策之戰術指令 (Directive)
        :param user_demand: 玩家透過語音 (STT) 或文字輸入之需求 (如「幫我閃避紅光攻擊」、「現在要切誰輸出」)
        :param game_type: 遊戲類型
        :param capability: 輔助能力 (操作指導、代替操作、資料分析)
        :param image: 可選畫面截圖
        :return: 結構化戰術指導文字
        """
        if not user_demand or not user_demand.strip():
            return ""

        demand_lower = user_demand.lower()

        if not self.client:
            return self._fallback_decompose(user_demand, game_type, capability)

        game_name = game_type.value if hasattr(game_type, "value") else str(game_type)
        prompt = (
            f"你是一位頂級遊戲戰術決策專家 (Gemini 3.8 Flash)。\n"
            f"當前遊戲：{game_name}\n"
            f"輔助模式：{capability.value}\n"
            f"玩家提出了具體需求：【{user_demand.strip()}】。\n"
            "請將玩家需求轉化為極度簡潔的即時戰術指示 (Directive)，格式包含：\n"
            "1. 核心目標 (例如：破韌、極限閃避、元素反應、自動打怪)\n"
            "2. 推薦技能序列與優先級 (例如：切 2 號位 -> E -> 普攻)\n"
            "3. 警戒條件 (例如：遇黃光招架、遇紅光閃避)\n"
            "請以繁體中文回答，適合後續 Jev 高頻決策器直接取用。"
        )

        try:
            contents = [image, prompt] if image else [prompt]
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents
            )
            if response and response.text:
                return response.text.strip()
            return f"戰術目標：因應需求【{user_demand}】執行最佳輸出與防守。"
        except Exception as e:
            print(f"[GeminiAuxiliaryEngine] decompose_user_demand 異常: {e}")
            return self._fallback_decompose(user_demand, game_type, capability)

    def _fallback_decompose(
        self,
        user_demand: str,
        game_type: GameType,
        capability: AssistCapability
    ) -> str:
        demand_lower = user_demand.lower()
        game_str = game_type.value if hasattr(game_type, "value") else str(game_type)
        if "閃避" in user_demand or "dodge" in demand_lower or "紅光" in user_demand or "危險" in user_demand:
            return (
                f"【戰術指示 - {game_str}】：\n"
                f"1. 核心目標：極限閃避防禦\n"
                f"2. 推薦操作：抓準攻擊前搖無敵幀，立即按下 Shift / 右鍵\n"
                f"3. 警戒條件：鎖定敵方紅光或紅圈警示"
            )
        elif "招架" in user_demand or "parry" in demand_lower or "黃光" in user_demand:
            return (
                f"【戰術指示 - {game_str}】：\n"
                f"1. 核心目標：極限招架反擊\n"
                f"2. 推薦操作：敵方閃黃光瞬間按下 Space / C 觸發支援突擊\n"
                f"3. 警戒條件：失衡積蓄最大化"
            )
        elif "大招" in user_demand or "終結技" in user_demand or "burst" in demand_lower or "ult" in demand_lower:
            return (
                f"【戰術指示 - {game_str}】：\n"
                f"1. 核心目標：終結技/大招爆發破韌\n"
                f"2. 推薦操作：按下 1-4 號位大招或 Q 鍵進行立即插隊輸出\n"
                f"3. 警戒條件：確認敵方處於弱點或失衡易傷狀態"
            )
        elif "反應" in user_demand or "元素" in user_demand or "蒸發" in user_demand or "融化" in user_demand:
            return (
                f"【戰術指示 - {game_str}】：\n"
                f"1. 核心目標：元素反應增傷鏈\n"
                f"2. 推薦操作：切換 2 號位掛水/火/雷 ➔ 切回 1 號位主 C 施放戰技 E 與平 A\n"
                f"3. 警戒條件：維持元素附著覆蓋"
            )
        elif "分析" in user_demand or "資料" in user_demand:
            return (
                f"【戰術指示 - {game_str}】：\n"
                f"1. 核心目標：戰鬥遙測與資源分析\n"
                f"2. 推薦操作：統計威脅度與 SP/能量循環\n"
                f"3. 警戒條件：監控血量低於 30% 與戰技點耗盡"
            )
        else:
            return (
                f"【戰術指示 - {game_str}】：\n"
                f"1. 核心目標：因應需求「{user_demand}」維持最佳攻防\n"
                f"2. 推薦操作：技能 E/Q 冷卻好即施放，穿插普攻壓制\n"
                f"3. 警戒條件：保持拉扯走位，遇危險立即閃避"
            )

    def analyze_screen(
        self,
        image: Image.Image,
        game_type: GameType,
        mode: AnalysisMode,
        custom_prompt: Optional[str] = None
    ) -> str:
        """
        深度多模態視覺畫面剖析 (快照分析 F10 / 裝備遺器評估 / 地圖解謎)
        :param image: PIL Image 物件
        :param game_type: 遊戲類型
        :param mode: 分析模式
        :param custom_prompt: 玩家自訂提示詞
        :return: 深度 Markdown 分析文字
        """
        if not self.client:
            return "⚠️ **提示**：未檢測到 Gemini API Key。Gemini 輔助認知處於離線狀態，Jev 決策核心將依據本地啟發式決策運作。"

        if custom_prompt and custom_prompt.strip():
            game_name = game_type.value if hasattr(game_type, "value") else str(game_type)
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
                model=self.model_name,
                contents=[image, final_prompt]
            )
            if response and response.text:
                return response.text
            return "⚠️ Gemini 輔助認知未返回文字結果。"
        except Exception as e:
            return f"❌ **Gemini 輔助認知分析異常**：\n```\n{str(e)}\n```"


# 向下相容別名
GeminiAIEngine = GeminiAuxiliaryEngine


if __name__ == "__main__":
    engine = GeminiAuxiliaryEngine()
    print("Gemini 3.8 Flash Auxiliary Engine Initialized. Key present:", bool(engine.api_key))
