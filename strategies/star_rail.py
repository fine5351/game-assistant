import time
from typing import Dict, Any, List
from PIL import Image

from config import GameType, AssistCapability
from jev_engine import Choice, Noul, Score, JevResponse
from input_actuator import ScreenActuator
from strategies.base import (
    BaseGameStrategy, TelemetryData, ActionResult, StrategyDecision
)


class StarRailStrategy(BaseGameStrategy):
    """
    《崩壞：星穹鐵道》即時回合制輔助策略
    專精：戰技點 (SP) 配額平衡、終結技立即插隊破韌 (1-4)、弱點屬性打擊與模擬宇宙事件決策。
    支援操作指導、螢幕代替操作、回合與遺器數據分析。
    """

    @property
    def game_type(self) -> GameType:
        return GameType.STAR_RAIL

    @property
    def name(self) -> str:
        return "崩壞：星穹鐵道 (Honkai: Star Rail)"

    def extract_telemetry(self, image: Image.Image, visual_context: str = "") -> TelemetryData:
        now = time.time()
        ctx_lower = visual_context.lower()

        sp_count = 3
        if "sp不足" in visual_context or "sp: 0" in ctx_lower or "sp: 1" in ctx_lower:
            sp_count = 1

        ult_ready = ("終結技" in visual_context or "ult_ready" in ctx_lower)

        return TelemetryData(
            timestamp=now,
            game_type=self.game_type,
            in_combat=True,
            player_hp_ratio=0.85,
            energy_ready=ult_ready,
            cooldown_ready=(sp_count > 1),
            danger_detected=("boss蓄力" in visual_context or "高威脅" in visual_context),
            threat_level=0.4,
            active_character="1",
            features={
                "sp": sp_count,
                "ult_available": [1] if ult_ready else [],
                "target_weakness": "雷 / 量子"
            }
        )

    def build_jev_questions(self, capability: AssistCapability, context: Dict[str, Any]) -> Dict[str, Any]:
        questions = {
            "tactical_action": Choice(
                instructions="在星穹鐵道當前行動輪次回合中，選擇最佳操作：",
                criteria={
                    "skill_e": None,               # 消耗 SP 施放戰技 (E)
                    "basic_attack_q": None,        # 施放普攻回覆 SP (Q)
                    "ultimate_1": None,            # 1 號位終結技插隊 (按鍵 1)
                    "ultimate_2": None,            # 2 號位終結技插隊 (按鍵 2)
                    "ultimate_3": None,            # 3 號位終結技插隊 (按鍵 3)
                    "ultimate_4": None,            # 4 號位終結技插隊 (按鍵 4)
                    "confirm_action": None,        # 確認施放/點擊目標 (Space / 左鍵)
                    "idle": None                   # 等待動畫或對手輪次
                }
            ),
            "should_interrupt_ultimate": Noul(
                instructions="是否有角色的終結技能量已滿，且當前輪次適合立即插隊破韌或開盾？"
            ),
            "sp_urgency": Score(
                instructions="戰技點 (SP) 緊繃程度評分",
                criteria=["充裕 (3-5點)", "平衡 (2點)", "匱乏 (0-1點)"]
            )
        }

        if capability == AssistCapability.DATA_ANALYSIS:
            questions["combat_phase"] = Choice(
                instructions="當前星穹鐵道戰鬥輪次評估：",
                options=["weakness_break", "sp_generation", "dps_burst", "defensive_heal"]
            )
            questions["rotation_efficiency"] = Score(
                instructions="戰技點與終結技施放整體效率評分",
                criteria=["緊缺", "平衡", "完美"]
            )
            questions["needs_optimization"] = Noul(
                instructions="隊伍戰技點收支是否失衡需要立即調整？"
            )

        return questions

    def build_jev_state(
        self,
        telemetry: TelemetryData,
        gemini_directive: str,
        user_demand: str,
        capability: AssistCapability
    ) -> str:
        sp = telemetry.features.get("sp", 3)
        weakness = telemetry.features.get("target_weakness", "未知")

        state_parts = [
            f"[Game]: {self.name}",
            f"[Mode]: {capability.value}",
            f"[Turn State]: in_combat=True, SP_remaining={sp}, TargetWeakness={weakness}",
            f"[Ultimate Ready]: {telemetry.energy_ready}"
        ]
        if telemetry.danger_detected:
            state_parts.append("[ALERT]: 敵方 Boss 正處於鎖定蓄力狀態！")
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

        ult_noul = jev_response.nouls.get("should_interrupt_ultimate")
        should_ult = ult_noul.noul if ult_noul else False
        if should_ult and telemetry.energy_ready:
            primary_action = "ultimate_1"

        sp_score = jev_response.scores.get("sp_urgency")
        urgency = sp_score.score if sp_score else 0.4

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
            "ultimate_1": "💥 **終結技破韌插隊**：立即按下 【1】 插入 1 號位大招破韌！",
            "ultimate_2": "💥 **終結技破韌插隊**：立即按下 【2】 插入 2 號位大招！",
            "ultimate_3": "🛡️ **輔助大招插隊**：立即按下 【3】 施放輔助大招拉條/補Buff！",
            "ultimate_4": "💚 **救急大招插隊**：立即按下 【4】 施放全隊治療或護盾！",
            "skill_e": "⚡ **戰技爆發**：SP 充裕，按下 【E】 施放戰技！",
            "basic_attack_q": "🔋 **回覆戰技點**：按下 【Q】 普攻補充 SP 給核心角色！",
            "confirm_action": "🎯 **確認目標**：按下 【Space】 或點擊確認行動！",
            "idle": "⏳ **等待輪次**：敵我行動結算中，觀察行動條排序。"
        }
        guidance_text = guidance_map.get(primary_action, f"建議操作: {primary_action}")

        return StrategyDecision(
            primary_action=primary_action,
            confidence=confidence,
            urgency=urgency,
            should_evade=False,
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

        if act == "skill_e":
            target = "e"
            executed = actuator.press_key("e", hold_sec=0.06)
        elif act == "basic_attack_q":
            target = "q"
            executed = actuator.press_key("q", hold_sec=0.06)
        elif act.startswith("ultimate_"):
            slot = act.split("_")[-1]
            target = slot
            executed = actuator.press_key(slot, hold_sec=0.06)
        elif act == "confirm_action":
            target = "space"
            executed = actuator.press_key("space", hold_sec=0.05)
        else:
            return ActionResult(
                action_type=act,
                target_key_or_button="IDLE",
                executed=True,
                message="等待輪次，無需操作"
            )

        latency = (time.perf_counter() - start_t) * 1000.0
        msg = f"已發送崩鐵螢幕操作：[{target}]" if executed else f"螢幕操作冷卻中：[{target}]"
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
            return "尚無回合戰鬥數據。"

        avg_sp = sum(t.features.get("sp", 0) for t in telemetry_history) / count

        return (
            f"### 📊 《崩壞：星穹鐵道》實時戰況遙測分析 (取樣 {count} 幀)\n\n"
            f"- **平均戰技點 (SP) 儲備**：`{avg_sp:.1f}` / 5.0\n"
            f"- **行動點循環評估**：{'🟢 戰技點收支健康' if avg_sp >= 2.0 else '🔴 戰技點緊缺，請多用普攻產點'}\n"
            f"- **擊破韌性建議**：鎖定弱點屬性角色進行削韌破防。"
        )
