from typing import Dict, Optional, List
from config import GameType
from strategies.base import BaseGameStrategy
from strategies.genshin import GenshinStrategy
from strategies.star_rail import StarRailStrategy
from strategies.zzz import ZZZStrategy
from strategies.general import GeneralGameStrategy


class StrategyRegistry:
    """
    遊戲策略註冊中心 (Strategy Registry & Factory)
    管理原神、星穹鐵道、絕區零及泛用遊戲策略，並支援未來任意新遊戲的動態擴充。
    """
    _strategies: Dict[GameType, BaseGameStrategy] = {}

    @classmethod
    def register(cls, game_type: GameType, strategy: BaseGameStrategy):
        """
        註冊新遊戲輔助策略 (保留未來其他遊戲之擴充能力)
        :param game_type: 遊戲類型枚舉或字串
        :param strategy: 繼承 BaseGameStrategy 的策略實例
        """
        cls._strategies[game_type] = strategy

    @classmethod
    def get(cls, game_type: GameType) -> BaseGameStrategy:
        """
        取得指定遊戲之策略實例；若未命中則自動降級為 GeneralGameStrategy
        """
        if not cls._strategies:
            cls.initialize_default_strategies()

        if game_type in cls._strategies:
            return cls._strategies[game_type]

        # 嘗試以 value 或 string 比對
        for k, v in cls._strategies.items():
            if k == game_type or k.value == getattr(game_type, "value", str(game_type)):
                return v

        return cls._strategies.get(GameType.GENERAL, GeneralGameStrategy())

    @classmethod
    def list_available(cls) -> List[GameType]:
        if not cls._strategies:
            cls.initialize_default_strategies()
        return list(cls._strategies.keys())

    @classmethod
    def initialize_default_strategies(cls):
        """初始化預設策略：原神、星穹鐵道、絕區零、泛用遊戲"""
        cls._strategies.clear()
        cls.register(GameType.GENSHIN, GenshinStrategy())
        cls.register(GameType.STAR_RAIL, StarRailStrategy())
        cls.register(GameType.ZZZ, ZZZStrategy())
        cls.register(GameType.GENERAL, GeneralGameStrategy())


# 模組載入時自動初始化預設策略
StrategyRegistry.initialize_default_strategies()


def get_game_strategy(game_type: GameType) -> BaseGameStrategy:
    """便利取得策略函數"""
    return StrategyRegistry.get(game_type)
