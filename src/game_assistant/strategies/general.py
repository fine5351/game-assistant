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
        in_combat = True
        has_interactive = False
        target_name = ""
        gear_score = 0.0
        upgrade_pot = 0.0

        # 通用探索與拾取檢測
        if any(kw in visual_context for kw in ["寶箱", "拾取", "掉落", "採集", "路標", "戰利品", "loot", "chest"]):
            in_combat = False
            has_interactive = True
            if "寶箱" in visual_context or "chest" in ctx_lower:
                target_name = "戰利品寶箱"
            elif "拾取" in visual_context or "掉落" in visual_context or "loot" in ctx_lower:
                target_name = "地面掉落物"
            else:
                target_name = "可互動地物"

        # 通用裝備與強化檢測
        if any(kw in visual_context for kw in ["裝備", "強化", "背包", "裝等", "詞條", "gear", "item", "upgrade"]):
            in_combat = False
            gear_score = 30.0
            upgrade_pot = 0.70

        return TelemetryData(
            timestamp=now,
            game_type=self.game_type,
            in_combat=in_combat,
            player_hp_ratio=0.75,
            energy_ready=True,
            cooldown_ready=True,
            danger_detected=danger,
            threat_level=threat,
            active_character="Main",
            target_name=target_name,
            has_interactive_target=has_interactive,
            gear_score=gear_score,
            upgrade_potential=upgrade_pot,
            features={
                "crosshair_aligned": ("準星" in visual_context or "target_locked" in ctx_lower),
                "resource_ok": True,
                "target_name": target_name
            }
        )

    def build_jev_questions(self, capability: AssistCapability, context: Dict[str, Any]) -> Dict[str, Any]:
        # 1. 通用探索與拾取 Schema
        if capability == AssistCapability.EXPLORATION:
            return {
                "exploration_action": Choice(
                    instructions="在通用遊戲地圖探索中，選擇最優先的行動：",
                    criteria={
                        "interact_pickup": "靠近並拾取掉落物或道具 (按 F 鍵)",
                        "open_loot": "開啟眼前的寶箱或戰利品容器 (按 F 鍵)",
                        "solve_puzzle": "進行場景謎題或機關操作",
                        "navigate_waypoint": "朝目標路標導航點前進 (按 W 鍵跑動)",
                        "idle": "無目標，維持觀察"
                    }
                ),
                "has_interactive_target": Noul(
                    instructions="畫面中是否檢測到可拾取的物品、箱子或機關？"
                ),
                "exploration_priority": Score(
                    instructions="當前探索物品之價值優先度評分",
                    criteria=["雜物/普通容器", "中級物資", "高階稀有寶箱"]
                )
            }

        # 2. 通用裝備與強化分析 Schema
        if capability == AssistCapability.EQUIPMENT_BUILD:
            return {
                "enhancement_action": Choice(
                    instructions="針對當前裝備數值與性價比，給出最優處理建議：",
                    criteria={
                        "upgrade_gear": "投入資源強化升級該裝備",
                        "keep_current": "維持現狀，保留資源",
                        "salvage_or_sell": "屬性落後，建議拆解回收材料或出售",
                        "compare_and_equip": "比對目前穿著裝備，推薦立即替換穿上",
                        "idle": "維持背包比對"
                    }
                ),
                "is_worth_upgrading": Noul(
                    instructions="此裝備提升幅度是否值得投入當前強化資源與金幣？"
                ),
                "gear_score": Score(
                    instructions="裝備裝等與屬性品質綜合評分",
                    criteria=["淘汰品 (<20分)", "過渡可用 (20-35分)", "極品畢業 (40分+)"]
                ),
                "upgrade_potential": Score(
                    instructions="強化提升幅度與性價比潛力評分",
                    criteria=["收益微薄", "中等提升", "質變提升"]
                )
            }

        # 3. 常規操作與戰鬥指導 Schema
        questions = {
            "tactical_action": Choice(
                instructions="在當前通用遊戲畫面中，判斷最合理的操作動作：",
                criteria={
                    "primary_action": "主要動作或普通攻擊 (滑鼠左鍵)",
                    "secondary_action": "次要動作、瞄準或防禦 (滑鼠右鍵)",
                    "use_skill_1": "釋放技能 1 (按鍵 E)",
                    "use_skill_2": "釋放技能 2 (按鍵 Q)",
                    "use_ultimate": "施放大招終極爆發 (按鍵 R)",
                    "interact": "環境互動或拾取道具 (按鍵 F)",
                    "jump": "機動跳躍躲避障礙 (按鍵 Space)",
                    "dodge": "翻滾、閃避或衝刺 (按鍵 Shift)",
                    "idle": "保持當前狀態觀察環境動態"
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
                criteria={
                    "engagement": "接觸交戰與試探階段",
                    "skill_burst": "核心技能連鎖爆發階段",
                    "repositioning": "走位拉扯與尋找掩體階段",
                    "peaceful_exploration": "和平非戰鬥探索階段"
                }
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
            f"[Mode]: {getattr(capability, 'value', str(capability))}"
        ]

        if capability == AssistCapability.EXPLORATION:
            state_parts.extend([
                f"[Exploration Target]: {telemetry.target_name or '無特定目標'}",
                f"[Has Target]: {telemetry.has_interactive_target}",
                f"[Status]: 地圖物資探索中"
            ])
        elif capability == AssistCapability.EQUIPMENT_BUILD:
            state_parts.extend([
                f"[Gear Stats]: Estimated Score={telemetry.gear_score:.1f}, UpgradePotential={telemetry.upgrade_potential:.2f}",
                f"[Status]: 裝備/背包調整中"
            ])
        else:
            state_parts.append(f"[Threat Level]: {telemetry.threat_level:.2f}, DangerAlert={telemetry.danger_detected}")

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
        # 1. 通用探索模式解析
        if capability == AssistCapability.EXPLORATION:
            act_choice = jev_response.choices.get("exploration_action")
            primary_action = act_choice.choice if act_choice else "idle"
            confidence = act_choice.confidence if act_choice else 0.65

            prio_score = jev_response.scores.get("exploration_priority")
            urgency = prio_score.score if prio_score else 0.5

            guidance_map = {
                "interact_pickup": f"🖐️ **發現可拾取物 ({telemetry.target_name or '道具'})**：靠近並按 【F】 拾取！",
                "open_loot": f"🎁 **發現戰利品容器 ({telemetry.target_name or '箱子'})**：按 【F】 開啟！",
                "solve_puzzle": "🧩 **機關提示**：與當前解謎機關互動！",
                "navigate_waypoint": "🏃 **前往導航點**：按住 【W】 朝目標點跑動！",
                "idle": "🔍 **自由探索中**：環顧四周尋找戰利品標記。"
            }
            guidance_text = guidance_map.get(primary_action, f"探索指引: {primary_action}")

            return StrategyDecision(
                primary_action=primary_action,
                confidence=confidence,
                urgency=urgency,
                should_evade=False,
                guidance_text=guidance_text,
                telemetry=telemetry,
                raw_jev=jev_response
            )

        # 2. 通用裝備調整與強化模式解析
        if capability == AssistCapability.EQUIPMENT_BUILD:
            act_choice = jev_response.choices.get("enhancement_action")
            primary_action = act_choice.choice if act_choice else "upgrade_gear"
            confidence = act_choice.confidence if act_choice else 0.7

            worth_noul = jev_response.nouls.get("is_worth_upgrading")
            is_worth = (worth_noul.noul >= 0.5) if worth_noul else True

            score_val = jev_response.scores.get("gear_score")
            gear_score = (score_val.score * 50.0) if score_val else (telemetry.gear_score or 25.0)
            telemetry.gear_score = gear_score

            pot_score = jev_response.scores.get("upgrade_potential")
            upgrade_pot = pot_score.score if pot_score else 0.6
            telemetry.upgrade_potential = upgrade_pot

            guidance_map = {
                "upgrade_gear": f"📈 **建議強化**：當前評分 {gear_score:.1f} 分，強化升級性價比高！",
                "keep_current": "⚖️ **維持現狀**：當前提升有限，建議保留金幣與材料！",
                "salvage_or_sell": f"🛑 **淘汰處理**：屬性落後 (評分 {gear_score:.1f} 分)，建議分解拆解或出售！",
                "compare_and_equip": "🔄 **建議換裝**：新裝備屬性優於當前配裝，建議立即穿戴！",
                "idle": "👀 **背包比對中**：保留備用。"
            }
            guidance_text = guidance_map.get(primary_action, f"裝備決策: {primary_action}")

            return StrategyDecision(
                primary_action=primary_action,
                confidence=confidence,
                urgency=upgrade_pot,
                should_evade=False,
                guidance_text=guidance_text,
                telemetry=telemetry,
                raw_jev=jev_response
            )

        # 3. 常規操作模式解析
        action_choice = jev_response.choices.get("tactical_action")
        primary_action = action_choice.choice if action_choice else "idle"
        confidence = action_choice.confidence if action_choice else 0.5

        if capability == AssistCapability.AUTONOMOUS and confidence < 0.55:
            if primary_action not in ("idle", "primary_action"):
                primary_action = "idle"

        threat_noul = jev_response.nouls.get("threat_alert")
        should_evade = (threat_noul.noul >= 0.5) if threat_noul else False
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
                telemetry.features["needs_optimization"] = opt_noul.noul >= 0.5

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

        # 探索模式代替操作
        if act in ("interact_pickup", "open_loot", "interact"):
            target = "f"
            executed = actuator.press_key("f", hold_sec=0.06)
        elif act == "navigate_waypoint":
            target = "w"
            executed = actuator.press_key("w", hold_sec=0.25)
        # 戰鬥操作
        elif act == "dodge":
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

        gear_scores = [t.gear_score for t in telemetry_history if t.gear_score > 0]
        targets = [t.target_name for t in telemetry_history if t.target_name]

        report_lines = [f"### 📊 《通用遊戲》全情境實時遙測數據 (取樣 {count} 幀)\n"]

        if gear_scores:
            avg_gear = sum(gear_scores) / len(gear_scores)
            report_lines.append(
                f"#### 🛡️ 裝備與強化評定\n"
                f"- **平均裝備評分**：`{avg_gear:.1f}` 分\n"
                f"- **決策指引**：強化建議參考性價比評分，落後裝備及時分解/售出。\n"
            )

        if targets:
            report_lines.append(
                f"#### 🧭 地圖物資探索與拾取\n"
                f"- **最近目標**：{', '.join(set(targets[:5]))}\n"
                f"- **拾取快捷**：靠近目標時按 【F】 進行互動。\n"
            )

        avg_threat = sum(t.threat_level for t in telemetry_history) / count
        report_lines.append(
            f"#### ⚔️ 即時戰況\n"
            f"- **平均動態威脅度**：`{avg_threat:.2f}`\n"
            f"- **通用 Agent 狀態**：運行正常，已就緒支援自訂遊戲策略擴充。"
        )

        return "\n".join(report_lines)
