"""
自律網路情報採集器 (Web Sensory Ears/Eyes)
提供主動式遊戲百科檢索、攻略抓取、大世界探索採集導航與角色配裝資料庫，
具備本地磁碟快取與離線確定性知識防護網。
"""

import os
import json
import re
import urllib.parse
import urllib.request
from typing import Dict, Any, List, Optional
from game_assistant.core.config import GameType


class WebSensoryGatherer:
    """
    網路情報感官採集器 (Web Sensory Ears/Eyes)
    如同助理的耳朵與眼睛，自主從網路上蒐集攻略、百科數值與地圖點位情報。
    """

    def __init__(self, cache_dir: str = "data/knowledge_cache", enable_network: bool = True):
        self.cache_dir = cache_dir
        self.enable_network = enable_network
        self._ensure_cache_dir()
        self._curated_knowledge = self._init_curated_knowledge()

    def _ensure_cache_dir(self) -> None:
        """確保快取目錄存在"""
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
        except Exception:
            pass

    def _get_cache_path(self, key: str) -> str:
        """取得特定鍵值的快取檔案路徑"""
        safe_key = re.sub(r'[\\/*?:"<>| ]', '_', key.strip().lower())
        return os.path.join(self.cache_dir, f"{safe_key}.json")

    def _read_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """讀取本地磁碟快取"""
        path = self._get_cache_path(key)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def _write_cache(self, key: str, data: Dict[str, Any]) -> None:
        """寫入本地磁碟快取"""
        path = self._get_cache_path(key)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def search_game_knowledge(
        self,
        query: str,
        game_type: Optional[GameType] = None,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        全域遊戲情報檢索（結合網路採集與內建精選百科）
        """
        query_clean = query.strip()
        cache_key = f"search_{game_type.name if game_type else 'all'}_{query_clean}"
        cached = self._read_cache(cache_key)
        if cached and isinstance(cached.get("results"), list):
            return cached["results"]

        results: List[Dict[str, Any]] = []

        # 1. 檢索內建精選知識庫 (Curated Knowledge)
        for entry in self._curated_knowledge:
            if game_type and entry.get("game_type") != game_type.name and entry.get("game_type") != "ALL":
                continue
            title = entry.get("title") or entry.get("character") or entry.get("boss") or entry.get("target") or "遊戲情報"
            tags = entry.get("tags", [])
            content = entry.get("content", "") or entry.get("mechanism", "")
            
            # 關鍵字匹配度計算
            matches = sum(1 for q in query_clean.split() if q.lower() in (title + " " + " ".join(tags) + " " + content).lower())
            if matches > 0:
                results.append({
                    "title": title,
                    "snippet": content[:180] + ("..." if len(content) > 180 else ""),
                    "source": entry.get("source", "內建遊戲精選百科"),
                    "score": matches * 10,
                    "tags": tags,
                    "full_content": content,
                    "game_type": entry.get("game_type", "GENERAL")
                })

        # 2. 若啟用網路且結果不足，嘗試網路連線採集 (Web Crawling)
        if self.enable_network and len(results) < max_results:
            net_results = self._fetch_from_network(query_clean, game_type)
            results.extend(net_results)

        # 排序並限制數量
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        final_results = results[:max_results]

        # 寫入快取
        self._write_cache(cache_key, {"results": final_results})
        return final_results

    def fetch_character_build_guide(
        self,
        character_name: str,
        game_type: Optional[GameType] = None
    ) -> Dict[str, Any]:
        """
        查詢特定角色的養成配裝攻略（聖遺物/音擎/遺器、主副詞條、天賦升級、配隊）
        """
        char_name = character_name.strip()
        cache_key = f"build_{game_type.name if game_type else 'all'}_{char_name}"
        cached = self._read_cache(cache_key)
        if cached:
            return cached

        # 比對知識庫
        for entry in self._curated_knowledge:
            if entry.get("category") == "character_build":
                target_char = entry.get("character", "")
                alias = entry.get("alias", [])
                if char_name.lower() in [target_char.lower()] + [a.lower() for a in alias]:
                    data = {
                        "character": target_char,
                        "game_type": entry.get("game_type"),
                        "best_equipment": entry.get("best_equipment", []),
                        "stat_priority": entry.get("stat_priority", {}),
                        "skill_priority": entry.get("skill_priority", []),
                        "team_recommendations": entry.get("team_recommendations", []),
                        "summary": entry.get("content", ""),
                        "source": "精選角色培育資料庫"
                    }
                    self._write_cache(cache_key, data)
                    return data

        # 啟發式通用生成 (Heuristic Fallback)
        fallback_data = {
            "character": char_name,
            "game_type": game_type.name if game_type else "GENERAL",
            "best_equipment": ["專屬/推薦套裝 (4件套)", "泛用過渡 2+2 套裝"],
            "stat_priority": {
                "sand_or_body": "攻擊力百分比 / 雙暴",
                "goblet_or_sphere": "對應屬性傷害加成",
                "circlet_or_rope": "暴擊率 / 暴擊傷害 / 能量充能"
            },
            "skill_priority": ["主輸出戰技/終結技", "核心被動天賦", "普通攻擊"],
            "team_recommendations": ["主C + 專屬輔助 + 生存位/護盾 + 副C/聚怪"],
            "summary": f"已由網路感官系統為【{char_name}】生成標準通用培育骨架，建議優先拉滿雙暴與屬性增傷。",
            "source": "通用自律推論分析"
        }
        self._write_cache(cache_key, fallback_data)
        return fallback_data

    def fetch_exploration_targets(
        self,
        location_or_target: str,
        game_type: Optional[GameType] = None
    ) -> Dict[str, Any]:
        """
        查詢大地圖探索點位、特產採集與解謎導引
        """
        loc_clean = location_or_target.strip()
        cache_key = f"explore_{game_type.name if game_type else 'all'}_{loc_clean}"
        cached = self._read_cache(cache_key)
        if cached:
            return cached

        tokens = [t.lower() for t in loc_clean.split()]
        for entry in self._curated_knowledge:
            if entry.get("category") == "exploration":
                target = entry.get("target", "").lower()
                tags = [t.lower() for t in entry.get("tags", [])]
                all_text = target + " " + " ".join(tags)
                if any(tok in all_text for tok in tokens):
                    data = {
                        "target": entry.get("target", ""),
                        "game_type": entry.get("game_type"),
                        "routes": entry.get("routes", []),
                        "mechanism": entry.get("mechanism", ""),
                        "tips": entry.get("tips", []),
                        "source": "精選大世界探索圖鑑"
                    }
                    self._write_cache(cache_key, data)
                    return data

        fallback_data = {
            "target": loc_clean,
            "game_type": game_type.name if game_type else "GENERAL",
            "routes": ["自最近傳送錨點出發，沿地形邊緣順時針探索"],
            "mechanism": "注意地圖高低差指示與元素視野/機巧掃描反應",
            "tips": ["開啟夜間加速模式", "攜帶雙風/跑圖特化角色"],
            "source": "通用自律探索推論"
        }
        self._write_cache(cache_key, fallback_data)
        return fallback_data

    def fetch_boss_mechanics(
        self,
        boss_name: str,
        game_type: Optional[GameType] = None
    ) -> Dict[str, Any]:
        """
        查詢 Boss 戰鬥機制、大招前奏警示音與應對策略
        """
        name_clean = boss_name.strip()
        cache_key = f"boss_{game_type.name if game_type else 'all'}_{name_clean}"
        cached = self._read_cache(cache_key)
        if cached:
            return cached

        for entry in self._curated_knowledge:
            if entry.get("category") == "boss_mechanics":
                boss = entry.get("boss", "")
                if name_clean.lower() in boss.lower() or any(name_clean.lower() in a.lower() for a in entry.get("alias", [])):
                    data = {
                        "boss": boss,
                        "game_type": entry.get("game_type"),
                        "phases": entry.get("phases", []),
                        "dangerous_skills": entry.get("dangerous_skills", []),
                        "warning_cues": entry.get("warning_cues", []),
                        "counters": entry.get("counters", []),
                        "source": "精選強敵戰鬥指南"
                    }
                    self._write_cache(cache_key, data)
                    return data

        fallback_data = {
            "boss": name_clean,
            "game_type": game_type.name if game_type else "GENERAL",
            "phases": ["通常階段", "狂暴/蓄力大招階段"],
            "dangerous_skills": ["全場範圍地面重砸", "多段追蹤彈幕"],
            "warning_cues": ["高頻警報音效", "地面紅圈擴散", "前置蓄力硬直動作"],
            "counters": ["看準前搖閃避觸發無敵幀", "破壞蓄力護盾或進行打斷", "預先開啟全隊護盾"],
            "source": "通用首領防禦反應庫"
        }
        self._write_cache(cache_key, fallback_data)
        return fallback_data

    def summarize_for_jev(self, knowledge_dict: Dict[str, Any]) -> str:
        """
        將非結構化或半結構化情報壓縮轉化為 Jev 高密度 Predicate 上下文
        """
        parts = []
        if "character" in knowledge_dict:
            parts.append(f"角色:{knowledge_dict['character']}")
        if "boss" in knowledge_dict:
            parts.append(f"首領:{knowledge_dict['boss']}")
        if "target" in knowledge_dict:
            parts.append(f"目標:{knowledge_dict['target']}")
        if "best_equipment" in knowledge_dict:
            eq = "/".join(knowledge_dict["best_equipment"][:2])
            parts.append(f"推薦裝備:[{eq}]")
        if "stat_priority" in knowledge_dict:
            stats = str(knowledge_dict["stat_priority"])[:60]
            parts.append(f"詞條:{stats}")
        if "warning_cues" in knowledge_dict:
            cues = ",".join(knowledge_dict["warning_cues"][:2])
            parts.append(f"危險警訊:[{cues}]")
        if "counters" in knowledge_dict:
            counters = ",".join(knowledge_dict["counters"][:2])
            parts.append(f"應對:[{counters}]")
        if "summary" in knowledge_dict:
            parts.append(f"摘要:{knowledge_dict['summary'][:80]}")
        return " | ".join(parts) if parts else "情報已就緒"

    def _fetch_from_network(self, query: str, game_type: Optional[GameType]) -> List[Dict[str, Any]]:
        """
        從網路進行 HTTP 查詢（具備逾時與例外隔離）
        """
        results: List[Dict[str, Any]] = []
        try:
            # 針對米哈遊與熱門遊戲百科進行安全 API 檢索（示範 DuckDuckGo API 或開放查詢）
            encoded_query = urllib.parse.quote_plus(f"{game_type.value if game_type else ''} {query}")
            url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1&skip_disambig=1"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "GameAssistant-SensoryBot/0.2.0"}
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status == 200:
                    payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    abstract = payload.get("AbstractText", "")
                    heading = payload.get("Heading", query)
                    if abstract:
                        results.append({
                            "title": heading,
                            "snippet": abstract,
                            "source": payload.get("AbstractURL", "DuckDuckGo Instant Answer"),
                            "score": 8,
                            "tags": ["網路即時情報"],
                            "full_content": abstract,
                            "game_type": game_type.name if game_type else "GENERAL"
                        })
        except Exception:
            # 網路離線或受阻時安全靜默，保證不影響遊戲助手主循環
            pass
        return results

    def _init_curated_knowledge(self) -> List[Dict[str, Any]]:
        """
        預置經典三遊戲與泛用模式的高品質離線知識庫
        """
        return [
            # === 原神：角色培育 ===
            {
                "category": "character_build",
                "character": "那維萊特",
                "alias": ["龍王", "水龍", "那維"],
                "game_type": GameType.GENSHIN.name,
                "best_equipment": ["萬世流湧的大典", "遺祀玉瓏", "試作金珀", "逐影獵人 4件套"],
                "stat_priority": {
                    "sand": "生命值百分比",
                    "goblet": "水元素傷害加成 / 生命值百分比",
                    "circlet": "暴擊傷害 / 暴擊率 (維持逐影觸發後 64% 暴擊率)"
                },
                "skill_priority": ["普通攻擊·如水如波 (首要滿級)", "元素戰技·淚光啊", "元素爆發·潮湧啊"],
                "team_recommendations": ["那維萊特 + 芙寧娜 + 萬葉 + 白朮/鐘離", "那維萊特 + 鐘離 + 菲謝爾 + 萬葉"],
                "content": "那維萊特以重擊蓄力激流為核心輸出，逐影獵人4件套提供36%暴擊率極為契合，隊伍需觸發3層古海孑遺龍王被動獲得160%重擊增傷。"
            },
            {
                "category": "character_build",
                "character": "芙寧娜",
                "alias": ["水神", "芙芙"],
                "game_type": GameType.GENSHIN.name,
                "best_equipment": ["靜水流湧之輝", "腐殖之劍", "灰河渡手", "黃金劇團 4件套"],
                "stat_priority": {
                    "sand": "生命值百分比 / 元素充能效率 (180%-200%)",
                    "goblet": "生命值百分比 / 水元素傷害加成",
                    "circlet": "暴擊率 / 暴擊傷害"
                },
                "skill_priority": ["元素爆發 (萬民狂歡 - 全隊增傷)", "元素戰技 (孤心沙龍 - 後台重砲)", "普通攻擊 (可不點)"],
                "team_recommendations": ["芙寧娜 + 那維萊特 + 楓原萬葉 + 白朮", "芙寧娜 + 雷電將軍 + 夜蘭 + 琴"],
                "content": "芙寧娜透過戰技後台全自動輸出消耗隊伍生命，大招萬民狂歡依全隊生命變動堆疊氣氛值，提供極高全隊增傷，黃金劇團4件套增傷70%戰技傷害。"
            },
            # === 崩鐵：角色培育 ===
            {
                "category": "character_build",
                "character": "黃泉",
                "alias": ["Acheron", "雷巡獵", "虛無C"],
                "game_type": GameType.STAR_RAIL.name,
                "best_equipment": ["行於流逝的岸", "晚安與睡顏", "死水深潛的先驅 4件套", "出雲顯見與高天神國 2件套"],
                "stat_priority": {
                    "body": "暴擊傷害 / 暴擊率",
                    "feet": "攻擊力百分比 / 速度 (推薦慢速純爆發流)",
                    "sphere": "雷屬性傷害提高 / 攻擊力百分比",
                    "rope": "攻擊力百分比"
                },
                "skill_priority": ["終結技·殘夢盡染 (首要滿級)", "天賦·紅葉喋血", "戰技·八雷飛渡"],
                "team_recommendations": ["黃泉 + 椒丘 + 佩拉 + 砂金/符玄", "黃泉 + 黑天鵝 + 卡芙卡 + 藿藿"],
                "content": "黃泉無能量條，仰賴隊友施加負面狀態累積【殘夢】9層開啟毀滅性終結技。死水4件套對負面目標暴擊率與暴傷大幅提升，椒丘為最頂級充能增傷隊友。"
            },
            {
                "category": "character_build",
                "character": "流螢",
                "alias": ["Firefly", "薩姆", "擊破C"],
                "game_type": GameType.STAR_RAIL.name,
                "best_equipment": ["夢應歸於何處", "記一位星神的隕落", "盪除蠹災的鐵騎 4件套", "劫火蓮燈鑄煉宮 2件套"],
                "stat_priority": {
                    "body": "攻擊力百分比",
                    "feet": "速度 (首選 150+ 局內觸發四動)",
                    "sphere": "攻擊力百分比",
                    "rope": "擊破特攻 (追求 250%-360%+)"
                },
                "skill_priority": ["終結技·火火入定", "天賦", "戰技"],
                "team_recommendations": ["流螢 + 同諧開拓者 + 阮·梅 + 加拉赫/靈砂"],
                "content": "超級擊破核心主C，開大進入完全燃燒狀態無視弱點削韌。鐵騎4件套在超擊破時無視防禦最高25%，必須綁定同諧主與阮梅組成超擊破國家隊。"
            },
            # === 絕區零：角色培育 ===
            {
                "category": "character_build",
                "character": "艾蓮·喬",
                "alias": ["鯊魚妹", "艾蓮", "Ellen"],
                "game_type": GameType.ZZZ.name,
                "best_equipment": ["深海訪客", "加農轉子", "極地重金屬 4件套", "啄木鳥電音 2件套"],
                "stat_priority": {
                    "disc_4": "暴擊率 / 暴擊傷害",
                    "disc_5": "冰屬性傷害加成 / 穿透率",
                    "disc_6": "攻擊力百分比 / 能量自動回復"
                },
                "skill_priority": ["普通攻擊·鯊魚步剪擊", "終結技·永冬風暴", "特殊技·尾擊突刺"],
                "team_recommendations": ["艾蓮 + 萊卡恩 (狼哥失衡) + 蒼角 (冰屬拐)", "艾蓮 + 青衣 + 露西"],
                "content": "艾蓮核心機制為巡遊衝刺蓄力剪擊獲得【急凍充能】，普攻轉為高倍率冰傷。極地4件套配合凍結觸發28%額外暴傷，失衡期切出進行三段蓄力爆發。"
            },
            {
                "category": "character_build",
                "character": "朱鳶",
                "alias": ["朱局", "警官", "以太強攻"],
                "game_type": GameType.ZZZ.name,
                "best_equipment": ["防暴者VI型", "硫磺石", "混沌爵士 / 啄木鳥 4件套", "河豚電音 2件套"],
                "stat_priority": {
                    "disc_4": "暴擊傷害 (被動自帶高暴擊)",
                    "disc_5": "以太屬性傷害加成",
                    "disc_6": "攻擊力百分比"
                },
                "skill_priority": ["普通攻擊·壓制霰彈", "終結技·特勤火力掃射", "連攜技"],
                "team_recommendations": ["朱鳶 + 青衣 (頂級失衡) + 妮可 (以太減防聚怪)"],
                "content": "朱鳶極度依賴壓制霰彈槍子彈發射連射。最佳輸出手法為擊發失衡後，妮可降防接朱鳶連攜技與長按普攻壓制射擊，秒傷極為驚人。"
            },
            # === 大世界探索情報 ===
            {
                "category": "exploration",
                "target": "原神 納塔燃素與神瞳探索",
                "tags": ["原神", "納塔", "神瞳", "燃素", "特產"],
                "game_type": GameType.GENSHIN.name,
                "routes": [
                    "聖火競技場傳送點出發 ➔ 附身匿葉龍採集高空卷心菜與火神瞳",
                    "流泉之眾沿河流 ➔ 附身鰭遊龍進行水下衝刺飛越瀑布"
                ],
                "mechanism": "納塔地區特有燃素槽機制：附身三種龍（匿葉、鰭遊、嵴鋒）進行超地形移動；進入夜魂迸發狀態提升採集效率。",
                "tips": ["多利用夜魂傳送點隨時補充燃素", "攜帶瑪拉妮或卡齊娜標記納塔特產"]
            },
            {
                "category": "exploration",
                "target": "崩鐵 匹諾康尼折紙小鳥與寶箱導航",
                "tags": ["星穹鐵道", "匹諾康尼", "折紙小鳥", "夢境", "寶箱"],
                "game_type": GameType.STAR_RAIL.name,
                "routes": [
                    "黃金的時刻二樓愛麗絲雕像 ➔ 逐一拉扯路燈與氣球中的小鳥羽毛",
                    "白日夢酒店夢境 ➔ 透過夢境泡泡充能走上牆面與天花板取得隱藏寶箱"
                ],
                "mechanism": "利用【夢客行者】重力反轉走牆壁解謎；收集全部折紙小鳥可兌換4星光錐與大量星瓊。",
                "tips": ["使用黃泉戰技可直接斬殺小怪免除戰鬥拖慢探索節奏", "利用機巧鳥視角巡視高處死角"]
            },
            {
                "category": "exploration",
                "target": "絕區零 空洞探索走格子與邦布插件",
                "tags": ["絕區零", "空洞", "走格子", "喵吉", "邦布"],
                "game_type": GameType.ZZZ.name,
                "routes": [
                    "觀察齒輪金幣分布 ➔ 優先走隱藏裂隙與金色傳送門",
                    "踩中警戒格前預備解鎖安全閥 ➔ 避免侵蝕度突破100觸發全隊負面失真"
                ],
                "mechanism": "空洞電視機格子機制：善用炸彈開拓隱藏通道；透過觀測數據收集解鎖 S 級結算通關評價。",
                "tips": ["攜帶尋寶型邦布插件提高丁尼掉落率", "侵蝕度高時優先踩綠十字醫院格減壓"]
            },
            # === 首領機制與警報 ===
            {
                "category": "boss_mechanics",
                "boss": "吞星之鯨",
                "alias": ["全生之鯨", "周本水鯨魚"],
                "game_type": GameType.GENSHIN.name,
                "phases": ["巨鯨形態 (海面巡弋)", "幻影騎士形態 (巨鯨胃中決鬥)"],
                "dangerous_skills": ["全場落水重砸", "幻影騎士黑雷三連橫掃", "星海漩渦牽引"],
                "warning_cues": ["警報：全場海面泛紫光並出現倒數光圈", "幻影騎士蓄力拔刀雷光音效"],
                "counters": ["使用荒性/芒性攻擊打斷鯨魚蓄力", "胃中迅速擊破幻影騎士護盾破防癱瘓鯨魚"]
            },
            {
                "category": "boss_mechanics",
                "boss": "「齊響詩班」神主日",
                "alias": ["星期日", "哲學胎兒", "周本神主日"],
                "game_type": GameType.STAR_RAIL.name,
                "phases": ["第一階段：三合一化身", "第二階段：太初之歌群體護盾", "第三階段：終末啟示太初大招"],
                "dangerous_skills": ["太初之歌 (全隊巨量穿透護盾打擊)", "神罰天譴 (單體秒殺禁錮)"],
                "warning_cues": ["警報：神主日雙手合十鐘鳴聲迴盪", "背景合唱曲高潮前夕蓄力條滿溢"],
                "counters": ["利用鐘錶小子火車列車撞擊破韌全體化身", "知更鳥開大拉條全體進行連續削韌打碎護盾"]
            },
            {
                "category": "boss_mechanics",
                "boss": "龐培 / 屠夫 / 芭萊雙子",
                "alias": ["空洞屠夫", "雙子舞者", "Pompey"],
                "game_type": GameType.ZZZ.name,
                "phases": ["單體狂暴突刺", "雙子交替合體旋風連斬"],
                "dangerous_skills": ["紅光大招：全屏烈焰重砸 (不可招架)", "黃光三連斬 (必須連續彈刀換人)"],
                "warning_cues": ["刺耳黃光叮嚀聲 (極限支援彈刀時機)", "奪目紅光閃爍 (強制極限閃避)"],
                "counters": ["黃光閃爍瞬間按空白鍵觸發招架支援與擊破失衡", "紅光立即按右鍵進行無敵幀滑行閃避"]
            }
        ]
