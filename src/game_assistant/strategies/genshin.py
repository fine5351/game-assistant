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
        w, h = image.size
        threat = 0.0
        danger = False
        in_combat = True
        has_interactive = False
        target_name = ""
        gear_score = 0.0
        upgrade_pot = 0.0

        ctx_lower = visual_context.lower()

        # 戰鬥狀態判斷
        if "前搖" in visual_context or "紅光" in visual_context or "attack" in ctx_lower:
            danger = True
            threat = 0.85

        # 大世界探索蒐集目標檢測
        if any(kw in visual_context for kw in ["寶箱", "神瞳", "特產", "琉璃袋", "塞西莉亞", "仙靈", "方碑", "採集", "拾取"]):
            in_combat = False
            has_interactive = True
            if "神瞳" in visual_context and "寶箱" in visual_context:
                target_name = "散失的神瞳 / 珍貴寶箱"
            elif "神瞳" in visual_context:
                target_name = "散失的神瞳"
            elif "華麗" in visual_context or "珍貴" in visual_context:
                target_name = "珍貴/華麗寶箱"
            elif "寶箱" in visual_context:
                target_name = "大世界寶箱"
            elif "特產" in visual_context or "琉璃袋" in visual_context or "塞西莉亞" in visual_context:
                target_name = "區域特產植物"
            else:
                target_name = "可互動解謎機關"

        # 聖遺物裝備數值檢測
        if any(kw in visual_context for kw in ["聖遺物", "雙暴", "暴擊", "生之花", "死之羽", "時之沙", "空之杯", "理之冠", "cv"]):
            in_combat = False
            # 依據上下文估算詞條評分
            if "40分" in visual_context or "大畢業" in visual_context or "極品" in visual_context:
                gear_score = 42.5
                upgrade_pot = 0.95
            elif "30分" in visual_context or "良品" in visual_context:
                gear_score = 32.0
                upgrade_pot = 0.75
            elif "20分" in visual_context or "及格" in visual_context:
                gear_score = 22.0
                upgrade_pot = 0.50
            else:
                gear_score = 28.5
                upgrade_pot = 0.65

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
            target_name=target_name,
            has_interactive_target=has_interactive,
            gear_score=gear_score,
            upgrade_potential=upgrade_pot,
            features={
                "elements": ["Pyro", "Hydro"],
                "optimal_reaction": "蒸發 (Vaporize)",
                "target_name": target_name
            }
        )

    def build_jev_questions(self, capability: AssistCapability, context: Dict[str, Any]) -> Dict[str, Any]:
        # 1. 探索蒐集情境專屬 Jev Schema
        if capability == AssistCapability.EXPLORATION:
            return {
                "exploration_action": Choice(
                    instructions="在原神大世界探索與採集情境下，選擇最優先的行動：",
                    criteria={
                        "gather_specialty": "採集大世界特產植物或礦物 (靠近按 F 鍵拾取)",
                        "open_chest": "開啟眼前的寶箱 (靠近按 F 鍵開啟)",
                        "collect_oculus": "拾取散失的神瞳 (攀爬/飛越碰撞拾取)",
                        "solve_puzzle": "破解元素方碑或仙靈機關 (切換對應元素攻擊或引導)",
                        "follow_route": "沿推薦跟跑路線前進 (向前跑動)",
                        "idle": "無互動目標，觀察四周地形與小地圖"
                    }
                ),
                "has_interactive_target": Noul(
                    instructions="畫面中是否檢測到可拾取的特產、寶箱、神瞳或可破解的機關？"
                ),
                "exploration_priority": Score(
                    instructions="當前探索目標之價值與優先度評分",
                    criteria=["普通破壞物/素材", "特產/精緻寶箱", "珍貴/華麗寶箱/神瞳"]
                )
            }

        # 2. 裝備調整與強化分析情境專屬 Jev Schema
        if capability == AssistCapability.EQUIPMENT_BUILD:
            return {
                "enhancement_action": Choice(
                    instructions="針對原神當前聖遺物數值與詞條，給出最佳調整或強化決策：",
                    criteria={
                        "upgrade_to_next_tier": "強化至下一詞條跳動閾值 (+4/+8/+12/+16/+20) 查看詞條",
                        "lock_and_keep": "極品胚子或畢業聖遺物 (高雙暴/多有效詞條)，立即上鎖保留",
                        "stop_and_salvage": "主副詞條嚴重歪斜或連續跳無效詞條，及時停損作為狗糧",
                        "reroll_artifact": "詞條不佳之金色聖遺物，保留作為還聖奧跡合成胚子",
                        "idle": "維持現狀，比對其他部位"
                    }
                ),
                "is_worth_upgrading": Noul(
                    instructions="此聖遺物胚子是否具備雙暴或雙有效詞條，值得繼續投入資源強化？"
                ),
                "should_lock": Noul(
                    instructions="是否強烈建議立即上鎖，避免誤當作狗糧或還聖奧跡消耗？"
                ),
                "gear_score": Score(
                    instructions="聖遺物詞條綜合評分 (雙暴分 CV 與有效詞條加權)",
                    criteria=["過渡 (<20分)", "及格可用 (20-30分)", "極品畢業 (35分+)"]
                ),
                "upgrade_potential": Score(
                    instructions="聖遺物剩餘強化次數跳動潛力評分",
                    criteria=["潛力耗盡/已歪", "中等期望", "極高期望 (雙暴胚子)"]
                )
            }

        # 3. 戰鬥操作與即時指導情境 (GUIDANCE / AUTONOMOUS)
        questions = {
            "tactical_action": Choice(
                instructions="在原神當前戰鬥情境下，選擇最優先的戰術動作：",
                criteria={
                    "burst_q": "釋放元素爆發 (Q) 進行高額傷害輸出",
                    "skill_e": "釋放元素戰技 (E) 產球充能並觸發元素附著",
                    "dash_dodge": "衝刺無敵幀閃避 (Shift / 右鍵) 躲避攻擊",
                    "switch_char_2": "切換 2 號位施放輔助技能或打反應",
                    "switch_char_3": "切換 3 號位施放增益 Buff",
                    "switch_char_4": "切換 4 號位進行護盾或治療保護",
                    "switch_char_1": "切回 1 號位主 C 進行站場輸出",
                    "normal_attack": "普通攻擊或重擊 (左鍵) 補充傷害",
                    "idle": "保持走位觀察，等待技能冷卻或敵方動作"
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
                criteria={
                    "opening_setup": "戰鬥起手輔助上 Buff 階段",
                    "reaction_burst": "主 C 爆發與元素反應連鎖階段",
                    "skill_recharge": "全隊戰技產球與充能循環階段",
                    "evasion_recovery": "閃避規避傷害與隊伍治療拉扯階段"
                }
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
            f"[Mode]: {getattr(capability, 'value', str(capability))}"
        ]

        if capability == AssistCapability.EXPLORATION:
            state_parts.extend([
                f"[Exploration Target]: {telemetry.target_name or '無特定標記'}",
                f"[Has Target]: {telemetry.has_interactive_target}",
                f"[Position/Status]: HP=100%, 自由移動探索中"
            ])
        elif capability == AssistCapability.EQUIPMENT_BUILD:
            state_parts.extend([
                f"[Artifact Stats]: Estimated CV={telemetry.gear_score:.1f}, UpgradePotential={telemetry.upgrade_potential:.2f}",
                f"[Status]: 聖遺物背包/強化面板中"
            ])
        else:
            state_parts.extend([
                f"[Combat Status]: in_combat={telemetry.in_combat}, threat={telemetry.threat_level:.2f}",
                f"[Player Status]: HP=80%, ActiveChar={telemetry.active_character}, BurstReady={telemetry.energy_ready}",
                f"[Reactions]: Elements={telemetry.features.get('elements')}, Optimal={telemetry.features.get('optimal_reaction')}"
            ])
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
        # 1. 探索蒐集模式決策解析
        if capability == AssistCapability.EXPLORATION:
            act_choice = jev_response.choices.get("exploration_action")
            primary_action = act_choice.choice if act_choice else "idle"
            confidence = act_choice.confidence if act_choice else 0.6

            target_noul = jev_response.nouls.get("has_interactive_target")
            has_target = (target_noul.noul >= 0.5) if target_noul else telemetry.has_interactive_target
            telemetry.has_interactive_target = has_target

            prio_score = jev_response.scores.get("exploration_priority")
            urgency = prio_score.score if prio_score else 0.5

            guidance_map = {
                "gather_specialty": f"🌿 **發現大世界特產 ({telemetry.target_name or '素材'})**：靠近並按 【F】 進行採集拾取！",
                "open_chest": f"🎁 **發現寶箱 ({telemetry.target_name or '戰利品'})**：按 【F】 開啟獲取原石與聖遺物！",
                "collect_oculus": "✨ **散失的神瞳標記**：攀爬高處或利用風場滑翔拾取！",
                "solve_puzzle": "🔮 **元素機關/仙靈指引**：切換對應元素角色攻擊方碑或跟隨仙靈！",
                "follow_route": "🏃 **採集跟跑路徑**：沿當前採集路徑向前奔跑 [W]！",
                "idle": "🔍 **大地圖探索中**：持續環視周邊地形與迷你地圖標記。"
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

        # 2. 裝備調整與強化分析模式決策解析
        if capability == AssistCapability.EQUIPMENT_BUILD:
            act_choice = jev_response.choices.get("enhancement_action")
            primary_action = act_choice.choice if act_choice else "upgrade_to_next_tier"
            confidence = act_choice.confidence if act_choice else 0.7

            worth_noul = jev_response.nouls.get("is_worth_upgrading")
            is_worth = (worth_noul.noul >= 0.5) if worth_noul else True

            lock_noul = jev_response.nouls.get("should_lock")
            should_lock = (lock_noul.noul >= 0.5) if lock_noul else False

            score_val = jev_response.scores.get("gear_score")
            gear_score = (score_val.score * 50.0) if score_val else (telemetry.gear_score or 25.0)
            telemetry.gear_score = gear_score

            pot_score = jev_response.scores.get("upgrade_potential")
            upgrade_pot = pot_score.score if pot_score else 0.6
            telemetry.upgrade_potential = upgrade_pot

            guidance_map = {
                "upgrade_to_next_tier": f"📈 **建議強化**：當前評分約 {gear_score:.1f} 分，建議升至下一跳動等級 (+4/+8/+12) 觀察詞條！",
                "lock_and_keep": f"🌟 **極品胚子 (評分: {gear_score:.1f} 分)**：強烈建議立即【上鎖保留】，雙暴收益極高！",
                "stop_and_salvage": f"🛑 **停損建議**：詞條歪斜 (評分僅 {gear_score:.1f} 分)，建議停止強化並作為狗糧肥料！",
                "reroll_artifact": f"♻️ **還聖奧跡**：評分低於門檻，建議保留作為三合一還聖奧跡素材！",
                "idle": "⚖️ **聖遺物對比**：數值與當前佩戴裝備持平，請保留觀察。"
            }
            guidance_text = guidance_map.get(primary_action, f"聖遺物強化建議: {primary_action}")
            if should_lock:
                guidance_text = "🔒 **已判定具備收藏價值**！" + guidance_text

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
            if primary_action not in ("idle", "normal_attack"):
                primary_action = "idle"

        evade_noul = jev_response.nouls.get("should_evade")
        should_evade = (evade_noul.noul >= 0.5) if evade_noul else False
        if should_evade:
            primary_action = "dash_dodge"

        urgency_score = jev_response.scores.get("combat_urgency")
        urgency = urgency_score.score if urgency_score else 0.5

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

        # 探索模式代替操作
        if act in ("gather_specialty", "open_chest"):
            target = "f"
            executed = actuator.press_key("f", hold_sec=0.08)
        elif act == "follow_route":
            target = "w"
            executed = actuator.press_key("w", hold_sec=0.25)
        # 戰鬥模式代替操作
        elif act == "dash_dodge":
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
        msg = f"已發送原神操作：[{target}]" if executed else f"操作冷卻中：[{target}]"
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
            return "尚無足夠的原神遙測數據。"

        # 檢查是否含有裝備強化或探索數據
        gear_scores = [t.gear_score for t in telemetry_history if t.gear_score > 0]
        targets = [t.target_name for t in telemetry_history if t.target_name]

        report_lines = [f"### 📊 《原神》實時戰況遙測分析 (全方位多情境 / 取樣 {count} 幀 / 每 0.25 秒)\n"]

        if gear_scores:
            avg_gear = sum(gear_scores) / len(gear_scores)
            report_lines.append(
                f"#### 🛡️ 聖遺物數值與強化評級\n"
                f"- **平均詞條評分 (CV)**：`{avg_gear:.1f}` 分\n"
                f"- **胚子評級**：{'🏆 極品良品' if avg_gear >= 30 else '⚖️ 過渡可用'}\n"
                f"- **強化建議**：{'+4 測第四條詞條' if avg_gear < 30 else '建議強化至 +20 畢業'}\n"
            )

        if targets:
            report_lines.append(
                f"#### 🧭 大世界探索與素材採集\n"
                f"- **最近辨識目標**：{', '.join(set(targets[:5]))}\n"
                f"- **採集提示**：靠近目標時請按 【F】 進行快速互動拾取。\n"
            )

        avg_threat = sum(t.threat_level for t in telemetry_history) / count
        danger_count = sum(1 for t in telemetry_history if t.danger_detected)
        report_lines.append(
            f"#### ⚔️ 戰況遙測數據\n"
            f"- **平均威脅指數**：`{avg_threat:.2f}` / 1.0\n"
            f"- **敵方危險攻擊判定**：`{danger_count}` 次\n"
            f"- **當前元素環境**：火/水 (蒸發反應加成維持中)\n"
            f"- **技能循環建議**：建議維持 2號位(掛水) ➔ 1號位(火C爆發) 之循環節奏。"
        )

        return "\n".join(report_lines)
