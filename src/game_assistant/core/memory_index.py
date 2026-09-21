"""
Jev 驅動的多層索引記憶檢索與路由系統 (Hierarchical Memory Indexing with Jev Routing)

徹底告別扁平記憶遍歷 (Flat Search / 大海撈針)，建立：
- Level 1 領域情境層 (Domain Layer)
- Level 2 意圖機制聚類層 (Intent Cluster Layer)
- Level 3 記憶痕跡葉節點層 (Leaf Memory Trace Layer)

由 TypeSafe Jev 的 Choice 原語驅動精準逐層路由，將檢索時間複雜度由 O(N) 降至 O(log N)。
"""

import os
import re
import json
import threading
from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict

from game_assistant.core.config import GameType, AssistCapability


class MemoryDomain:
    """Level 1 領域分類常數"""
    GENSHIN_COMBAT = "genshin_combat"
    GENSHIN_EXPLORE = "genshin_explore"
    STAR_RAIL_COMBAT = "star_rail_combat"
    STAR_RAIL_EXPLORE = "star_rail_explore"
    ZZZ_COMBAT = "zzz_combat"
    ZZZ_EXPLORE = "zzz_explore"
    EQUIPMENT_BUILD = "equipment_build"
    TRANSLATION = "translation"
    GENERAL = "general"

    ALL_DOMAINS = [
        GENSHIN_COMBAT, GENSHIN_EXPLORE,
        STAR_RAIL_COMBAT, STAR_RAIL_EXPLORE,
        ZZZ_COMBAT, ZZZ_EXPLORE,
        EQUIPMENT_BUILD, TRANSLATION, GENERAL
    ]

    DOMAIN_LABELS = {
        GENSHIN_COMBAT: "原神即時戰鬥與元素反應",
        GENSHIN_EXPLORE: "原神大世界解謎與特產採集",
        STAR_RAIL_COMBAT: "星穹鐵道回合戰術與破韌",
        STAR_RAIL_EXPLORE: "星穹鐵道大世界撲滿與戰利品",
        ZZZ_COMBAT: "絕區零快節奏戰鬥與極限招架",
        ZZZ_EXPLORE: "絕區零空洞探索與街區物資",
        EQUIPMENT_BUILD: "角色養成與裝備聖遺物詞條精算",
        TRANSLATION: "遊戲畫面外文與對話字幕翻譯",
        GENERAL: "泛用遊戲即時輔助"
    }


