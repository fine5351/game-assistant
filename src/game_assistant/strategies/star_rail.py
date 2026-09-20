import time
from typing import Dict, Any, List
from PIL import Image

from game_assistant.core.config import GameType, AssistCapability
from game_assistant.engines.jev_engine import Choice, Noul, Score, JevResponse
from game_assistant.utils.input_actuator import ScreenActuator
from game_assistant.strategies.base import (
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
        in_combat = True
        has_interactive = False
        target_name = ""
        gear_score = 0.0
        upgrade_pot = 0.0

        # 銀河探索與戰利品/撲滿檢測
        if any(kw in visual_context for kw in ["戰利品", "寶箱", "撲滿", "次元撲滿", "可破壞", "紫瓶", "魔方", "引航"]):
            in_combat = False
            has_interactive = True
            if "撲滿" in visual_context:
                target_name = "次元撲滿 (星瓊目標)"
            elif "貴重" in visual_context or "豐厚" in visual_context:
                target_name = "貴重/豐厚戰利品"
            elif "戰利品" in visual_context or "寶箱" in visual_context:
                target_name = "戰利品寶箱"
            elif "紫瓶" in visual_context or "回能" in visual_context:
                target_name = "回能紫瓶/秘技點"
            else:
                target_name = "大世界解謎機關"

        # 遺器數值與強化面板檢測
        if any(kw in visual_context for kw in ["遺器", "速度", "雙爆", "雙暴", "隧洞", "位面", "充能繩", "自塑塵脂"]):
            in_combat = False
            if "134" in visual_context or "160" in visual_context or "極品" in visual_context:
                gear_score = 45.0
                upgrade_pot = 0.90
            elif "速度鞋" in visual_context or "充能" in visual_context:
                gear_score = 35.0
                upgrade_pot = 0.80
            else:
                gear_score = 25.0
                upgrade_pot = 0.55

        return TelemetryData(
            timestamp=now,
            game_type=self.game_type,
            in_combat=in_combat,
            player_hp_ratio=0.85,
            energy_ready=ult_ready,
            cooldown_ready=(sp_count > 1),
            danger_detected=("boss蓄力" in visual_context or "高威脅" in visual_context),
            threat_level=0.4,
            active_character="1",
            target_name=target_name,
            has_interactive_target=has_interactive,
            gear_score=gear_score,
            upgrade_potential=upgrade_pot,
            features={
                "sp": sp_count,
                "ult_available": [1] if ult_ready else [],
                "target_weakness": "雷 / 量子",
                "target_name": target_name
            }
        )

    def build_jev_questions(self, capability: AssistCapability, context: Dict[str, Any]) -> Dict[str, Any]:
        # 1. 銀河探索專屬 Jev Schema
        if capability == AssistCapability.EXPLORATION:
            return {
                "exploration_action": Choice(
                    instructions="在星穹鐵道大地圖探索情境下，選擇最優先的行動：",
                    criteria={
                        "catch_trotter": "發現次元撲滿！施放角色秘技 (按 E 鍵) 搶先開怪防止逃跑",
                        "open_chest": "開啟眼前的戰利品寶箱 (按 F 鍵獲取星瓊與遺器)",
                        "break_destructible": "擊破大世界可破壞物件或回能紫瓶 (左鍵攻擊補充秘技點)",
                        "solve_puzzle": "進行魔方、枘鑿六合或引航要渡解謎",
                        "follow_route": "沿大地圖指示路徑前進跑動 (按 W 鍵)",
                        "idle": "無目標，環視周圍"
                    }
                ),
                "has_interactive_target": Noul(
                    instructions="畫面中是否檢測到戰利品寶箱、次元撲滿、破壞物或解謎機關？"
                ),
                "is_urgent_trotter": Noul(
                    instructions="是否檢測到次元撲滿，需立即使用遠程或加速秘技搶開？"
                ),
                "exploration_priority": Score(
                    instructions="當前探索目標之價值評分 (撲滿/貴重戰利品優先度最高)",
                    criteria=["普通破壞容器", "一般戰利品", "貴重戰利品/次元撲滿"]
                )
            }

        # 2. 遺器調整與強化分析專屬 Jev Schema
        if capability == AssistCapability.EQUIPMENT_BUILD:
            return {
                "enhancement_action": Choice(
                    instructions="針對星穹鐵道當前遺器屬性，給出最佳強化或調整建議：",
                    criteria={
                        "upgrade_to_next_tier": "升級至下一強化閾值 (+3/+6/+9/+12/+15) 觀察副詞條跳動",
                        "lock_and_keep": "極品雙暴速度胚子，立即上鎖保留",
                        "salvage_relic": "主副詞條皆不符角色需求，停損分解為遺器殘骸 (10合1)",
                        "craft_with_resin": "強烈建議使用「自塑塵脂」定向合成此稀缺部位 (如能量充能繩/速度鞋/屬性球)",
                        "tune_speed_boots": "速度未達標 134 首輪雙動關鍵閾值，建議優先洗練速度副詞條",
                        "idle": "維持現狀比對"
                    }
                ),
                "is_worth_upgrading": Noul(
                    instructions="此遺器胚子主詞條是否正確且副詞條有潛力，值得消耗遺器經驗強化？"
                ),
                "meets_speed_threshold": Noul(
                    instructions="當前裝備搭配是否能助益角色達到 133.4 (首輪雙動) 或 160 (高速) 速度閾值？"
                ),
                "gear_score": Score(
                    instructions="遺器詞條有效度綜合評分",
                    criteria=["過渡狗糧 (<25分)", "可用良品 (25-35分)", "極品畢業 (40分+)"]
                ),
                "upgrade_potential": Score(
                    instructions="遺器剩餘跳動次數之強化期望值",
                    criteria=["已歪無潛力", "中等期望", "高期望值胚子"]
                )
            }

        # 3. 戰鬥操作情境
        questions = {
            "tactical_action": Choice(
                instructions="在星穹鐵道當前行動輪次回合中，選擇最佳操作：",
                criteria={
                    "skill_e": "消耗 SP 施放戰技 (E)",
                    "basic_attack_q": "施放普攻回覆 SP 戰技點 (Q)",
                    "ultimate_1": "1 號位主 C 終結技插隊爆發 (按鍵 1)",
                    "ultimate_2": "2 號位副 C 終結技插隊破韌 (按鍵 2)",
                    "ultimate_3": "3 號位輔助終結技插隊增益 (按鍵 3)",
                    "ultimate_4": "4 號位生存位終結技插隊急救開盾 (按鍵 4)",
                    "confirm_action": "確認施放或選定攻擊目標 (Space / 左鍵)",
                    "idle": "等待動畫播放或等待對手行動輪次"
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
                criteria={
                    "weakness_break": "弱點擊破與韌性削減階段",
                    "sp_generation": "戰技點收支累積循環階段",
                    "dps_burst": "爆發輸出與大招插隊連鎖階段",
                    "defensive_heal": "減傷保命與治療回血防禦階段"
                }
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
            f"[Mode]: {getattr(capability, 'value', str(capability))}"
        ]

        if capability == AssistCapability.EXPLORATION:
            state_parts.extend([
                f"[Exploration Target]: {telemetry.target_name or '無特定標記'}",
                f"[Has Target]: {telemetry.has_interactive_target}",
                f"[Position/Status]: 銀河大地圖探索中"
            ])
        elif capability == AssistCapability.EQUIPMENT_BUILD:
            state_parts.extend([
                f"[Relic Stats]: Estimated Score={telemetry.gear_score:.1f}, UpgradePotential={telemetry.upgrade_potential:.2f}",
                f"[Status]: 遺器強化/合成面板中"
            ])
        else:
            state_parts.extend([
                f"[Turn State]: in_combat=True, SP_remaining={sp}, TargetWeakness={weakness}",
                f"[Ultimate Ready]: {telemetry.energy_ready}"
            ])
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
        # 1. 銀河探索模式決策解析
        if capability == AssistCapability.EXPLORATION:
            act_choice = jev_response.choices.get("exploration_action")
            primary_action = act_choice.choice if act_choice else "idle"
            confidence = act_choice.confidence if act_choice else 0.65

            trotter_noul = jev_response.nouls.get("is_urgent_trotter")
            is_trotter = (trotter_noul.noul >= 0.5) if trotter_noul else False
            if is_trotter:
                primary_action = "catch_trotter"

            prio_score = jev_response.scores.get("exploration_priority")
            urgency = prio_score.score if prio_score else 0.5

            guidance_map = {
                "catch_trotter": "🐷 **警告：發現次元撲滿**！立即按下 【E】 施放秘技先手開戰，防止逃跑 (獲得 60 星瓊)！",
                "open_chest": f"🎁 **發現戰利品 ({telemetry.target_name or '寶箱'})**：按 【F】 開啟領取星瓊與素材！",
                "break_destructible": "💥 **可破壞物/紫瓶**：滑鼠 【左鍵】 擊破，補滿角色秘技點！",
                "solve_puzzle": "🧩 **機關解謎指引**：進行引航要渡或枘鑿六合解謎！",
                "follow_route": "🏃 **探索移動**：按住 【W】 沿地圖路徑前進！",
                "idle": "🔍 **銀河探索中**：持續觀察地圖方位與撲滿動靜。"
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

        # 2. 遺器調整與強化分析模式決策解析
        if capability == AssistCapability.EQUIPMENT_BUILD:
            act_choice = jev_response.choices.get("enhancement_action")
            primary_action = act_choice.choice if act_choice else "upgrade_to_next_tier"
            confidence = act_choice.confidence if act_choice else 0.7

            worth_noul = jev_response.nouls.get("is_worth_upgrading")
            is_worth = (worth_noul.noul >= 0.5) if worth_noul else True

            speed_noul = jev_response.nouls.get("meets_speed_threshold")
            meets_speed = (speed_noul.noul >= 0.5) if speed_noul else False

            score_val = jev_response.scores.get("gear_score")
            gear_score = (score_val.score * 50.0) if score_val else (telemetry.gear_score or 28.0)
            telemetry.gear_score = gear_score

            pot_score = jev_response.scores.get("upgrade_potential")
            upgrade_pot = pot_score.score if pot_score else 0.6
            telemetry.upgrade_potential = upgrade_pot

            guidance_map = {
                "upgrade_to_next_tier": f"📈 **建議強化**：當前評分 {gear_score:.1f} 分，建議強化至 +3/+6 測試副詞條跳動！",
                "lock_and_keep": f"🌟 **極品遺器 (評分: {gear_score:.1f} 分)**：速度雙暴兼備，強烈建議【立即上鎖】！",
                "salvage_relic": f"🛑 **及時停損**：副詞條無效 (評分僅 {gear_score:.1f} 分)，建議分解為遺器殘骸 (10合1)！",
                "craft_with_resin": "💎 **自塑塵脂推薦**：此部位極其稀缺 (如充能繩/屬性球)，建議使用自塑塵脂定向合成！",
                "tune_speed_boots": "⚡ **速度調配建議**：當前速度未達 134 閾值，建議優先更換主詞條速度鞋！",
                "idle": "⚖️ **遺器對比**：屬性持平，建議暫存背包。"
            }
            guidance_text = guidance_map.get(primary_action, f"遺器強化建議: {primary_action}")

            return StrategyDecision(
                primary_action=primary_action,
                confidence=confidence,
                urgency=upgrade_pot,
                should_evade=False,
                guidance_text=guidance_text,
                telemetry=telemetry,
                raw_jev=jev_response
            )

        # 3. 戰鬥操作模式決策解析
        action_choice = jev_response.choices.get("tactical_action")
        primary_action = action_choice.choice if action_choice else "idle"
        confidence = action_choice.confidence if action_choice else 0.5

        if capability == AssistCapability.AUTONOMOUS and confidence < 0.55:
            if primary_action not in ("idle", "confirm_action"):
                primary_action = "idle"

        ult_noul = jev_response.nouls.get("should_interrupt_ultimate")
        should_ult = (ult_noul.noul >= 0.5) if ult_noul else False
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
                telemetry.features["needs_optimization"] = opt_noul.noul >= 0.5

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

        # 探索模式代替操作
        if act == "catch_trotter":
            target = "e"
            executed = actuator.press_key("e", hold_sec=0.1)
        elif act == "open_chest":
            target = "f"
            executed = actuator.press_key("f", hold_sec=0.08)
        elif act == "break_destructible":
            target = "left_click"
            executed = actuator.click_mouse("left", count=1)
        elif act == "follow_route":
            target = "w"
            executed = actuator.press_key("w", hold_sec=0.25)
        # 戰鬥模式代替操作
        elif act == "skill_e":
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

        gear_scores = [t.gear_score for t in telemetry_history if t.gear_score > 0]
        targets = [t.target_name for t in telemetry_history if t.target_name]

        report_lines = [f"### 📊 《崩壞：星穹鐵道》實時遙測分析 (取樣 {count} 幀)\n"]

        if gear_scores:
            avg_gear = sum(gear_scores) / len(gear_scores)
            report_lines.append(
                f"#### 🛡️ 遺器數值與強化分析\n"
                f"- **平均遺器評分**：`{avg_gear:.1f}` 分\n"
                f"- **速度配速檢測**：建議優先追求 133.4 速度閾值 (首輪雙動)\n"
                f"- **自塑塵脂推薦**：優先定向合成「能量恢復效率連結繩」或「屬性傷害位面球」\n"
            )

        if targets:
            report_lines.append(
                f"#### 🧭 銀河大地圖探索與戰利品\n"
                f"- **最近辨識標的**：{', '.join(set(targets[:5]))}\n"
                f"- **特別提示**：若遇次元撲滿，務必於開戰前施放秘技先手開怪！\n"
            )

        avg_sp = sum(t.features.get("sp", 0) for t in telemetry_history) / count
        report_lines.append(
            f"#### ⚔️ 回合戰鬥數據\n"
            f"- **平均戰技點 (SP) 儲備**：`{avg_sp:.1f}` / 5.0\n"
            f"- **行動點循環評估**：{'🟢 戰技點收支健康' if avg_sp >= 2.0 else '🔴 戰技點緊缺，請多用普攻產點'}\n"
            f"- **擊破韌性建議**：鎖定弱點屬性角色進行削韌破防。"
        )

        return "\n".join(report_lines)
