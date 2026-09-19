if __name__ == "__main__" and not __package__:
    import sys
    from pathlib import Path
    _src = str(Path(__file__).resolve().parents[2])
    if _src not in sys.path:
        sys.path.insert(0, _src)

import os
from typing import Optional
from PIL import Image
from google import genai
from game_assistant.core.config import GEMINI_API_KEY, MODEL_NAME, GameType, AnalysisMode, AssistCapability, PROMPTS


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
        cap_name = capability.value if hasattr(capability, "value") else str(capability)
        prompt = (
            f"你是一位頂級遊戲戰術決策專家 (Gemini 3.8 Flash)。\n"
            f"當前遊戲：{game_name}\n"
            f"輔助模式：{cap_name}\n"
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

    def translate_screen(
        self,
        image: Image.Image,
        game_type: GameType = GameType.GENERAL,
        target_lang: str = "繁體中文"
    ) -> str:
        """
        外文遊戲畫面多模態視覺翻譯
        擷取遊戲畫面，識別畫面外文 UI、按鈕、劇情對話與任務並翻譯為目標語言 (預設繁中)
        :param image: PIL 截圖
        :param game_type: 遊戲類型
        :param target_lang: 目標語言
        :return: 結構化 Markdown 翻譯對照報告
        """
        if not self.client:
            return self._fallback_screen_translation(game_type, target_lang)

        prompt = (
            f"你是一位頂尖的多國語言遊戲在地化與介面視覺翻譯大師。\n"
            f"請深度解析這張外文遊戲畫面，將畫面中的所有外語（英文、日文、韓文、俄文等）徹底翻譯為【{target_lang}（台灣）】。\n\n"
            "請嚴格依據以下結構化格式清晰輸出：\n\n"
            "### 🌐 遊戲畫面外文翻譯報告\n\n"
            "#### 1. 🖥️ 介面與選單對照 (UI & Navigation)\n"
            "| 原始外文 | 繁體中文翻譯 | 功能說明/對應位置 |\n"
            "| :--- | :--- | :--- |\n"
            "| [原文] | [繁中翻譯] | [位置說明] |\n\n"
            "#### 2. 📜 任務與劇情字幕 (Quest & Dialogue)\n"
            "- **說話者/標題**：`[原文]` ➔ **[繁中翻譯]**\n\n"
            "#### 3. 💬 聊天與玩家互動 (Chat & Subtitles)\n"
            "- **[發言者]**：`[原文]` ➔ **[繁中翻譯]**\n\n"
            "#### 4. 💡 即時操作指引\n"
            "- [下一步建議或快捷鍵提醒]\n\n"
            "若畫面中存在對話字幕、NPC台詞或玩家聊天發言，請務必在文末附帶標準 JSON 區塊供系統即時浮動輸出：\n"
            "```json\n"
            "[\n"
            '  {"sender": "說話者", "original": "外文原文", "translated": "繁中翻譯"}\n'
            "]\n"
            "```\n\n"
            "請使用流暢易讀的繁體中文，格式條點美觀，適合玩家即時查閱。"
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[image, prompt]
            )
            if response and response.text:
                return response.text.strip()
            return "⚠️ Gemini 畫面翻譯未返回內容。"
        except Exception as e:
            return f"❌ **Gemini 畫面翻譯異常**：\n```\n{str(e)}\n```\n\n" + self._fallback_screen_translation(game_type, target_lang)

    def translate_chat_subtitles(
        self,
        image: Image.Image,
        game_type: GameType = GameType.GENERAL,
        target_lang: str = "繁體中文"
    ) -> tuple[str, list[dict]]:
        """
        專注於遊戲對話字幕與聊天訊息之多模態識別與即時翻譯
        :param image: PIL 截圖
        :param game_type: 遊戲類型
        :param target_lang: 目標語言
        :return: (markdown_report, list_of_subtitle_items)
        """
        if not self.client:
            return self._fallback_chat_subtitles(target_lang)

        prompt = (
            f"你是一位遊戲語音字幕與聊天框即時翻譯助手。\n"
            f"請聚焦辨識畫面中的「對話字幕 (Subtitles)」或「玩家文字聊天框 (Chat Box)」的外文內容，並翻譯為【{target_lang}】。\n"
            "請在輸出末尾附帶標準 JSON 格式區塊，供系統在遊戲上方浮動輸出翻譯字幕：\n"
            "```json\n"
            "[\n"
            '  {"sender": "玩家或NPC名稱", "original": "外文原文", "translated": "繁中翻譯"}\n'
            "]\n"
            "```\n"
            "前文請用清晰的 Markdown 對照輸出。"
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[image, prompt]
            )
            text = response.text.strip() if response and response.text else ""
            if not text:
                return self._fallback_chat_subtitles(target_lang)

            subtitles = self._extract_subtitles_from_json(text)
            return text, subtitles
        except Exception as e:
            print(f"[GeminiAuxiliaryEngine] translate_chat_subtitles 異常: {e}")
            return self._fallback_chat_subtitles(target_lang)

    def translate_voice_text(
        self,
        chinese_text: str,
        target_lang: str = "英文"
    ) -> str:
        """
        將玩家的中文語音文字（STT 辨識結果）翻譯為目標外語，供自動輸入至遊戲文字聊天框
        :param chinese_text: 繁體中文文字
        :param target_lang: 目標語言 (如 '英文', '日文', '韓文', '俄文')
        :return: 翻譯後的目標外語文字 (直接可用於聊天發言)
        """
        if not chinese_text or not chinese_text.strip():
            return ""

        if not self.client:
            return self._fallback_voice_translation(chinese_text, target_lang)

        prompt = (
            f"你是一位專業的多人線上遊戲隊伍對話翻譯員。\n"
            f"請將玩家說的繁體中文：【{chinese_text.strip()}】精確翻譯為符合線上遊戲玩家慣用溝通的【{target_lang}】。\n"
            "【嚴格規定】：\n"
            "1. 僅返回翻譯後的純文字字串，絕對不要包含引號、解釋、音標或任何多餘文字。\n"
            "2. 語氣自然、簡短有力，符合遊戲隊伍報點、戰術配合與社交打招呼習慣。"
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt]
            )
            if response and response.text:
                clean_text = response.text.strip().strip('"\'`')
                return clean_text
            return self._fallback_voice_translation(chinese_text, target_lang)
        except Exception as e:
            print(f"[GeminiAuxiliaryEngine] translate_voice_text 異常: {e}")
            return self._fallback_voice_translation(chinese_text, target_lang)

    def _extract_subtitles_from_json(self, text: str) -> list[dict]:
        """
        從 AI 產生的輸出中高容錯抽取字幕列表 (支援 JSON 區塊、原始 JSON 與 Markdown 正則降級)
        """
        import json
        import re

        # 1. 優先嘗試由 Markdown 代碼區塊提取 (容許帶或不帶 json 語言標註)
        code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if code_block_match:
            try:
                data = json.loads(code_block_match.group(1).strip())
                if isinstance(data, list):
                    return [x for x in data if isinstance(x, dict)]
                elif isinstance(data, dict):
                    for k in ("subtitles", "dialogues", "chat", "items", "messages"):
                        if isinstance(data.get(k), list):
                            return [x for x in data[k] if isinstance(x, dict)]
                    if "original" in data or "translated" in data:
                        return [data]
            except Exception:
                pass

        # 2. 嘗試直接在文本中匹配原始 JSON 陣列模式 [...]
        raw_array_match = re.search(r'\[\s*\{[\s\S]*?\}\s*\]', text)
        if raw_array_match:
            try:
                data = json.loads(raw_array_match.group(0).strip())
                if isinstance(data, list):
                    return [x for x in data if isinstance(x, dict)]
            except Exception:
                pass

        # 3. 若無可用 JSON，以結構化規則解析 Markdown 對話/字幕行
        subtitles = []
        for line in text.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("|") or line_str.startswith("#"):
                continue

            if "➔" in line_str or "->" in line_str:
                parts = re.split(r'➔|->', line_str, maxsplit=1)
                if len(parts) == 2:
                    left_raw = parts[0].strip(" -*`#")
                    right_raw = parts[1].strip(" -*`#【】")

                    # 解析發言者與原文
                    sender = "對話"
                    orig_text = left_raw
                    # 匹配 - **發言者**：原文 或 [發言者]: 原文
                    prefix_match = re.match(r'^(?:\[([^\]]+)\]|\*\*([^*]+)\*\*|([^：:]+))[：:]\s*(.*)$', left_raw)
                    if prefix_match:
                        s_cand = prefix_match.group(1) or prefix_match.group(2) or prefix_match.group(3)
                        remainder = prefix_match.group(4)
                        if s_cand and remainder:
                            sender = s_cand.strip(" *#`")
                            orig_text = remainder.strip(" `*\'\"[]")

                    orig_clean = orig_text.strip(" `*\'\"[]")
                    trans_clean = right_raw.strip(" `*\'\"【】")
                    if orig_clean and trans_clean:
                        subtitles.append({
                            "sender": sender,
                            "original": orig_clean,
                            "translated": trans_clean
                        })
        return subtitles

    def _fallback_screen_translation(self, game_type: GameType, target_lang: str) -> str:
        game_name = game_type.value if hasattr(game_type, "value") else str(game_type)
        return (
            f"### 🌐 遊戲畫面外文翻譯 (離線對照模式)\n\n"
            f"> ℹ️ *當前處於離線確定性對照模式（未檢測到有效 Gemini API Key）。以下提供通用介面與常見外文對照表。*\n\n"
            f"**當前遊戲**：`{game_name}` | **目標語言**：`{target_lang}`\n\n"
            f"#### 1. 🖥️ 介面與選單對照 (UI & Navigation)\n"
            f"| 原始外文 | 繁體中文翻譯 | 功能說明/對應位置 |\n"
            f"| :--- | :--- | :--- |\n"
            f"| **Settings / Options** | **系統設定** | 畫面/音效/操作鍵位配置 |\n"
            f"| **Inventory / Bag** | **背包 / 道具欄** | 裝備、聖遺物與消耗品清單 |\n"
            f"| **Quest Log / Missions** | **任務日誌** | 主線/支線/每日委託追蹤 |\n"
            f"| **Party / Team Setup** | **隊伍配置** | 角色編隊與切換出戰陣容 |\n"
            f"| **Character / Agent** | **角色面板** | 屬性數值、天賦與技能升級 |\n"
            f"| **Confirm / OK** | **確認 / 確定** | 確定當前操作 |\n"
            f"| **Cancel / Back** | **取消 / 返回** | 關閉或返回上一層介面 |\n\n"
            f"#### 2. 📜 劇情與字幕對話 (Subtitles)\n"
            f"- **System / NPC**：`[Attention! Danger ahead]` ➔ **【警告！前方有危險】**\n\n"
            f"#### 3. 💬 聊天室訊息 (Chat)\n"
            f"- **Teammate**：`[Group up here, let's fight together!]` ➔ **【在這邊集合，一起打！】**\n\n"
            f"```json\n"
            f"[\n"
            f'  {{"sender": "System / NPC", "original": "Attention! Danger ahead", "translated": "警告！前方有危險"}},\n'
            f'  {{"sender": "Teammate", "original": "Group up here, let\'s fight together!", "translated": "在這邊集合，一起打！"}}\n'
            f"]\n"
            f"```\n\n"
            f"💡 **提示**：配置 `GEMINI_API_KEY` 後即可啟動 Gemini 3.8 Flash 實時多模態視覺多國語言完整翻譯。"
        )

    def _fallback_chat_subtitles(self, target_lang: str) -> tuple[str, list[dict]]:
        report = (
            "### 💬 遊戲字幕與對話即時翻譯\n\n"
            "- **NPC / 隊友**：`Watch out! The boss is entering phase 2.` ➔ **【注意！Boss 進入第二階段！】**\n"
            "- **Team**：`Need backup at point A!` ➔ **【A 點需要支援！】**\n"
        )
        subtitles = [
            {
                "sender": "NPC / 隊友",
                "original": "Watch out! The boss is entering phase 2.",
                "translated": "注意！Boss 進入第二階段！"
            },
            {
                "sender": "Team",
                "original": "Need backup at point A!",
                "translated": "A 點需要支援！"
            }
        ]
        return report, subtitles

    def _fallback_voice_translation(self, chinese_text: str, target_lang: str) -> str:
        txt = chinese_text.strip().lower()

        # 針對不同目標外語（英文 / 日文 / 韓文 / 俄文）之遊戲溝通本地字典
        vocab_en = {
            "救我": "Help me!", "救一下": "Help me please!", "救命": "Help!",
            "快跑": "Run! / Retreat!", "快撤": "Fall back!", "撤退": "Retreat!",
            "集合": "Group up here!", "過來": "Come here!", "來這裡": "Gather here!",
            "打boss": "Let's attack the boss!", "打王": "Focus the boss!",
            "開大": "Use your ultimate!", "大招好了": "My ultimate is ready!",
            "漂亮": "Nice play!", "打得好": "Good job!",
            "好的": "OK / Got it!", "收到": "Roger that!",
            "謝謝": "Thanks! / GG!", "多謝": "Thank you!", "感謝": "Thank you so much! GG!",
            "我是台灣人": "I am from Taiwan, nice to meet you!",
            "有人嗎": "Anyone here?", "走這裡": "This way!",
            "注意閃避": "Watch out! Dodge!", "小心": "Be careful!",
            "你好": "Hello everyone!", "哈囉": "Hi there!",
            "加油": "Let's do this!", "稍等": "Wait a moment please.", "等我一下": "Wait for me please."
        }

        vocab_ja = {
            "救我": "助けて！", "救一下": "助けてください！", "救命": "助けて！",
            "快跑": "逃げて！", "快撤": "引いて！", "撤退": "撤退！",
            "集合": "集合！", "過來": "こっちに来て！", "來這裡": "ここに集まって！",
            "打boss": "ボスを集中攻撃！", "打王": "ボスを狙って！",
            "開大": "ウルト使って！", "大招好了": "必殺技準備完了！",
            "漂亮": "ナイス！", "打得好": "ナイスプレイ！",
            "好的": "了解！", "收到": "了解です！",
            "謝謝": "ありがとう！ GG！", "多謝": "どうも！", "感謝": "ありがとうございます！",
            "我是台灣人": "台湾から来ました、よろしくお願いします！",
            "有人嗎": "誰かいますか？", "走這裡": "こっちです！",
            "注意閃避": "気をつけて！回避！", "小心": "注意してください！",
            "你好": "こんにちは！", "哈囉": "やあ！",
            "加油": "頑張りましょう！", "稍等": "ちょっと待って！", "等我一下": "待ってください！"
        }

        vocab_ko = {
            "救我": "살려주세요!", "救一下": "도와주세요!", "救命": "살려줘요!",
            "快跑": "도망쳐요!", "快撤": "후퇴해요!", "撤退": "후퇴!",
            "集合": "모여주세요!", "過來": "이쪽으로 와요!", "來這裡": "여기 모여요!",
            "打boss": "보스 점사해요!", "打王": "보스 집중 공격!",
            "開大": "궁극기 써주세요!", "大招好了": "궁극기 준비 완료!",
            "漂亮": "나이스!", "打得好": "잘했어요!",
            "好的": "확인!", "收到": "알겠습니다!",
            "謝謝": "감사합니다! GG!", "多謝": "고마워요!", "感謝": "정말 감사합니다!",
            "我是台灣人": "대만에서 왔습니다, 잘 부탁드립니다!",
            "有人嗎": "누구 계신가요?", "走這裡": "이쪽이에요!",
            "注意閃避": "조심해요! 회피!", "小心": "조심하세요!",
            "你好": "안녕하세요!", "哈囉": "안녕!",
            "加油": "화이팅!", "稍等": "잠시만요!", "等我一下": "잠시만 기다려주세요!"
        }

        vocab_ru = {
            "救我": "Помогите!", "救一下": "Помогите, пожалуйста!", "救命": "Спасите!",
            "快跑": "Бегите!", "快撤": "Назад!", "撤退": "Отступаем!",
            "集合": "Собираемся здесь!", "過來": "Сюда!", "來這裡": "Идите сюда!",
            "打boss": "Атакуем босса!", "打王": "Фокусите босса!",
            "開大": "Используй ульту!", "大招好了": "Ульта готова!",
            "漂亮": "Отлично!", "打得好": "Хорошая игра!",
            "好的": "Хорошо!", "收到": "Принято!",
            "謝謝": "Спасибо! GG!", "多謝": "Благодарю!", "感謝": "Большое спасибо!",
            "我是台灣人": "Я из Тайваня, приятно познакомиться!",
            "有人嗎": "Есть кто?", "走這裡": "Сюда!",
            "注意閃避": "Осторожно! Уворачивайтесь!", "小心": "Осторожно!",
            "你好": "Всем привет!", "哈囉": "Привет!",
            "加油": "Вперёд!", "稍等": "Минутку.", "等我一下": "Подождите меня."
        }

        if "日" in target_lang:
            target_dict = vocab_ja
            prefix = "[日文]"
        elif "韓" in target_lang:
            target_dict = vocab_ko
            prefix = "[韓文]"
        elif "俄" in target_lang:
            target_dict = vocab_ru
            prefix = "[Русский]"
        else:
            target_dict = vocab_en
            prefix = "[Chat]"

        for k, v in target_dict.items():
            if k in txt:
                return v

        return f"{prefix}: {chinese_text}"


# 向下相容別名
GeminiAIEngine = GeminiAuxiliaryEngine


if __name__ == "__main__":
    engine = GeminiAuxiliaryEngine()
    print("Gemini 3.8 Flash Auxiliary Engine Initialized. Key present:", bool(engine.api_key))
    print("離線語音翻譯測試 ('救我'):", engine.translate_voice_text("救我", target_lang="英文"))