@dataclass
class MemoryClusterNode:
    """Level 2 意圖機制聚類節點"""
    cluster_id: str
    name: str
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    trace_ids: List[str] = field(default_factory=list)
    reflex_arc_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "name": self.name,
            "description": self.description,
            "keywords": self.keywords,
            "trace_ids": self.trace_ids,
            "reflex_arc_ids": self.reflex_arc_ids
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryClusterNode":
        return cls(
            cluster_id=data.get("cluster_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            keywords=data.get("keywords", []),
            trace_ids=data.get("trace_ids", []),
            reflex_arc_ids=data.get("reflex_arc_ids", [])
        )


@dataclass
class DomainNode:
    """Level 1 領域分區節點"""
    domain_id: str
    name: str
    clusters: Dict[str, MemoryClusterNode] = field(default_factory=dict)
    inverted_index: Dict[str, List[str]] = field(default_factory=dict)  # token -> list of cluster_ids

    def add_cluster(self, cluster: MemoryClusterNode):
        self.clusters[cluster.cluster_id] = cluster
        # 更新倒排索引
        for kw in cluster.keywords:
            kw_lower = kw.lower()
            if kw_lower not in self.inverted_index:
                self.inverted_index[kw_lower] = []
            if cluster.cluster_id not in self.inverted_index[kw_lower]:
                self.inverted_index[kw_lower].append(cluster.cluster_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain_id": self.domain_id,
            "name": self.name,
            "clusters": {cid: c.to_dict() for cid, c in self.clusters.items()},
            "inverted_index": self.inverted_index
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DomainNode":
        node = cls(
            domain_id=data.get("domain_id", ""),
            name=data.get("name", ""),
            inverted_index=data.get("inverted_index", {})
        )
        for cid, c_data in data.get("clusters", {}).items():
            node.clusters[cid] = MemoryClusterNode.from_dict(c_data)
        return node


class HierarchicalMemoryIndex:
    """
    多層記憶索引庫 (Hierarchical Memory Index)
    維護領域層、聚類層與葉節點痕跡之映射關係，具備原子磁碟持久化
    """
    def __init__(self, storage_path: str = "data/memory/hierarchical_index.json"):
        self.storage_path = storage_path
        self._lock = threading.RLock()
        self.domains: Dict[str, DomainNode] = {}
        self._init_default_hierarchy()
        self._load_from_disk()

    def _init_default_hierarchy(self):
        """初始化預設領域與經典機制聚類桶"""
        for domain_id in MemoryDomain.ALL_DOMAINS:
            label = MemoryDomain.DOMAIN_LABELS.get(domain_id, domain_id)
            node = DomainNode(domain_id=domain_id, name=label)
            self.domains[domain_id] = node

        # 預置原神戰鬥經典聚類
        self.domains[MemoryDomain.GENSHIN_COMBAT].add_cluster(
            MemoryClusterNode(
                cluster_id="elemental_reaction",
                name="元素反應戰術",
                description="水火蒸發、冰火融化、超綻放、超激化反應切人循環",
                keywords=["蒸發", "融化", "超綻放", "激化", "擴散", "元素", "切人", "反應"]
            )
        )
        self.domains[MemoryDomain.GENSHIN_COMBAT].add_cluster(
            MemoryClusterNode(
                cluster_id="burst_ult",
                name="大招爆發輸出",
                description="能量滿溢大招施放、雷神開大、無敵幀爆發",
                keywords=["大招", "元素爆發", "q", "滿能量", "爆發", "雷神"]
            )
        )
        self.domains[MemoryDomain.GENSHIN_COMBAT].add_cluster(
            MemoryClusterNode(
                cluster_id="evade_parry",
                name="極限閃避與走位",
                description="敵方紅光前搖警示、無敵幀閃避、拉扯走位",
                keywords=["閃避", "shift", "紅光", "無敵幀", "躲避", "防禦", "走位"]
            )
        )

        # 預置原神探索經典聚類
        self.domains[MemoryDomain.GENSHIN_EXPLORE].add_cluster(
            MemoryClusterNode(
                cluster_id="specialty_gather",
                name="區域特產採集",
                description="琉璃袋、塞西莉亞花、幽光星星大世界採集跟跑",
                keywords=["特產", "採集", "琉璃袋", "材料", "植物", "跟跑", "拾取", "f"]
            )
        )
        self.domains[MemoryDomain.GENSHIN_EXPLORE].add_cluster(
            MemoryClusterNode(
                cluster_id="chest_puzzle",
                name="寶箱與機關解謎",
                description="神瞳引導、仙靈座、元素方碑、各類寶箱開啟",
                keywords=["寶箱", "神瞳", "仙靈", "方碑", "解謎", "機關", "華麗寶箱"]
            )
        )

        # 預置星鐵戰鬥經典聚類
        self.domains[MemoryDomain.STAR_RAIL_COMBAT].add_cluster(
            MemoryClusterNode(
                cluster_id="weakness_break",
                name="弱點破韌戰術",
                description="弱點屬性壓制、削韌、弱點擊破爆發",
                keywords=["破韌", "弱點", "擊破", "削韌", "韌性", "屬性壓制"]
            )
        )
        self.domains[MemoryDomain.STAR_RAIL_COMBAT].add_cluster(
            MemoryClusterNode(
                cluster_id="speed_action_order",
                name="速度軸與行動輪次",
                description="134速度首輪雙動、戰技點平衡、終結技插隊",
                keywords=["速度", "行動條", "戰技點", "sp", "終結技", "插隊", "雙動"]
            )
        )

        # 預置星鐵探索經典聚類
        self.domains[MemoryDomain.STAR_RAIL_EXPLORE].add_cluster(
            MemoryClusterNode(
                cluster_id="trotter_catch",
                name="次元撲滿捕捉",
                description="撲滿逃跑警告、遠程秘技開怪先手",
                keywords=["撲滿", "次元撲滿", "秘技", "開怪", "e", "逃跑", "抓捕"]
            )
        )

        # 預置絕區零戰鬥經典聚類
        self.domains[MemoryDomain.ZZZ_COMBAT].add_cluster(
            MemoryClusterNode(
                cluster_id="yellow_flash_parry",
                name="黃光極限支援招架",
                description="敵人黃光前搖、空格極限招架、連攜技支援",
                keywords=["黃光", "招架", "極限招架", "格擋", "支援", "連攜", "space", "空格"]
            )
        )
        self.domains[MemoryDomain.ZZZ_COMBAT].add_cluster(
            MemoryClusterNode(
                cluster_id="red_flash_dodge",
                name="紅光極限閃避反擊",
                description="敵人紅光前搖、右鍵/Shift極限閃避、閃避反擊",
                keywords=["紅光", "極限閃避", "反擊", "閃避", "shift", "躲避"]
            )
        )

        # 預置絕區零探索聚類
        self.domains[MemoryDomain.ZZZ_EXPLORE].add_cluster(
            MemoryClusterNode(
                cluster_id="hdd_hollow_route",
                name="空洞電視網格導航",
                description="零號空洞路線、鳴徽選擇、降侵蝕度最優解",
                keywords=["空洞", "電視", "網格", "鳴徽", "侵蝕", "喵吉", "小卡格車"]
            )
        )

        # 預置裝備養成聚類
        self.domains[MemoryDomain.EQUIPMENT_BUILD].add_cluster(
            MemoryClusterNode(
                cluster_id="substat_cv_rating",
                name="聖遺物/遺器雙暴精算與停損",
                description="雙暴分 (CV) 計算、+4/+8 詞條跳動停損與保留上鎖",
                keywords=["聖遺物", "遺器", "驅動盤", "雙暴", "詞條", "強化", "停損", "上鎖", "主詞條"]
            )
        )

    def get_domain(self, domain_id: str) -> Optional[DomainNode]:
        with self._lock:
            return self.domains.get(domain_id)

    def add_trace_to_cluster(self, domain_id: str, cluster_id: str, memory_id: str):
        """將記憶痕跡 ID 登記至指定聚類桶"""
        with self._lock:
            domain = self.domains.get(domain_id)
            if not domain:
                domain = DomainNode(domain_id=domain_id, name=domain_id)
                self.domains[domain_id] = domain
            cluster = domain.clusters.get(cluster_id)
            if not cluster:
                cluster = MemoryClusterNode(
                    cluster_id=cluster_id,
                    name=f"意圖聚類-{cluster_id}"
                )
                domain.add_cluster(cluster)
            if memory_id not in cluster.trace_ids:
                cluster.trace_ids.append(memory_id)
            self._save_to_disk()

    def get_cluster_traces(self, domain_id: str, cluster_id: str) -> List[str]:
        """取得特定聚類桶中的所有記憶痕跡 ID (精確縮小搜尋範圍)"""
        with self._lock:
            domain = self.domains.get(domain_id)
            if not domain:
                return []
            cluster = domain.clusters.get(cluster_id)
            if not cluster:
                return []
            return list(cluster.trace_ids)

    def find_candidate_clusters_by_keywords(self, domain_id: str, tokens: Set[str]) -> List[Tuple[str, int]]:
        """利用倒排索引在特定領域內快速找出可能命中的聚類桶與權重"""
        with self._lock:
            domain = self.domains.get(domain_id)
            if not domain:
                return []
            scores: Dict[str, int] = {}
            for token in tokens:
                token_lower = token.lower()
                for kw, cluster_ids in domain.inverted_index.items():
                    if token_lower in kw or kw in token_lower:
                        for cid in cluster_ids:
                            scores[cid] = scores.get(cid, 0) + 1
            # 按匹配權重排序
            sorted_clusters = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            return sorted_clusters

    def get_index_stats(self) -> Dict[str, Any]:
        """獲取多層樹狀記憶索引之全域統計 (領域數、聚類桶數、登記葉節點數)"""
        with self._lock:
            total_clusters = sum(len(d.clusters) for d in self.domains.values())
            total_indexed_traces = sum(
                sum(len(c.trace_ids) for c in d.clusters.values())
                for d in self.domains.values()
            )
            return {
                "domain_count": len(self.domains),
                "cluster_count": total_clusters,
                "indexed_traces_count": total_indexed_traces,
                "domains": [
                    {
                        "domain_id": did,
                        "name": d.name,
                        "cluster_count": len(d.clusters),
                        "traces_count": sum(len(c.trace_ids) for c in d.clusters.values())
                    }
                    for did, d in self.domains.items()
                ]
            }

    def clear(self):
        """清空並重置為預設結構"""
        with self._lock:
            self.domains.clear()
            self._init_default_hierarchy()
            self._save_to_disk()

    def _save_to_disk(self):
        """原子持久化至磁碟"""
        try:
            target_dir = os.path.dirname(self.storage_path)
            if target_dir and not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
            data = {did: d.to_dict() for did, d in self.domains.items()}
            tmp_path = f"{self.storage_path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.storage_path)
        except Exception:
            pass

    def _load_from_disk(self):
        """從磁碟載入多層索引結構"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        for did, d_data in data.items():
                            self.domains[did] = DomainNode.from_dict(d_data)
            except Exception:
                pass


class JevMemoryRouter:
    """
    Jev 階層式記憶路由器 (Hierarchical Jev Memory Router)
    結合 TypeSafe Jev 原語與本地快速路徑，依序執行：
    1. route_level_1: 判定所屬 Domain (原神/星鐵/絕區零 x 戰鬥/探索/配裝)
    2. route_level_2: 判定所屬 Cluster (元素反應/大招/閃避/破韌/聖遺物雙暴)
    3. query_leaf_memories: 僅在目標葉節點桶內精準檢索，拒絕大海撈針！
    """

    def __init__(self, index: HierarchicalMemoryIndex, jev_engine=None):
        self.index = index
        self.jev_engine = jev_engine  # JevDecisionEngine 實例 (可選)

    def route_domain(
        self,
        input_text: str,
        game_type: Optional[GameType] = None,
        capability: Optional[AssistCapability] = None
    ) -> str:
        """
        Level 1 領域路由器：
        優先透過遊戲類型與能力快速決定領域；未知時使用 Jev Choice 進行語意分類。
        """
        # 1. 快速通道 (Fast Path)
        if game_type is not None:
            gt_str = game_type.value if hasattr(game_type, "value") else str(game_type)
            cap_str = capability.value if capability and hasattr(capability, "value") else str(capability or "")

            if "原神" in gt_str or "GENSHIN" in gt_str.upper():
                if "探索" in cap_str or capability == AssistCapability.EXPLORATION:
                    return MemoryDomain.GENSHIN_EXPLORE
                if "裝備" in cap_str or capability == AssistCapability.EQUIPMENT_BUILD:
                    return MemoryDomain.EQUIPMENT_BUILD
                return MemoryDomain.GENSHIN_COMBAT

            elif "星穹鐵道" in gt_str or "STAR_RAIL" in gt_str.upper():
                if "探索" in cap_str or capability == AssistCapability.EXPLORATION:
                    return MemoryDomain.STAR_RAIL_EXPLORE
                if "裝備" in cap_str or capability == AssistCapability.EQUIPMENT_BUILD:
                    return MemoryDomain.EQUIPMENT_BUILD
                return MemoryDomain.STAR_RAIL_COMBAT

            elif "絕區零" in gt_str or "ZZZ" in gt_str.upper():
                if "探索" in cap_str or capability == AssistCapability.EXPLORATION:
                    return MemoryDomain.ZZZ_EXPLORE
                if "裝備" in cap_str or capability == AssistCapability.EQUIPMENT_BUILD:
                    return MemoryDomain.EQUIPMENT_BUILD
                return MemoryDomain.ZZZ_COMBAT

        # 2. 依據 input_text 文本關鍵字啟發判定
        text_lower = input_text.lower()
        if any(w in text_lower for w in ["原神", "提瓦特", "胡桃", "雷神", "鍾離", "水火蒸發"]):
            return MemoryDomain.GENSHIN_COMBAT
        if any(w in text_lower for w in ["星穹鐵道", "星鐵", "撲滿", "弱點", "戰技點", "黃泉", "黑天鵝"]):
            return MemoryDomain.STAR_RAIL_COMBAT
        if any(w in text_lower for w in ["絕區零", "空洞", "鳴徽", "喵吉", "黃光", "紅光", "代理人"]):
            return MemoryDomain.ZZZ_COMBAT
        if any(w in text_lower for w in ["聖遺物", "遺器", "驅動盤", "雙暴", "詞條", "強化", "停損"]):
            return MemoryDomain.EQUIPMENT_BUILD
        if any(w in text_lower for w in ["翻譯", "英文", "日文", "韓文", "字幕"]):
            return MemoryDomain.TRANSLATION

        # 3. 若注入了 Jev 引擎且文本較複雜，調用 Jev Choice 進行智慧路由
        if self.jev_engine and hasattr(self.jev_engine, "decide"):
            try:
                candidates = [
                    MemoryDomain.GENSHIN_COMBAT,
                    MemoryDomain.STAR_RAIL_COMBAT,
                    MemoryDomain.ZZZ_COMBAT,
                    MemoryDomain.EQUIPMENT_BUILD,
                    MemoryDomain.GENERAL
                ]
                res = self.jev_engine.decide(
                    state=input_text,
                    question="此遊戲情境最符合下列哪個領域分類？",
                    candidates=candidates
                )
                if res and res.primary_action in candidates:
                    return res.primary_action
            except Exception:
                pass

        return MemoryDomain.GENERAL

    def route_cluster(
        self,
        input_text: str,
        domain_id: str,
        tokens: Optional[Set[str]] = None
    ) -> str:
        """
        Level 2 意圖機制路由器：
        在特定 Domain 下，從所有候選聚類桶中選出最符合的意圖聚類桶。
        """
        domain = self.index.get_domain(domain_id)
        if not domain or not domain.clusters:
            return "general_cluster"

        cluster_list = list(domain.clusters.values())
        if len(cluster_list) == 1:
            return cluster_list[0].cluster_id

        # 1. 倒排索引關鍵字權重比對
        if tokens:
            candidates = self.index.find_candidate_clusters_by_keywords(domain_id, tokens)
            if candidates and candidates[0][1] > 0:
                return candidates[0][0]

        # 2. 直接關鍵字比對
        text_lower = input_text.lower()
        best_match_id = cluster_list[0].cluster_id
        max_matches = -1

        for cluster in cluster_list:
            matches = sum(1 for kw in cluster.keywords if kw.lower() in text_lower)
            if matches > max_matches:
                max_matches = matches
                best_match_id = cluster.cluster_id

        if max_matches > 0:
            return best_match_id

        # 3. 若有 Jev 引擎，使用 Jev Choice 原語精準路由
        if self.jev_engine and hasattr(self.jev_engine, "decide"):
            try:
                cid_candidates = [c.cluster_id for c in cluster_list]
                res = self.jev_engine.decide(
                    state=input_text,
                    question="判定玩家此需求最精準對應下列哪項戰術機制？",
                    candidates=cid_candidates
                )
                if res and res.primary_action in cid_candidates:
                    return res.primary_action
            except Exception:
                pass

        return cluster_list[0].cluster_id

    def route(
        self,
        input_text: str,
        game_type: Optional[GameType] = None,
        capability: Optional[AssistCapability] = None,
        tokens: Optional[Set[str]] = None
    ) -> Tuple[str, str]:
        """
        完整雙層路由：回傳 (domain_id, cluster_id)
        """
        domain_id = self.route_domain(input_text, game_type=game_type, capability=capability)
        cluster_id = self.route_cluster(input_text, domain_id=domain_id, tokens=tokens)
        return domain_id, cluster_id

    def query_leaf_traces(
        self,
        input_tokens: Set[str],
        domain_id: str,
        cluster_id: str,
        memory_store,
        compute_similarity_fn,
        tokenize_fn=None,
        top_k: int = 3
    ) -> List[Tuple[Any, float]]:
        """
        Level 3 葉節點精準檢索：
        只在被 Jev 路由選中的特定 Cluster 桶內計算相似度，拒絕全域大海撈針！
        :return: List of (MemoryTrace, similarity_score)
        """
        target_trace_ids = set(self.index.get_cluster_traces(domain_id, cluster_id))
        if not target_trace_ids:
            # 備援：若該桶剛好沒有 trace，擴展檢索同 domain 下的其他 traces
            domain = self.index.get_domain(domain_id)
            if domain:
                for c in domain.clusters.values():
                    target_trace_ids.update(c.trace_ids)

        if not target_trace_ids:
            return []

        scored_traces = []
        for trace in memory_store.get_all_traces():
            if trace.memory_id in target_trace_ids:
                u_demand = getattr(trace, "user_demand", "")
                s_text = getattr(trace, "state_text", "") or getattr(trace, "feature_text", "")
                p_act = getattr(trace, "primary_action", "")
                feat_text = f"{u_demand} {s_text} {p_act}"

                if tokenize_fn:
                    trace_tokens = tokenize_fn(feat_text)
                else:
                    trace_tokens = set(re.findall(r'[a-zA-Z0-9\u4e00-\u9fff]+', feat_text.lower()))

                sim = compute_similarity_fn(input_tokens, trace_tokens)
                scored_traces.append((trace, sim))


        scored_traces.sort(key=lambda x: x[1], reverse=True)
        return scored_traces[:top_k]

    def register_trace_auto(
        self,
        trace,
        game_type: Optional[GameType] = None,
        capability: Optional[AssistCapability] = None
    ) -> Tuple[str, str]:
        """
        新記憶留痕時，透過路由器自動定位分層路徑並沉澱進目標聚類桶
        """
        u_demand = getattr(trace, "user_demand", "")
        v_context = getattr(trace, "visual_context", "") or getattr(trace, "context", "")
        s_text = getattr(trace, "state_text", "") or getattr(trace, "feature_text", "")
        p_act = getattr(trace, "primary_action", "")
        text = f"{u_demand} {s_text} {p_act} {v_context}"
        g_type = game_type or getattr(trace, "game_type", None)
        domain_id, cluster_id = self.route(
            input_text=text,
            game_type=g_type,
            capability=capability
        )
        self.index.add_trace_to_cluster(domain_id, cluster_id, trace.memory_id)
        return domain_id, cluster_id

