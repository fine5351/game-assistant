"""
器官註冊與生命週期管理中心 (Organ Registry)
管理神經系統所有的眼睛、耳朵、手與腳，支援自律生長、熱插拔與動態掛載。
"""

import os
import glob
from typing import Dict, Any, List, Optional
from game_assistant.organs.base import BaseOrganTool, OrganType
from game_assistant.organs.sensory import (
    EnemyStanceWatcherEye,
    BossSoundWarningEar,
    WebIntelligenceEar
)
from game_assistant.organs.actuator import (
    DodgeCancelHand,
    ElementalComboHand,
    AutoLootSprintFoot
)
from game_assistant.organs.synthesizer import OrganSynthesizer
from game_assistant.utils.input_actuator import ScreenActuator
from game_assistant.sensory.web_sensory import WebSensoryGatherer


class OrganRegistry:
    """
    器官工具註冊中心 (Organ Registry)
    統籌所有感官工具與致動工具，並負責動態生長與持久化載入。
    """

    def __init__(
        self,
        storage_dir: str = "data/dynamic_organs",
        actuator: Optional[ScreenActuator] = None,
        gatherer: Optional[WebSensoryGatherer] = None,
        synthesizer: Optional[OrganSynthesizer] = None
    ):
        self.storage_dir = storage_dir
        self.actuator = actuator
        self.gatherer = gatherer
        self.synthesizer = synthesizer or OrganSynthesizer(storage_dir=storage_dir)
        self._organs: Dict[str, BaseOrganTool] = {}

        # 1. 註冊預裝內建器官
        self._register_built_in_organs()

        # 2. 自動載入先前已生長之動態器官
        self._load_persisted_dynamic_organs()

    def _register_built_in_organs(self) -> None:
        """載入神經系統內建感官與致動器官"""
        built_ins = [
            EnemyStanceWatcherEye(),
            BossSoundWarningEar(),
            WebIntelligenceEar(gatherer=self.gatherer),
            DodgeCancelHand(actuator=self.actuator),
            ElementalComboHand(actuator=self.actuator),
            AutoLootSprintFoot(actuator=self.actuator)
        ]
        for organ in built_ins:
            self.register_organ(organ)

    def _load_persisted_dynamic_organs(self) -> None:
        """從磁碟載入先前自律生長之動態器官代碼"""
        if not os.path.exists(self.storage_dir):
            return

        for file_path in glob.glob(os.path.join(self.storage_dir, "*.py")):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    code = f.read()
                organ_id = os.path.splitext(os.path.basename(file_path))[0]
                # 安全審查並動態編譯
                self.synthesizer.guard.inspect_code(code)
                organ = self.synthesizer._load_organ_from_code(code, organ_id)
                self.register_organ(organ)
            except Exception:
                pass

    def register_organ(self, organ: BaseOrganTool) -> None:
        """註冊器官至中心"""
        self._organs[organ.organ_id] = organ

    def unregister_organ(self, organ_id: str) -> Optional[BaseOrganTool]:
        """註銷器官"""
        return self._organs.pop(organ_id, None)

    def get_organ(self, organ_id: str) -> Optional[BaseOrganTool]:
        """取得指定器官"""
        return self._organs.get(organ_id)

    def get_organs_by_type(self, organ_type: OrganType) -> List[BaseOrganTool]:
        """依類別（眼/耳/手/腳）取得器官清單"""
        return [org for org in self._organs.values() if org.organ_type == organ_type]

    def list_all_organs(self) -> List[BaseOrganTool]:
        """取得所有已掛載器官"""
        return list(self._organs.values())

    def grow_organ(
        self,
        requirement: str,
        organ_type: OrganType,
        name: str,
        organ_id: Optional[str] = None
    ) -> BaseOrganTool:
        """
        自律演化生長新器官工具
        由 Synthesizer 編寫、安全審查、編譯後立即掛載進註冊中心
        """
        new_organ = self.synthesizer.synthesize_organ(
            requirement=requirement,
            organ_type=organ_type,
            name=name,
            organ_id=organ_id
        )
        self.register_organ(new_organ)
        return new_organ

    def collect_all_predicates(self) -> Dict[str, Any]:
        """
        彙整當前所有感官器官（眼睛與耳朵）的最新 Predicates 供 Jev 評判
        """
        predicates = {}
        for organ in self._organs.values():
            if organ.organ_type in (OrganType.SENSORY_EYE, OrganType.SENSORY_EAR):
                try:
                    preds = organ.extract_predicates()
                    predicates.update(preds)
                except Exception:
                    pass
        return predicates

    def get_summary(self) -> Dict[str, Any]:
        """產出供 GUI HUD 與統計面板顯示之器官狀態摘要"""
        eyes = self.get_organs_by_type(OrganType.SENSORY_EYE)
        ears = self.get_organs_by_type(OrganType.SENSORY_EAR)
        hands = self.get_organs_by_type(OrganType.ACTUATOR_HAND)
        feet = self.get_organs_by_type(OrganType.ACTUATOR_FOOT)

        return {
            "total_count": len(self._organs),
            "eyes_count": len(eyes),
            "ears_count": len(ears),
            "hands_count": len(hands),
            "feet_count": len(feet),
            "dynamic_grown_count": sum(1 for o in self._organs.values() if not o.is_built_in),
            "organs": [o.to_dict() for o in self._organs.values()]
        }
