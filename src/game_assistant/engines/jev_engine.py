if __name__ == "__main__" and not __package__:
    import sys
    from pathlib import Path
    _src = str(Path(__file__).resolve().parents[2])
    if _src not in sys.path:
        sys.path.insert(0, _src)

import json
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from game_assistant.core.config import TYPESAFE_API_KEY, JEV_MODEL_NAME, JEV_API_URL, REFLEX_CONFIDENCE_THRESHOLD

# 嘗試載入官方 typesafe-sdk
try:
    from typesafe_sdk import TypeSafeClient as _OfficialClient
    from typesafe_sdk import Choice as _OfficialChoice
    from typesafe_sdk import Noul as _OfficialNoul
    from typesafe_sdk import Score as _OfficialScore
    OFFICIAL_SDK_AVAILABLE = True
except ImportError:
    OFFICIAL_SDK_AVAILABLE = False


@dataclass
class Choice:
    """Jev Choice Primitive: 從多個具體選項中單選最佳決策"""
    instructions: str = ""
    criteria: Dict[str, Any] = field(default_factory=dict)
    options: List[str] = field(default_factory=list)
    name: str = ""
    description: str = ""

    def __post_init__(self):
        if not self.description and self.instructions:
            self.description = self.instructions
        if not self.instructions and self.description:
            self.instructions = self.description
        if not self.options and self.criteria:
            self.options = list(self.criteria.keys()) if isinstance(self.criteria, dict) else list(self.criteria)
        if not self.criteria and self.options:
            self.criteria = {opt: None for opt in self.options}

    def to_dict(self) -> dict:
        criteria_dict = self.criteria
        if not criteria_dict and self.options:
            criteria_dict = {opt: None for opt in self.options}
        elif isinstance(criteria_dict, list):
            criteria_dict = {opt: None for opt in criteria_dict}
        opts = self.options or (list(criteria_dict.keys()) if isinstance(criteria_dict, dict) else [])
        return {
            "type": "choice",
            "instructions": self.instructions or self.description,
            "criteria": criteria_dict,
            "options": opts
        }


@dataclass
class Noul:
    """Jev Noul Primitive: 評估布林是/否 (Yes/No) 狀態與機率"""
    instructions: str = ""
    criteria: Optional[Dict[str, str]] = None
    name: str = ""
    description: str = ""

    def __post_init__(self):
        if not self.description and self.instructions:
            self.description = self.instructions
        if not self.instructions and self.description:
            self.instructions = self.description

    def to_dict(self) -> dict:
        d = {
            "type": "noul",
            "instructions": self.instructions or self.description
        }
        if self.criteria:
            d["criteria"] = self.criteria
        return d


@dataclass
class Score:
    """Jev Score Primitive: 數值化評估與打分"""
    instructions: str = ""
    criteria: List[str] = field(default_factory=list)
    name: str = ""
    description: str = ""

    def __post_init__(self):
        if not self.description and self.instructions:
            self.description = self.instructions
        if not self.instructions and self.description:
            self.instructions = self.description

    def to_dict(self) -> dict:
        return {
            "type": "score",
            "instructions": self.instructions or self.description,
            "criteria": self.criteria
        }


@dataclass
class ChoiceResult:
    choice: str
    confidence: float = 1.0
    probabilities: Dict[str, float] = field(default_factory=dict)


@dataclass
class NoulResult:
    """
    Jev Noul 結果：
    - noul: Yes 的機率值 (0.0 ~ 1.0)。
    - is_positive(threshold=0.5): 依據閾值判定是否為真。
    - __bool__: 當進行 if noul_result 時，以 0.5 機率為閾值防禦，杜絕非 0 浮點數誤判。
    """
    noul: float = 0.0
    confidence: float = 1.0

    def __post_init__(self):
        if isinstance(self.noul, bool):
            self.noul = 1.0 if self.noul else 0.0
        else:
            try:
                self.noul = float(self.noul)
            except (ValueError, TypeError):
                self.noul = 0.0

    def is_positive(self, threshold: float = 0.5) -> bool:
        return self.noul >= threshold

    def __bool__(self) -> bool:
        return self.noul >= 0.5


