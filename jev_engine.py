import json
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from config import TYPESAFE_API_KEY, JEV_MODEL_NAME, JEV_API_URL

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
        return {
            "type": "choice",
            "name": self.name,
            "instructions": self.instructions or self.description,
            "description": self.description or self.instructions,
            "options": self.options,
            "criteria": self.criteria
        }


@dataclass
class Noul:
    """Jev Noul Primitive: 評估布林是/否 (Yes/No) 狀態"""
    instructions: str = ""
    name: str = ""
    description: str = ""

    def __post_init__(self):
        if not self.description and self.instructions:
            self.description = self.instructions
        if not self.instructions and self.description:
            self.instructions = self.description

    def to_dict(self) -> dict:
        return {
            "type": "noul",
            "name": self.name,
            "instructions": self.instructions or self.description,
            "description": self.description or self.instructions
        }


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
            "name": self.name,
            "instructions": self.instructions or self.description,
            "description": self.description or self.instructions,
            "criteria": self.criteria
        }


@dataclass
class ChoiceResult:
    choice: str
    confidence: float = 1.0
    probabilities: Dict[str, float] = field(default_factory=dict)


@dataclass
class NoulResult:
    noul: bool
    confidence: float = 1.0


@dataclass
class ScoreResult:
    score: float
    confidence: float = 1.0


@dataclass
class JevResponse:
    """Jev System 1 決策回傳結構"""
    choices: Dict[str, ChoiceResult] = field(default_factory=dict)
    nouls: Dict[str, NoulResult] = field(default_factory=dict)
    scores: Dict[str, ScoreResult] = field(default_factory=dict)
    latency_ms: float = 0.0
    model: str = JEV_MODEL_NAME
    raw: Dict[str, Any] = field(default_factory=dict)


class JevDecisionEngine:
    """
    TypeSafe AI - Jev (System 1) 高速即時決策引擎
    專為 0.25 秒高頻遊戲迴圈設計，支援 Choice, Noul, Score 結構化決策。
    具備官方 SDK、標準 REST API 與無網路/本地離線啟發式模擬器三重降級防護。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: str = JEV_API_URL,
        model: str = JEV_MODEL_NAME
    ):
        self.api_key = api_key or TYPESAFE_API_KEY
        self.api_url = api_url
        self.model = model

    def update_api_key(self, api_key: str):
        self.api_key = api_key

    def evaluate(self, state: str, questions: Dict[str, Any]) -> JevResponse:
        """
        發送當前遊戲狀態與決策問題給 Jev 模型進行單 pass 結構化決策
        :param state: 當前畫面特徵、血量數值、敵我狀態及 Gemini 戰術指導的結構化文字
        :param questions: Choice/Noul/Score 定義字典
        :return: JevResponse
        """
        start_time = time.perf_counter()

        # 優先嘗試透過官方 SDK 或 HTTP REST API 請求真實 Jev 模型
        if self.api_key and self.api_key.strip():
            try:
                response = self._request_api(state, questions)
                response.latency_ms = (time.perf_counter() - start_time) * 1000.0
                return response
            except Exception as e:
                print(f"[JevDecisionEngine] Jev 遠端請求失敗，切換為本地確定性決策器: {e}")

        # 若無 API Key 或連線異常，採用本地高精度確定性決策器 (Local Heuristic Engine)
        response = self._evaluate_local_heuristics(state, questions)
        response.latency_ms = (time.perf_counter() - start_time) * 1000.0
        return response

    def _request_api(self, state: str, questions: Dict[str, Any]) -> JevResponse:
        """透過官方 SDK 或 TypeSafe REST API 呼叫 Jev 模型"""
        # 1. 若安裝了官方 SDK 且能實例化客戶端，優先採用 SDK
        if OFFICIAL_SDK_AVAILABLE and _OfficialClient:
            try:
                client = _OfficialClient(api_key=self.api_key)
                official_questions = []
                for q_id, q_obj in questions.items():
                    if isinstance(q_obj, Choice):
                        opts = q_obj.options or (list(q_obj.criteria.keys()) if isinstance(q_obj.criteria, dict) else list(q_obj.criteria))
                        official_questions.append(_OfficialChoice(
                            name=q_id,
                            options=opts,
                            description=q_obj.instructions or q_obj.description
                        ))
                    elif isinstance(q_obj, Noul):
                        official_questions.append(_OfficialNoul(
                            name=q_id,
                            description=q_obj.instructions or q_obj.description
                        ))
                    elif isinstance(q_obj, Score):
                        official_questions.append(_OfficialScore(
                            name=q_id,
                            criteria=q_obj.criteria,
                            description=q_obj.instructions or q_obj.description
                        ))
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
        res = JevResponse(raw=data)
        if "choices" in data:
            for k, v in data["choices"].items():
                if isinstance(v, dict):
                    res.choices[k] = ChoiceResult(
                        choice=v.get("choice", ""),
                        confidence=float(v.get("confidence", 1.0)),
                        probabilities=v.get("probabilities", {})
                    )
                else:
                    res.choices[k] = ChoiceResult(choice=str(v))

        if "nouls" in data:
            for k, v in data["nouls"].items():
                if isinstance(v, dict):
                    res.nouls[k] = NoulResult(
                        noul=bool(v.get("noul", False)),
                        confidence=float(v.get("confidence", 1.0))
                    )
                else:
                    res.nouls[k] = NoulResult(noul=bool(v))

        if "scores" in data:
            for k, v in data["scores"].items():
                if isinstance(v, dict):
                    res.scores[k] = ScoreResult(
                        score=float(v.get("score", 0.0)),
                        confidence=float(v.get("confidence", 1.0))
                    )
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

            # 2. 處理 Noul (布林是/否) 類型
            elif isinstance(q_obj, Noul) or (isinstance(q_obj, dict) and q_obj.get("type") == "noul"):
                # 檢測危險、閃避、滿能量、治療需求、優化需求等
                is_true = False
                conf = 0.85
                inst_lower = (instructions or getattr(q_obj, "description", "")).lower()
                if "attack" in inst_lower or "danger" in inst_lower or "警示" in instructions:
                    is_true = ("黃光" in state or "紅光" in state or "danger" in state_lower or "前搖" in state)
                elif "energy" in inst_lower or "能量" in instructions or "ult" in inst_lower:
                    is_true = ("滿能量" in state or "energy_full" in state_lower or "ultimateready: true" in state_lower)
                elif "heal" in inst_lower or "治療" in instructions or "殘血" in instructions:
                    is_true = ("low_hp" in state_lower or "殘血" in state)
                elif "optimi" in inst_lower or "優化" in instructions or "調整" in instructions:
                    is_true = ("sp_remaining=1" in state_lower or "sp_remaining=0" in state_lower or "殘血" in state or "danger" in state_lower)
                else:
                    # 預設依據 instructions 關鍵字在 state 存在與否
                    is_true = any(word in state_lower for word in inst_lower.split() if len(word) > 2)

                res.nouls[q_id] = NoulResult(noul=is_true, confidence=conf)

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
