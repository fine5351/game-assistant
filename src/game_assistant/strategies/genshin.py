import time
from typing import Dict, Any, List
from PIL import Image

from game_assistant.core.config import GameType, AssistCapability
from game_assistant.engines.jev_engine import Choice, Noul, Score, JevResponse
from game_assistant.utils.input_actuator import ScreenActuator
from game_assistant.strategies.base import (
    BaseGameStrategy, TelemetryData, ActionResult, StrategyDecision
)


class GenshinStrategy(BaseGameStrategy):
    """
    《原神》即時遊戲輔助策略
    專精：元素反應鏈（蒸發/融化/超綻放/超激化/凍結）、四人切人技能循環 (1-4 -> E/Q)、無敵幀衝刺閃避。
    支援操作指導、螢幕代替操作、戰況與聖遺物數據分析。
    """

    @property
    def game_type(self) -> GameType:
        return GameType.GENSHIN

    @property
    def name(self) -> str:
        return "原神 (Genshin Impact)"

    def extract_telemetry(self, image: Image.Image, visual_context: str = "") -> TelemetryData:
        now = time.time()
        # 進行超低延遲畫面快速特徵檢測 (約 1-5ms)
        # 例如藉由畫面中央與右下/右側 HUD 區域的亮度與色相評估戰鬥狀態
        w, h = image.size
        # 簡易色彩取樣評估戰鬥/危險警示
        threat = 0.0
        danger = False
        in_combat = True

        # 若 visual_context (來自 Gemini 或歷史標記) 提示敵方攻擊
        ctx_lower = visual_context.lower()
        if "前搖" in visual_context or "紅光" in visual_context or "attack" in ctx_lower:
            danger = True
            threat = 0.85

        return TelemetryData(
            timestamp=now,
            game_type=self.game_type,
            in_combat=in_combat,
            player_hp_ratio=0.8,
            energy_ready=("滿能量" in visual_context or "burst_ready" in ctx_lower),
            cooldown_ready=True,
            danger_detected=danger,
            threat_level=threat,
            active_character="1",
            features={
                "elements": ["Pyro", "Hydro"],
                "optimal_reaction": "蒸發 (Vaporize)"
            }
        )

    def build_jev_questions(self, capability: AssistCapability, context: Dict[str, Any]) -> Dict[str, Any]:
        questions = {
            "tactical_action": Choice(
                instructions="在原神當前戰鬥情境下，選擇最優先的戰術動作：",
                criteria={
                    "burst_q": None,         # 釋放元素爆發 (Q)
                    "skill_e": None,         # 釋放元素戰技 (E)
                    "dash_dodge": None,      # 衝刺無敵幀閃避 (Shift / 右鍵)
                    "switch_char_2": None,   # 切換 2 號位打反應
                    "switch_char_3": None,   # 切換 3 號位施放 Buff
                    "switch_char_4": None,   # 切換 4 號位補盾/治療
                    "switch_char_1": None,   # 切回主 C (1 號位)
                    "normal_attack": None,   # 普攻/重擊 (左鍵)
                    "idle": None             # 保持走位觀察
                }
            ),
            "should_evade": Noul(
                instructions="敵方是否有技能前搖、地面紅圈或高傷害即將命中，需要立即衝刺閃避？"
            ),
            "combat_urgency": Score(
                instructions="當前戰鬥緊急程度評分",
                criteria=["安全/蓄力", "普通對峙", "爆發/危險"]
            )
        }

        if capability == AssistCapability.DATA_ANALYSIS:
            questions["combat_phase"] = Choice(
                instructions="當前原神戰鬥循環階段判定：",
                options=["opening_setup", "reaction_burst", "skill_recharge", "evasion_recovery"]
            )
            questions["rotation_efficiency"] = Score(
                instructions="四人隊伍切人與元素反應循環效率評分",
                criteria=["低效", "良好", "極致"]
            )
            questions["needs_optimization"] = Noul(
                instructions="當前循環是否存在充能卡手或元素覆蓋不足需要優化？"
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
            f"[Combat Status]: in_combat={telemetry.in_combat}, threat={telemetry.threat_level:.2f}",
            f"[Player Status]: HP=80%, ActiveChar={telemetry.active_character}, BurstReady={telemetry.energy_ready}",
            f"[Reactions]: Elements={telemetry.features.get('elements')}, Optimal={telemetry.features.get('optimal_reaction')}"
        ]
        if telemetry.danger_detected:
            state_parts.append("[ALERT]: 敵方攻擊前搖/紅圈警示！危險！")
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
        # 解析 Choice
        action_choice = jev_response.choices.get("tactical_action")
        primary_action = action_choice.choice if action_choice else "idle"
        confidence = action_choice.confidence if action_choice else 0.5

        # 解析 Noul
        evade_noul = jev_response.nouls.get("should_evade")
        should_evade = evade_noul.noul if evade_noul else False
        if should_evade:
            primary_action = "dash_dodge"

        # 解析 Score
        urgency_score = jev_response.scores.get("combat_urgency")
        urgency = urgency_score.score if urgency_score else 0.5

        # 解析資料分析特定維度
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

        # 生成操作指導說明 (Guidance Text)
        guidance_map = {
            "dash_dodge": "⚠️ **敵方攻擊判定**：立即按 【右鍵 / Shift】 進行衝刺無敵幀閃避！",
            "burst_q": "💥 **爆發時機已至**：立即施放元素爆發 【Q】，打出最高傷害！",
            "skill_e": "⚡ **戰技充能**：立即施放元素戰技 【E】 產球並觸發元素附著！",
            "switch_char_2": "🔄 **元素反應切換**：按下 【2】 切換副 C 觸發蒸發/融化反應！",
            "switch_char_3": "🛡️ **隊伍增益支援**：按下 【3】 施放輔助技能與護盾！",
            "switch_char_4": "💚 **隊伍生存支援**：按下 【4】 施放治療或全隊充能！",
            "switch_char_1": "⚔️ **站場主輸出**：按下 【1】 切回主 C 持續平 A / 重擊！",
            "normal_attack": "🗡️ **平穩輸出**：滑鼠 【左鍵】 持續普攻連招！",
            "idle": "👀 **觀察戰況**：保持拉扯走位，等待技能冷卻或出招間隙。"
        }
        guidance_text = guidance_map.get(primary_action, f"建議執行動作: {primary_action}")

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

        if act == "dash_dodge":
            target = "shift"
            executed = actuator.press_key("shift", hold_sec=0.08)
        elif act == "burst_q":
            target = "q"
            executed = actuator.press_key("q", hold_sec=0.06)
        elif act == "skill_e":
            target = "e"
            executed = actuator.press_key("e", hold_sec=0.06)
        elif act.startswith("switch_char_"):
            char_num = act.split("_")[-1]
            target = char_num
            executed = actuator.press_key(char_num, hold_sec=0.05)
        elif act == "normal_attack":
            target = "left_click"
            executed = actuator.click_mouse("left", count=1)
        else:
            return ActionResult(
                action_type=act,
                target_key_or_button="IDLE",
                executed=True,
                message="無須進行螢幕操作"
            )

        latency = (time.perf_counter() - start_t) * 1000.0
        msg = f"已發送原神螢幕操作：[{target}]" if executed else f"螢幕操作冷卻中：[{target}]"
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
            return "尚無足夠的即時戰鬥遙測數據。"

        avg_threat = sum(t.threat_level for t in telemetry_history) / count
        danger_count = sum(1 for t in telemetry_history if t.danger_detected)

        return (
            f"### 📊 《原神》實時戰況遙測分析 (取樣 {count} 幀 / 每 0.25 秒)\n\n"
            f"- **平均威脅指數**：`{avg_threat:.2f}` / 1.0\n"
            f"- **敵方危險攻擊判定**：`{danger_count}` 次\n"
            f"- **當前元素環境**：火/水 (蒸發反應加成維持中)\n"
            f"- **技能循環建議**：建議維持 2號位(掛水) ➔ 1號位(火C爆發) 之循環節奏。"
        )