@dataclass
class ScoreResult:
    score: float
    confidence: float = 1.0
    legend: Dict[str, str] = field(default_factory=dict)
    probabilities: Dict[str, float] = field(default_factory=dict)


@dataclass
class JevResponse:
    """Jev System 1 決策回傳結構 (反射神經響應)"""
    choices: Dict[str, ChoiceResult] = field(default_factory=dict)
    nouls: Dict[str, NoulResult] = field(default_factory=dict)
    scores: Dict[str, ScoreResult] = field(default_factory=dict)
    latency_ms: float = 0.0
    model: str = JEV_MODEL_NAME
    raw: Dict[str, Any] = field(default_factory=dict)
    is_reflex: bool = False             # 是否由已固化之反射弧直接反射輸出
    matched_arc_id: Optional[str] = None # 命中的反射弧 ID
    overall_confidence: float = 1.0     # 綜合決策置信度
    needs_escalation: bool = False      # 置信度不足或無確定結果，需上升至大腦 (Gemini System 2) 思考


class JevDecisionEngine:
    """
    TypeSafe AI - Jev (System 1) 高速即時決策引擎 / 人類神經系統之「反射神經」
    專為 0.25 秒高頻遊戲迴圈設計，支援 Choice, Noul, Score 結構化決策與已知反射弧毫秒級反射。
    具備官方 SDK、標準 REST API 與無網路/本地離線啟發式模擬器三重降級防護。
    當決策置信度未達門檻時，標記 needs_escalation=True 觸發大腦深度思考。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: str = JEV_API_URL,
        model: str = JEV_MODEL_NAME,
        confidence_threshold: float = REFLEX_CONFIDENCE_THRESHOLD
    ):
        self.api_key = api_key or TYPESAFE_API_KEY
        self.api_url = api_url
        self.model = model
        self.confidence_threshold = confidence_threshold
        self.reflex_arcs: Dict[str, Any] = {}

    def update_api_key(self, api_key: str):
        self.api_key = api_key

    def register_reflex_arc(self, arc_id: str, arc_data: Any):
        """註冊固化反射弧"""
        self.reflex_arcs[arc_id] = arc_data

    def evaluate(self, state: str, questions: Dict[str, Any]) -> JevResponse:
        """
        發送當前遊戲狀態與決策問題給 Jev 模型進行單 pass 結構化決策
        :param state: 當前畫面特徵、血量數值、敵我狀態及 Gemini 戰術指導的結構化文字
        :param questions: Choice/Noul/Score 定義字典
        :return: JevResponse
        """
        start_time = time.perf_counter()

        response = None
        # 優先嘗試透過官方 SDK 或 HTTP REST API 請求真實 Jev 模型
        if self.api_key and self.api_key.strip():
            try:
                response = self._request_api(state, questions)
            except Exception as e:
                print(f"[JevDecisionEngine] Jev 遠端請求失敗，切換為本地確定性決策器: {e}")

        # 若無 API Key 或連線異常，採用本地高精度確定性決策器 (Local Heuristic Engine)
        if response is None:
            response = self._evaluate_local_heuristics(state, questions)

        response.latency_ms = (time.perf_counter() - start_time) * 1000.0

        # 計算綜合置信度並評估是否需上升大腦思考 (needs_escalation)
        confs = []
        if response.choices:
            confs.extend(c.confidence for c in response.choices.values())
        if response.scores:
            confs.extend(s.confidence for s in response.scores.values())

        if confs:
            response.overall_confidence = round(sum(confs) / len(confs), 2)
            if min(confs) < self.confidence_threshold:
                response.needs_escalation = True
        elif not response.choices and not response.nouls and not response.scores:
            response.overall_confidence = 0.0
            response.needs_escalation = True

        return response

    def _request_api(self, state: str, questions: Dict[str, Any]) -> JevResponse:
        """透過官方 SDK 或 TypeSafe REST API 呼叫 Jev 模型"""
        # 1. 若安裝了官方 SDK 且能實例化客戶端，優先採用 SDK
        if OFFICIAL_SDK_AVAILABLE and _OfficialClient:
            try:
                client = _OfficialClient(api_key=self.api_key)
                official_questions = {}
                for q_id, q_obj in questions.items():
                    inst = getattr(q_obj, "instructions", "") or getattr(q_obj, "description", "")
                    if isinstance(q_obj, Choice):
                        crit = q_obj.criteria
                        if not crit and q_obj.options:
                            crit = {opt: None for opt in q_obj.options}
                        elif isinstance(crit, list):
                            crit = {opt: None for opt in crit}
                        official_questions[q_id] = _OfficialChoice(
                            instructions=inst,
                            criteria=crit
                        )
                    elif isinstance(q_obj, Noul):
                        noul_kwargs = {"instructions": inst}
                        if getattr(q_obj, "criteria", None):
                            noul_kwargs["criteria"] = q_obj.criteria
                        official_questions[q_id] = _OfficialNoul(**noul_kwargs)
                    elif isinstance(q_obj, Score):
                        official_questions[q_id] = _OfficialScore(
                            instructions=inst,
                            criteria=q_obj.criteria
                        )
                sdk_resp = client.system_one(state=state, questions=official_questions)
                return self._parse_api_response(sdk_resp if isinstance(sdk_resp, dict) else getattr(sdk_resp, "__dict__", {}))
            except Exception as sdk_err:
                print(f"[JevDecisionEngine] 官方 SDK 呼叫異常，降級為標準 REST API: {sdk_err}")

        # 2. 標準 REST API 呼叫 (https://api.typesafe.ai/v1/systemone)
        serialized_questions = {}
        for q_id, q_obj in questions.items():
            if hasattr(q_obj, "to_dict"):
                serialized_questions[q_id] = q_obj.to_dict()
            elif isinstance(q_obj, dict):
                serialized_questions[q_id] = q_obj
            else:
                serialized_questions[q_id] = {"instructions": str(q_obj)}

        payload = {
            "model": self.model,
            "state": state,
            "questions": serialized_questions
        }
        data_bytes = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            self.api_url,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "GameAssistant-JevClient/1.0"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=1.5) as resp:
            resp_body = resp.read().decode("utf-8")
            raw_data = json.loads(resp_body)
            return self._parse_api_response(raw_data)

    def _parse_api_response(self, data: dict) -> JevResponse:
        """
        解析 TypeSafe Jev 模型回傳資料。
        標準規範：data["answers"][<question_id>] -> {type, choice/noul/score, probabilities, confidence...}
        向後相容：data["choices"], data["nouls"], data["scores"]
        """
        res = JevResponse(raw=data)

        # 1. 官方標準結構：data["answers"] 字典映射
        if "answers" in data and isinstance(data["answers"], dict):
            for k, v in data["answers"].items():
                if isinstance(v, dict):
                    ans_type = v.get("type", "")
                    if ans_type == "choice":
                        res.choices[k] = ChoiceResult(
                            choice=str(v.get("choice", "")),
                            confidence=float(v.get("confidence", 1.0)),
                            probabilities=v.get("probabilities", {})
                        )
                    elif ans_type == "noul":
                        # 官方 Noul 回傳 float 機率值 (0.0 ~ 1.0)
                        res.nouls[k] = NoulResult(
                            noul=float(v.get("noul", 0.0))
                        )
                    elif ans_type == "score":
                        res.scores[k] = ScoreResult(
                            score=float(v.get("score", 0.0)),
                            confidence=float(v.get("confidence", 1.0)),
                            legend=v.get("legend", {}),
                            probabilities=v.get("probabilities", {})
                        )
                else:
                    ans_type = getattr(v, "type", "")
                    if ans_type == "choice" or hasattr(v, "choice"):
                        res.choices[k] = ChoiceResult(
                            choice=str(getattr(v, "choice", "")),
                            confidence=float(getattr(v, "confidence", 1.0)),
                            probabilities=getattr(v, "probabilities", {})
                        )
                    elif ans_type == "noul" or hasattr(v, "noul"):
                        res.nouls[k] = NoulResult(
                            noul=float(getattr(v, "noul", 0.0))
                        )
                    elif ans_type == "score" or hasattr(v, "score"):
                        res.scores[k] = ScoreResult(
                            score=float(getattr(v, "score", 0.0)),
                            confidence=float(getattr(v, "confidence", 1.0)),
                            legend=getattr(v, "legend", {}),
                            probabilities=getattr(v, "probabilities", {})
                        )

        # 2. 相容舊式 / 本地模擬結構
        if "choices" in data and isinstance(data["choices"], dict):
            for k, v in data["choices"].items():
                if k not in res.choices:
                    if isinstance(v, dict):
                        res.choices[k] = ChoiceResult(
                            choice=v.get("choice", ""),
                            confidence=float(v.get("confidence", 1.0)),
                            probabilities=v.get("probabilities", {})
                        )
                    elif isinstance(v, ChoiceResult):
                        res.choices[k] = v
                    else:
                        res.choices[k] = ChoiceResult(choice=str(v))

        if "nouls" in data and isinstance(data["nouls"], dict):
            for k, v in data["nouls"].items():
                if k not in res.nouls:
                    if isinstance(v, dict):
                        res.nouls[k] = NoulResult(
                            noul=float(v.get("noul", 0.0)),
                            confidence=float(v.get("confidence", 1.0))
                        )
                    elif isinstance(v, NoulResult):
                        res.nouls[k] = v
                    else:
                        res.nouls[k] = NoulResult(noul=v)

        if "scores" in data and isinstance(data["scores"], dict):
            for k, v in data["scores"].items():
                if k not in res.scores:
                    if isinstance(v, dict):
                        res.scores[k] = ScoreResult(
                            score=float(v.get("score", 0.0)),
                            confidence=float(v.get("confidence", 1.0)),
                            legend=v.get("legend", {}),
                            probabilities=v.get("probabilities", {})
                        )
                    elif isinstance(v, ScoreResult):
                        res.scores[k] = v
                    else:
                        res.scores[k] = ScoreResult(score=float(v))

        return res

    def _evaluate_local_heuristics(self, state: str, questions: Dict[str, Any]) -> JevResponse:
        """
        本地確定性啟發式決策器 (Local System 1 Heuristics)
        在無網路、開發測試或低延遲環境下，根據狀態關鍵字與意圖進行毫秒級精確評估。
        """
        state_lower = state.lower()
        res = JevResponse()

        for q_id, q_obj in questions.items():
            # 取得 criteria 與 instructions
            criteria = getattr(q_obj, "criteria", {})
            instructions = getattr(q_obj, "instructions", "")

            # 1. 處理 Choice 類型
            if isinstance(q_obj, Choice) or (isinstance(q_obj, dict) and q_obj.get("type") == "choice"):
                options = getattr(q_obj, "options", [])
                if not options:
                    options = list(criteria.keys()) if isinstance(criteria, dict) else list(criteria)
                if not options:
                    options = ["idle"]

                # 依據狀態文字中的關鍵字權重進行打分匹配
                best_opt = options[0]
                best_score = -1.0
                scores_map = {}

                for opt in options:
                    score = 0.5
                    opt_term = opt.lower()
                    if opt_term in state_lower:
                        score += 0.4
                    # 依據常見戰術與資料分析關鍵字加權
                    if "dodge" in opt_term and ("黃光" in state or "紅光" in state or "attack" in state_lower or "danger" in state_lower):
                        score += 0.45
                    elif "parry" in opt_term and ("黃光" in state or "parry" in state_lower):
                        score += 0.48
                    elif "skill" in opt_term and ("cooldown_ready" in state_lower or "技能可用" in state):
                        score += 0.35
                    elif "burst" in opt_term and ("energy_full" in state_lower or "滿能量" in state or "ult_ready" in state_lower):
                        score += 0.4
                    elif "switch" in opt_term and ("switch_recommended" in state_lower or "換人" in state or "反應" in state):
                        score += 0.38
                    elif "reaction" in opt_term and ("蒸發" in state or "融化" in state or "elements" in state_lower):
                        score += 0.42
                    elif "break" in opt_term and ("weakness" in state_lower or "韌性" in state or "daze" in state_lower):
                        score += 0.41

                    scores_map[opt] = score
                    if score > best_score:
                        best_score = score
                        best_opt = opt

                res.choices[q_id] = ChoiceResult(
                    choice=best_opt,
                    confidence=min(1.0, round(best_score, 2)),
                    probabilities=scores_map
                )

            # 2. 處理 Noul (布林是/否與機率) 類型
            elif isinstance(q_obj, Noul) or (isinstance(q_obj, dict) and q_obj.get("type") == "noul"):
                # 檢測危險、閃避、滿能量、治療需求、優化需求等
                is_true = False
                conf = 0.85
                inst_lower = (instructions or getattr(q_obj, "description", "")).lower()
                if "attack" in inst_lower or "danger" in inst_lower or "警示" in instructions or "閃避" in instructions:
                    is_true = ("黃光" in state or "紅光" in state or "danger" in state_lower or "前搖" in state or "紅圈" in state)
                elif "energy" in inst_lower or "能量" in instructions or "ult" in inst_lower or "終結技" in instructions:
                    is_true = ("滿能量" in state or "energy_full" in state_lower or "ultimateready: true" in state_lower or "energy_ready=true" in state_lower or "ult_ready" in state_lower)
                elif "heal" in inst_lower or "治療" in instructions or "殘血" in instructions:
                    is_true = ("low_hp" in state_lower or "殘血" in state)
                elif "optimi" in inst_lower or "優化" in instructions or "調整" in instructions:
                    is_true = ("sp_remaining=1" in state_lower or "sp_remaining=0" in state_lower or "殘血" in state or "danger" in state_lower)
                else:
                    # 預設依據 instructions 關鍵字在 state 存在與否
                    is_true = any(word in state_lower for word in inst_lower.split() if len(word) > 2)

                # TypeSafe Noul 回傳 Yes 的機率 (0.0 ~ 1.0)
                noul_prob = 0.95 if is_true else 0.05
                res.nouls[q_id] = NoulResult(noul=noul_prob, confidence=conf)

            # 3. 處理 Score (數值評估) 類型
            elif isinstance(q_obj, Score) or (isinstance(q_obj, dict) and q_obj.get("type") == "score"):
                urgency = 0.5
                inst_lower = (instructions or getattr(q_obj, "description", "")).lower()
                if (
                    "黃光" in state or "紅光" in state or "danger" in state_lower or
                    "危險" in state or "前搖" in state or "紅圈" in state or "alert" in state_lower
                ):
                    urgency = 0.95
                elif "cooldown_ready" in state_lower or "滿能量" in state or "energy_full" in state_lower:
                    urgency = 0.75
                elif "efficiency" in inst_lower or "效率" in instructions:
                    urgency = 0.82 if ("in_combat=true" in state_lower and "energy_ready" in state_lower) else 0.65
                res.scores[q_id] = ScoreResult(score=urgency, confidence=0.9)

        return res


if __name__ == "__main__":
    engine = JevDecisionEngine()
    print(f"JevDecisionEngine 初始化成功 (Official SDK Available: {OFFICIAL_SDK_AVAILABLE})")
    sample_res = engine.evaluate(
        state="敵方出現黃光前搖攻擊，技能就緒，隊伍滿能量",
        questions={
            "action": Choice(instructions="選擇動作", options=["dodge", "parry", "attack"]),
            "danger": Noul(instructions="是否有危險警示"),
            "urgency": Score(instructions="緊急程度")
        }
    )
    print(f"決策動作: {sample_res.choices.get('action')}")
    print(f"危險判定: {sample_res.nouls.get('danger')}")
    print(f"緊急評分: {sample_res.scores.get('urgency')}")
