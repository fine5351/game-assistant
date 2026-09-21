"""
預裝感官器官 (Sensory Organs: Eyes and Ears)
包含視覺失衡監控眼、首領大招警報耳與網路情報耳。
"""

from typing import Dict, Any, Optional
from game_assistant.organs.base import BaseOrganTool, OrganType
from game_assistant.sensory.web_sensory import WebSensoryGatherer
from game_assistant.core.config import GameType


class EnemyStanceWatcherEye(BaseOrganTool):
    """
    視覺感官眼：敵方硬直與失衡值監控器官 (Enemy Stance & Stun Watcher)
    負責從畫面特徵或戰鬥遙測中，即時偵測敵方是否進入失衡、虛弱或蓄力狀態。
    """

    def __init__(self, organ_id: str = "eye_enemy_stance"):
        super().__init__(
            organ_id=organ_id,
            organ_type=OrganType.SENSORY_EYE,
            name="敵方失衡姿態監控眼",
            description="即時觀察敵方失衡值(Daze)與虛弱狀態，捕捉全力爆發輸出或連攜時機",
            is_built_in=True
        )

    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        分析傳入的戰況資料或畫面特徵
        支援參數: break_gauge (0.0~1.0), is_stunned (bool), boss_action (str)
        """
        self.execution_count += 1
        break_gauge = float(kwargs.get("break_gauge", 0.0))
        is_stunned = bool(kwargs.get("is_stunned", False) or break_gauge >= 1.0)
        boss_action = str(kwargs.get("boss_action", "normal"))

        status = "normal"
        if is_stunned:
            status = "stunned_vulnerable"
        elif break_gauge >= 0.8:
            status = "near_break"
        elif "charging" in boss_action:
            status = "charging"

        result = {
            "target_stunned": is_stunned,
            "break_gauge": break_gauge,
            "status": status,
            "recommendation": "連攜爆發輸出" if is_stunned else ("持續削韌" if status == "near_break" else "常規戰術循環")
        }
        self.last_result = result
        return result

    def extract_predicates(self, **kwargs) -> Dict[str, Any]:
        result = self.execute(**kwargs) if not self.last_result else self.last_result
        return {
            "is_target_stunned": result["target_stunned"],
            "target_status": result["status"],
            "stance_break_ratio": result["break_gauge"]
        }


class BossSoundWarningEar(BaseOrganTool):
    """
    聽覺感官耳：首領大招危險警報監聽器官 (Boss Sound & Danger Warning Ear)
    負責偵測戰場高頻警報音效、前奏蓄力音或極限閃避提示音。
    """

    def __init__(self, organ_id: str = "ear_boss_warning"):
        super().__init__(
            organ_id=organ_id,
            organ_type=OrganType.SENSORY_EAR,
            name="首領危險前奏警報耳",
            description="監聽戰場強敵大招釋放前置音效、蓄力提示音與閃避時機指示",
            is_built_in=True
        )

    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        分析戰況音訊線索或危險信號
        支援參數: sound_cue (str), danger_level (str), visual_flash (str)
        """
        self.execution_count += 1
        sound_cue = str(kwargs.get("sound_cue", "")).lower()
        danger_level = str(kwargs.get("danger_level", "low")).lower()
        visual_flash = str(kwargs.get("visual_flash", "")).lower()

        is_ult = any(k in sound_cue for k in ["警報", "alarm", "siren", "charging_high", "bell", "鐘鳴", "大招"])
        flash_danger = "red" in visual_flash or "黃光" in visual_flash or "yellow" in visual_flash

        incoming_danger = is_ult or flash_danger or danger_level in ["high", "critical", "danger"]
        action = "none"
        if incoming_danger:
            if "yellow" in visual_flash or "黃光" in visual_flash:
                action = "parry_switch"   # 彈刀換人
            else:
                action = "dodge_invincible" # 極限無敵幀閃避

        result = {
            "boss_ult_incoming": incoming_danger,
            "danger_level": "critical" if incoming_danger else danger_level,
            "suggested_action": action,
            "cue_detected": sound_cue or visual_flash or "none"
        }
        self.last_result = result
        return result

    def extract_predicates(self, **kwargs) -> Dict[str, Any]:
        result = self.execute(**kwargs) if not self.last_result else self.last_result
        return {
            "boss_ult_incoming": result["boss_ult_incoming"],
            "danger_level": result["danger_level"],
            "evade_required": result["suggested_action"] != "none"
        }


class WebIntelligenceEar(BaseOrganTool):
    """
    網路情報感官耳：主動聯網查詢與聆聽遊戲攻略百科情報
    """

    def __init__(self, gatherer: Optional[WebSensoryGatherer] = None, organ_id: str = "ear_web_intel"):
        super().__init__(
            organ_id=organ_id,
            organ_type=OrganType.SENSORY_EAR,
            name="全域網路情報聆聽耳",
            description="自主聯網獲取最新遊戲攻略、角色培育配裝與大世界地圖機制百科",
            is_built_in=True
        )
        self.gatherer = gatherer or WebSensoryGatherer()

    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        支援參數: query (str), char_name (str), game_type (GameType)
        """
        self.execution_count += 1
        query = kwargs.get("query", "")
        char_name = kwargs.get("char_name", "")
        game_type = kwargs.get("game_type")

        if char_name:
            data = self.gatherer.fetch_character_build_guide(char_name, game_type)
        elif query:
            results = self.gatherer.search_game_knowledge(query, game_type)
            data = {"results": results, "top_hit": results[0] if results else {}}
        else:
            data = {"status": "no_query_provided"}

        self.last_result = data
        return data

    def extract_predicates(self, **kwargs) -> Dict[str, Any]:
        if not self.last_result:
            return {"has_web_intel": False}
        return {
            "has_web_intel": True,
            "intel_summary": self.gatherer.summarize_for_jev(self.last_result)
        }
