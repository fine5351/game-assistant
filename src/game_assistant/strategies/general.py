import time
from typing import Dict, Any, List
from PIL import Image

from game_assistant.core.config import GameType, AssistCapability
from game_assistant.engines.jev_engine import Choice, Noul, Score, JevResponse
from game_assistant.utils.input_actuator import ScreenActuator
from game_assistant.strategies.base import (
    BaseGameStrategy, TelemetryData, ActionResult, StrategyDecision
)


class GeneralGameStrategy(BaseGameStrategy):
    """
    泛用遊戲策略 (General Game Agent Strategy)
    作為通用遊戲 Agent 的基底策略，支援各類 2D/3D、動作、RPG 或射擊遊戲。
    具備 WASD 走位、滑鼠主副操作 (攻擊/瞄準)、跳躍 (Space)、閃避 (Shift)、技能鍵 (Q/E/R/F/1-4) 等泛用操作與分析。
    """

    @property
    def game_type(self) -> GameType:
        return GameType.GENERAL

    @property
    def name(self) -> str:
        return "泛用遊戲模式 (General Game)"

    def extract_telemetry(self, image: Image.Image, visual_context: str = "") -> TelemetryData:
        now = time.time()
        ctx_lower = visual_context.lower()

        danger = ("危險" in visual_context or "attack" in ctx_lower or "danger" in ctx_lower)
        threat = 0.7 if danger else 0.2

        return TelemetryData(
            timestamp=now,
            game_type=self.game_type,
            in_combat=True,
            player_hp_ratio=0.75,
            energy_ready=True,
            cooldown_ready=True,
            danger_detected=danger,
            threat_level=threat,
            active_character="Main",
            features={
                "crosshair_aligned": ("準星" in visual_context or "target_locked" in ctx_lower),
                "resource_ok": True
            }
        )

    def build_jev_questions(self, capability: AssistCapability, context: Dict[str, Any]) -> Dict[str, Any]:
        questions = {
            "tactical_action": Choice(
                instructions="在當前通用遊戲畫面中，判斷最合理的操作動作：",
                criteria={
                    "primary_action": None,       # 主要動作 / 攻擊 (左鍵)
                    "secondary_action": None,     # 次要動作 / 瞄準/防禦 (右鍵)
                    "use_skill_1": None,          # 技能 1 (E)
                    "use_skill_2": None,          # 技能 2 (Q)
                    "use_ultimate": None,         # 大招 / 爆發 (R)
                    "interact": None,             # 互動 / 拾取 (F)
                    "jump": None,                 # 跳躍 (Space)
                    "dodge": None,                # 翻滾 / 閃避 / 衝刺 (Shift)
                    "idle": None                  # 保持當前狀態
                }
            ),
            "threat_alert": Noul(
                instructions="畫面中是否偵測到即將造成傷害的攻擊或障礙？"
            ),
            "action_confidence": Score(
                instructions="當前動作優先級評分",
                criteria=["常規行動", "戰術優化", "極限關鍵操作"]
            )
        }

        if capability == AssistCapability.DATA_ANALYSIS:
            questions["combat_phase"] = Choice(
                instructions="通用遊戲當前戰鬥環境節奏：",
                options=["engagement", "skill_burst", "repositioning", "peaceful_exploration"]
            )
            questions["rotation_efficiency"] = Score(
                instructions="操作連續性與走位流暢度評分",
                criteria=["生疏", "熟練", "精準流暢"]
            )
            questions["needs_optimization"] = Noul(
                instructions="當前操作節奏是否存在改進空間？"
            )

        return questions

    def build_jev_state(
        self,
        telemetry: TelemetryData,
        gemini_directive: str,
        user_demand: str,
        capability: AssistCapability
    ) -> str:
        state_parts = [
            f"[Game]: {self.name}",
            f"[Mode]: {getattr(capability, 'value', str(capability))}",
            f"[Threat Level]: {telemetry.threat_level:.2f}, DangerAlert={telemetry.danger_detected}"
        ]
        if gemini_directive:
            state_parts.append(f"[Gemini Strategy Directive]: {gemini_directive}")
        if user_demand:
            state_parts.append(f"[User Demand]: {user_demand}")

        return "\n".join(state_parts)

    def interpret_decision(
        self,
        jev_response: JevResponse,
        telemetry: TelemetryData,
        capability: AssistCapability
    ) -> StrategyDecision:
        action_choice = jev_response.choices.get("tactical_action")
        primary_action = action_choice.choice if action_choice else "idle"
        confidence = action_choice.confidence if action_choice else 0.5

        threat_noul = jev_response.nouls.get("threat_alert")
        should_evade = threat_noul.noul if threat_noul else False
        if should_evade:
            primary_action = "dodge"

        conf_score = jev_response.scores.get("action_confidence")
        urgency = conf_score.score if conf_score else 0.5

        if capability == AssistCapability.DATA_ANALYSIS:
            phase_choice = jev_response.choices.get("combat_phase")
            eff_score = jev_response.scores.get("rotation_efficiency")
            opt_noul = jev_response.nouls.get("needs_optimization")
            if phase_choice:
                telemetry.features["combat_phase"] = phase_choice.choice
            if eff_score:
                telemetry.features["efficiency_score"] = eff_score.score
            if opt_noul:
                telemetry.features["needs_optimization"] = opt_noul.noul

        guidance_map = {
            "dodge": "⚠️ **閃避警示**：按 【Shift / 翻滾】 閃避威脅！",
            "primary_action": "⚔️ **主要動作**：點擊 【滑鼠左鍵】 執行主要攻擊/動作！",
            "secondary_action": "🛡️ **次要動作**：點擊 【滑鼠右鍵】 進行防禦/精準瞄準！",
            "use_skill_1": "⚡ **技能釋放**：按下 【E】 釋放核心技能！",
            "use_skill_2": "⚡ **技能釋放**：按下 【Q】 釋放次要技能！",
            "use_ultimate": "💥 **絕招爆發**：按下 【R】 施放終極爆發！",
            "interact": "🖐️ **環境互動**：按下 【F】 拾取或觸發機關！",
            "jump": "🦘 **機動跳躍**：按下 【Space】 跳躍躲避地面攻擊！",
            "idle": "👀 **穩定觀察**：觀察目標動態。"
        }
        guidance_text = guidance_map.get(primary_action, f"建議操作: {primary_action}")

        return StrategyDecision(
            primary_action=primary_action,
            confidence=confidence,
            urgency=urgency,
            should_evade=should_evade,
            guidance_text=guidance_text,
            telemetry=telemetry,
            raw_jev=jev_response
        )

    def execute_action(
        self,
        decision: StrategyDecision,
        actuator: ScreenActuator
    ) -> ActionResult:
        start_t = time.perf_counter()
        act = decision.primary_action

        if not actuator.is_enabled:
            return ActionResult(
                action_type=act,
                target_key_or_button="NONE",
                executed=False,
                message="代替操作未開啓 (處於操作指導模式)"
            )

        executed = False
        target = ""

        if act == "dodge":
            target = "shift"
            executed = actuator.press_key("shift", hold_sec=0.06)
        elif act == "primary_action":
            target = "left_click"
            executed = actuator.click_mouse("left", count=1)
        elif act == "secondary_action":
            target = "right_click"
            executed = actuator.click_mouse("right", count=1)
        elif act == "use_skill_1":
            target = "e"
            executed = actuator.press_key("e", hold_sec=0.05)
        elif act == "use_skill_2":
            target = "q"
            executed = actuator.press_key("q", hold_sec=0.05)
        elif act == "use_ultimate":
            target = "r"
            executed = actuator.press_key("r", hold_sec=0.06)
        elif act == "interact":
            target = "f"
            executed = actuator.press_key("f", hold_sec=0.05)
        elif act == "jump":
            target = "space"
            executed = actuator.press_key("space", hold_sec=0.05)
        else:
            return ActionResult(
                action_type=act,
                target_key_or_button="IDLE",
                executed=True,
                message="觀察中"
            )

        latency = (time.perf_counter() - start_t) * 1000.0
        msg = f"已發送通用螢幕操作：[{target}]" if executed else f"操作冷卻中：[{target}]"
        return ActionResult(
            action_type=act,
            target_key_or_button=target,
            executed=executed,
            latency_ms=latency,
            message=msg
        )

    def format_analysis(self, telemetry_history: List[TelemetryData]) -> str:
        count = len(telemetry_history)
        if count == 0:
            return "尚無通用戰鬥數據。"

        avg_threat = sum(t.threat_level for t in telemetry_history) / count
        return (
            f"### 📊 《通用遊戲》實時遙測數據 (取樣 {count} 幀)\n\n"
            f"- **平均動態威脅度**：`{avg_threat:.2f}`\n"
            f"- **通用 Agent 狀態**：運行正常，已就緒支援自訂遊戲策略擴充。"
        )
