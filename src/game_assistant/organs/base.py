"""
神經系統器官工具基底 (Organ Tools Base Module)
定義助理感官器官 (眼睛/耳朵) 與致動器官 (手/腳) 的基本架構與規格介面。
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional


class OrganType(Enum):
    """器官類別列舉"""
    SENSORY_EYE = "眼睛 (視覺感官)"      # 畫面視覺監控、失衡硬直偵測、姿態辨識
    SENSORY_EAR = "耳朵 (聽覺情報感官)"  # 聲音特徵監聽、危險警報、網路百科情報汲取
    ACTUATOR_HAND = "手 (操作致動器)"    # 招式釋放、連招宏、取消後搖、精準彈刀
    ACTUATOR_FOOT = "腳 (導航移動器)"    # 跑圖、自動避險、採集路徑尋路、走位跟隨


class BaseOrganTool(ABC):
    """
    器官工具抽象基底類別
    每一個器官工具都具備感知能力（產生 Jev 可識別的 Predicates）或致動能力（執行行動）。
    """

    def __init__(
        self,
        organ_id: str,
        organ_type: OrganType,
        name: str,
        description: str,
        is_built_in: bool = False
    ):
        self.organ_id = organ_id
        self.organ_type = organ_type
        self.name = name
        self.description = description
        self.is_built_in = is_built_in
        self.execution_count = 0
        self.last_result: Optional[Dict[str, Any]] = None

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        執行器官工具之核心功能
        """
        pass

    def extract_predicates(self, **kwargs) -> Dict[str, Any]:
        """
        提煉結構化特徵 (Predicates)，供 Jev 評判與多層記憶索引消費。
        預設返回最近一次執行的主要特徵。
        """
        if self.last_result:
            return {f"{self.organ_id}_{k}": v for k, v in self.last_result.items() if isinstance(v, (bool, int, float, str))}
        return {}

    def to_dict(self) -> Dict[str, Any]:
        """序列化為字典結構"""
        return {
            "organ_id": self.organ_id,
            "organ_type": self.organ_type.name,
            "type_label": self.organ_type.value,
            "name": self.name,
            "description": self.description,
            "is_built_in": self.is_built_in,
            "execution_count": self.execution_count
        }

    def __repr__(self) -> str:
        return f"<OrganTool [{self.organ_type.name}] {self.name} ({self.organ_id})>"
