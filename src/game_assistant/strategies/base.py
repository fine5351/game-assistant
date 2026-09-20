import abc
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from PIL import Image

from game_assistant.core.config import GameType, AssistCapability
from game_assistant.engines.jev_engine import Choice, Noul, Score, JevResponse
from game_assistant.utils.input_actuator import ScreenActuator


@dataclass
class TelemetryData:
    """實時抽取之畫面遙測資料 (0.25s 輕量特徵)"""
    timestamp: float
    game_type: GameType
    in_combat: bool = False
    player_hp_ratio: float = 1.0
    energy_ready: bool = False
    cooldown_ready: bool = True
    danger_detected: bool = False
    threat_level: float = 0.0
    active_character: str = "1"
    # 擴充：探索蒐集與裝備強化專屬遙測特徵
    target_name: str = ""
    has_interactive_target: bool = False
    gear_score: float = 0.0
    upgrade_potential: float = 0.0
    recommended_action: str = ""
    features: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    """螢幕操作執行結果"""
    action_type: str
    target_key_or_button: str
    executed: bool
    latency_ms: float = 0.0
    message: str = ""


@dataclass
class StrategyDecision:
    """策略統合決策結構"""
    primary_action: str
    confidence: float
    urgency: float
    should_evade: bool
    guidance_text: str
    telemetry: TelemetryData
    raw_jev: JevResponse
    action_result: Optional[ActionResult] = None


class BaseGameStrategy(abc.ABC):
    """
    遊戲輔助策略抽象基底類別 (Strategy Pattern)
    所有遊戲（原神、崩鐵、絕區零、通用遊戲與未來擴充遊戲）皆需繼承此類別。
    提供：
    1. 0.25s 實時畫面特徵/遙測抽取
    2. Jev System 1 決策 Schema 定義 (Choice, Noul, Score)
    3. 實時操作指導 (Guidance HUD) 產出
    4. 實時螢幕代替操作 (Screen Actuation) 執行
    5. 實時資料分析 (Data Telemetry) 統計
    6. Gemini System 2 認知 Prompt 整合
    """

    @property
    @abc.abstractmethod
    def game_type(self) -> GameType:
        """策略所屬之遊戲類型枚舉"""
        pass

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """策略名稱"""
        pass

    @abc.abstractmethod
    def extract_telemetry(self, image: Image.Image, visual_context: str = "") -> TelemetryData:
        """
        從 0.25 秒快照畫面中抽取輕量化遊戲狀態遙測數據 (低於 15ms)
        :param image: PIL 截圖
        :param visual_context: 可選之 Gemini 視覺分析或歷史上下文
        """
        pass

    @abc.abstractmethod
    def build_jev_questions(self, capability: AssistCapability, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        建構給 Jev 模型進行 System 1 決策的問題結構 (Choice, Noul, Score)
        """
        pass

    @abc.abstractmethod
    def build_jev_state(
        self,
        telemetry: TelemetryData,
        gemini_directive: str,
        user_demand: str,
        capability: AssistCapability
    ) -> str:
        """
        將遙測數據、Gemini 戰術指示與玩家需求整合為 Jev 的狀態字串
        """
        pass

    @abc.abstractmethod
    def interpret_decision(
        self,
        jev_response: JevResponse,
        telemetry: TelemetryData,
        capability: AssistCapability
    ) -> StrategyDecision:
        """
        解析 Jev 的 Choice/Noul/Score，產出具體的戰術建議與行動決策
        """
        pass

    @abc.abstractmethod
    def execute_action(
        self,
        decision: StrategyDecision,
        actuator: ScreenActuator
    ) -> ActionResult:
        """
        執行代替操作：將 Jev 決策轉譯為鍵盤/滑鼠螢幕操作
        """
        pass

    @abc.abstractmethod
    def format_analysis(self, telemetry_history: List[TelemetryData]) -> str:
        """
        資料分析能力：產生即時戰況數據、反應統計與效能分析報告 (Markdown 格式)
        """
        pass

    def get_gemini_auxiliary_prompt(self, user_demand: str, capability: AssistCapability) -> str:
        """
        供 Gemini (System 2) 解析使用者需求與制定高階戰術意圖的 Prompt 範本
        """
        cap_name = getattr(capability, "value", str(capability))
        return (
            f"你是《{self.name}》的高級戰術顧問。\n"
            f"玩家目前的輔助模式是：【{cap_name}】。\n"
            f"玩家提出的具體需求是：【{user_demand}】。\n"
            "請將玩家的需求拆解為明確、可供即時決策執行的微觀指令。\n"
            "格式請條列出：1. 戰術目標 2. 推薦按鍵/操作序列 3. 觸發時機或防禦要點。以繁體中文簡明回答。"
        )
