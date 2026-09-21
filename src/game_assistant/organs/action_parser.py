"""
動作序列抽取與操作腳本解析器 (Action Sequence Extractor)
負責將玩家自然語言需求或大腦戰術指示 (Directive) 智慧解析為微觀按鍵與滑鼠動作序列。
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from game_assistant.core.config import GameType


@dataclass
class ActionStep:
    """單一微觀操作步驟"""
    action_type: str        # 'key', 'hold_key', 'click', 'hold_click', 'wait'
    target: str             # 按鍵名稱 ('1', '2', 'e', 'q', 'shift') 或滑鼠鍵 ('left', 'right')
    duration: float = 0.05  # 按鍵或點擊維持時長 (秒)
    post_delay: float = 0.15 # 步驟結束後之硬直等待時長 (秒)
    description: str = ""   # 步驟語義說明

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "target": self.target,
            "duration": self.duration,
            "post_delay": self.post_delay,
            "description": self.description
        }


class ActionSequenceExtractor:
    """
    動作序列抽取器
    能深度解析米哈遊遊戲（原神、崩鐵、絕區零）與泛用遊戲的戰術指令文本
    """

    TAKEYOVER_KEYWORDS = [
        "長出手", "長手", "生長手", "手在哪", "接管", "幫我打", "代打", "自動打",
        "執行操作", "幫我操作", "連招", "放技能", "開大招", "核爆", "自動戰鬥"
    ]

    @classmethod
    def is_takeover_or_hand_demand(cls, demand: str, directive: str = "") -> bool:
        """判定玩家需求或戰術指示是否表達了接管操作或長出手之意圖"""
        text = f"{demand} {directive}".lower()
        if any(kw in text for kw in cls.TAKEYOVER_KEYWORDS):
            return True
        if "推薦輸入序列" in text or "推薦技能序列" in text or "推薦操作" in text:
            return True
        return False

    @classmethod
    def extract_sequence(
        cls,
        text: str,
        user_demand: str = "",
        game_type: GameType = GameType.GENSHIN
    ) -> List[ActionStep]:
        """
        從文字中抽取連續動作步驟清單
        優先檢索 Directive 中的「推薦輸入序列」或「推薦技能序列」段落
        """
        steps: List[ActionStep] = []
        combined_text = f"{text}\n{user_demand}"

        # 1. 尋找序列核心區塊
        seq_block = ""
        patterns = [
            r"(?:推薦輸入序列|推薦技能序列|推薦操作|執行序列|技能順序)[:：\s]+([\s\S]+?)(?=\n\s*\d+\.|\n\s*3\.|\n\s*警戒條件|\Z)",
            r"(?:切換.*?[-\w➔→>].*?)(?=\n\n|\Z)"
        ]
        for pat in patterns:
            m = re.search(pat, combined_text, re.MULTILINE)
            if m:
                seq_block = m.group(1) if m.groups() else m.group(0)
                break

        target_text = seq_block if seq_block.strip() else combined_text

        # 2. 依行或箭頭符號分句切片 (將 - 放在集合最前避免範圍錯誤)
        lines_or_tokens = re.split(r'[-\r\n➔→>]+', target_text)

        for token in lines_or_tokens:
            token = token.strip()
            if not token:
                continue

            # (A) 切換角色判斷 (例如: 切 3 號位 (希諾寧)、切4號位、換2號位)
            match_slot = re.search(r'(?:切|換)?\s*([1-4])\s*號位', token)
            if match_slot:
                slot_num = match_slot.group(1)
                steps.append(ActionStep(
                    action_type="key",
                    target=slot_num,
                    duration=0.05,
                    post_delay=0.25,
                    description=f"切換至 {slot_num} 號位角色"
                ))

            # (B) 戰技 E (例如: E、長按 E、施放戰技)
            if "長按" in token and any(kw in token.lower() for kw in ["e", "戰技"]):
                steps.append(ActionStep(
                    action_type="hold_key",
                    target="e",
                    duration=0.5,
                    post_delay=0.25,
                    description="長按戰技 E 進入強化/驅動模式"
                ))
            elif re.search(r'\b[eE]\b|戰技', token):
                steps.append(ActionStep(
                    action_type="key",
                    target="e",
                    duration=0.08,
                    post_delay=0.3,
                    description="施放戰技 E"
                ))

            # (C) 元素爆發 / 大招 Q (例如: Q、元素爆發、大招、終結技)
            if re.search(r'\b[qQ]\b|爆發|大招|終結技', token):
                steps.append(ActionStep(
                    action_type="key",
                    target="q",
                    duration=0.1,
                    post_delay=0.45,
                    description="施放大招 Q (元素爆發/終結技)"
                ))

            # (D) 普攻 / 平A (例如: 普攻 2 次、連續普攻、平A)
            if "普攻" in token or "平a" in token.lower() or "平砍" in token:
                count_match = re.search(r'(\d+)\s*次', token)
                count = int(count_match.group(1)) if count_match else 2
                count = min(count, 5)
                for i in range(count):
                    steps.append(ActionStep(
                        action_type="click",
                        target="left",
                        duration=0.04,
                        post_delay=0.18,
                        description=f"普攻攻擊 ({i+1}/{count})"
                    ))

            # (E) 重擊
            if "重擊" in token:
                steps.append(ActionStep(
                    action_type="hold_click",
                    target="left",
                    duration=0.4,
                    post_delay=0.25,
                    description="蓄力重擊"
                ))

            # (F) 閃避 / 衝刺 (取消後搖)
            if "閃避" in token or "衝刺" in token or "shift" in token.lower():
                steps.append(ActionStep(
                    action_type="key",
                    target="shift",
                    duration=0.04,
                    post_delay=0.15,
                    description="極限閃避 / 衝刺打斷後搖"
                ))

            # (G) 支援突擊 / 招架 (絕區零 Space / C)
            if "招架" in token or "支援突擊" in token:
                steps.append(ActionStep(
                    action_type="key",
                    target="space",
                    duration=0.05,
                    post_delay=0.2,
                    description="極限招架反擊 / 支援突擊"
                ))

            # (H) 拾取互動 F
            if "拾取" in token or "採集" in token or re.search(r'\b[fF]\b', token):
                steps.append(ActionStep(
                    action_type="key",
                    target="f",
                    duration=0.03,
                    post_delay=0.1,
                    description="互動拾取"
                ))

        # 3. 兜底保障：若未成功抓出特定步驟，提供各遊戲最經典的預設爆發宏
        if not steps:
            steps = cls._get_default_steps(game_type)

        return steps

    @classmethod
    def _get_default_steps(cls, game_type: GameType) -> List[ActionStep]:
        """遊戲專屬預設戰術接管動作序列"""
        if game_type == GameType.GENSHIN:
            # 輔助掛屬 ➔ 副C增益 ➔ 主C核爆爆發
            return [
                ActionStep("key", "3", 0.05, 0.25, "切 3 號位輔助"),
                ActionStep("key", "e", 0.08, 0.3, "施放戰技 E 掛屬"),
                ActionStep("click", "left", 0.04, 0.15, "普攻補能量"),
                ActionStep("key", "4", 0.05, 0.25, "切 4 號位副C"),
                ActionStep("key", "e", 0.08, 0.3, "副C戰技 E"),
                ActionStep("key", "q", 0.1, 0.45, "副C大招 Q 增傷"),
                ActionStep("key", "1", 0.05, 0.25, "切 1 號位主 C"),
                ActionStep("key", "q", 0.1, 0.5, "主 C 大招 Q 核爆"),
                ActionStep("key", "e", 0.08, 0.25, "主 C 戰技 E 連招"),
                ActionStep("click", "left", 0.04, 0.15, "連續平 A 壓制")
            ]
        elif game_type == GameType.STAR_RAIL:
            # 戰技破韌 ➔ 終結技插隊
            return [
                ActionStep("key", "e", 0.08, 0.4, "釋放戰技 (消耗 SP 破弱點)"),
                ActionStep("key", "q", 0.1, 0.5, "插隊釋放終結技")
            ]
        elif game_type == GameType.ZZZ:
            # 支援招架 ➔ 連攜技 ➔ 終結技
            return [
                ActionStep("key", "space", 0.05, 0.25, "招架支援突擊"),
                ActionStep("key", "e", 0.08, 0.35, "特殊技 E 累積失衡"),
                ActionStep("click", "left", 0.04, 0.15, "普攻連段"),
                ActionStep("key", "q", 0.1, 0.5, "連攜終結技爆發")
            ]
        else:
            return [
                ActionStep("key", "1", 0.05, 0.2, "切換 1 號武器/技能"),
                ActionStep("key", "e", 0.08, 0.3, "釋放主力技能"),
                ActionStep("click", "left", 0.04, 0.15, "普攻攻擊")
            ]
