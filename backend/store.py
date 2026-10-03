import ast
import json
import re
import threading
from datetime import date, datetime, time
from typing import Any

from rdflib import Graph, RDF, URIRef
from pyshacl import validate

from .config import CONTAINER_FILE, DATA_DIR, GRAPH_FILE, PROPERTIES_FILE, SHAPES_FILE
from .model import CLASSES, PO, graph_to_record, node_uri, object_to_graph
from .vault import Container, ContainerMissing, VaultError, WrongPassword


class StoreError(Exception):
    pass


class StoreLocked(StoreError):
    """容器处于锁定态：没有密钥，也没有内存中的图。"""


class ValidationError(StoreError):
    def __init__(self, report: str):
        super().__init__(report)
        self.report = report


class RDFStore:
    """本体存储。

    磁盘上只有加密容器（见 docs/05）；启动时不读取任何数据，处于锁定态。
    只有 `unlock()` / `initialize()` 之后才有内存中的图。
    """

    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._mutex = threading.RLock()
        self.graph: Graph | None = None
        self.namespace_migration: dict[str, Any] | None = None
        self.vault = Container(CONTAINER_FILE)
        self.legacy_file = GRAPH_FILE

    # ---------- 状态 ----------
    @property
    def initialized(self) -> bool:
        return self.vault.exists

    @property
    def unlocked(self) -> bool:
        return self.graph is not None

    @property
    def revision(self) -> int:
        return self.vault.revision

    @property
    def has_legacy_plaintext(self) -> bool:
        """存在旧版明文图（尚未迁移）。"""
        return self.legacy_file.exists()

    def status(self) -> dict[str, Any]:
        info: dict[str, Any] = {"initialized": self.initialized, "unlocked": self.unlocked,
                                "legacy_plaintext": self.has_legacy_plaintext, "revision": None}
        if self.initialized:
            try:
                doc = self.vault.read_document()
                info["revision"] = int(doc.get("revision", 0))
                section = (doc.get("sections") or {}).get("ontology") or {}
                kdf = section.get("kdf") or {}
                info["kdf"] = {"name": kdf.get("name"), "iterations": kdf.get("iterations")}
                info["updated_at"] = doc.get("updated_at")
            except VaultError as exc:
                info["error"] = str(exc)
        return info

    # ---------- 生命周期 ----------
    def _bind(self, graph: Graph) -> None:
        graph.bind("po", PO)
        graph.bind("rdf", RDF)
        graph.bind("xsd", "http://www.w3.org/2001/XMLSchema#")

    def _build_graph(self, payload: bytes) -> Graph:
        graph = Graph()
        self._bind(graph)
        graph.parse(data=payload.decode("utf-8"), format="turtle")
        return graph

    def _migrate_namespace_if_needed(self, payload: bytes) -> bytes:
        """把已存图里的 RDF 命名空间升级为当前代码使用的命名空间。

        为什么需要：命名空间会被写进**每一条三元组**。升级代码后若不改数据，按新命名空间
        查询将一无所获——界面会看起来"本体空了"。放在解锁时自动做，避免"代码新、数据旧"
        的窗口，也避免要求用户手工跑脚本（迁移需要口令，而后端此刻正持有它）。

        安全措施：先备份容器文件；只重写 `ontology` 段；写前核对三元组数量；
        已是目标命名空间时直接返回（可重复执行）。
        """
        import datetime, shutil
        text = payload.decode("utf-8")
        target = str(PO)
        # 不能靠 `@prefix po:` 检测：rdflib 序列化时会把前缀名写成 ns1 之类，
        # 甚至只在谓词处用前缀、类型处用完整 URI。因此改为从**实际出现的命名空间**里找：
        # 取所有 `<…>` 中不以 http://www.w3.org 开头、且以 `#` 结尾的候选
        #（主语 URI 方案 `urn:personal-ontology:…` 不带 `#`，因此不会被误选）。
        candidates = {u for u in re.findall(r"<([^<>]*#)>", text) if not u.startswith("http://www.w3.org")}
        if not candidates or (len(candidates) == 1 and next(iter(candidates)) == target):
            return payload
        legacy = target if False else None
        for cand in sorted(candidates, key=len, reverse=True):
            if cand != target:
                legacy = cand
                break
        if legacy is None:
            return payload
        rewritten = text.replace(legacy, target)
        try:
            before = Graph(); before.parse(data=text, format="turtle")
            after = Graph(); after.parse(data=rewritten, format="turtle")
        except Exception:
            return payload
        if len(before) != len(after) or legacy in rewritten:
            return payload
        try:
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy2(self.vault.path, self.vault.path.with_suffix(self.vault.path.suffix + f".bak-{stamp}"))
        except OSError:
            pass
        self.vault.put_section("ontology", rewritten.encode("utf-8"))
        self.namespace_migration = {"from": legacy, "to": target, "triples": len(after)}
        print(f"[store] RDF 命名空间已迁移：{legacy} → {target}（{len(after)} 条三元组，容器已备份）", flush=True)
        return rewritten.encode("utf-8")

    def initialize(self, password: str, ontology: bytes, model_service: bytes) -> None:
        """首次创建容器（可携带待迁移的明文图），成功后处于解锁态。"""
        with self._mutex:
            self.vault.create(password, {"ontology": ontology, "model_service": model_service})
            ontology = self._migrate_namespace_if_needed(ontology)
            self.graph = self._build_graph(ontology)
            if self._ensure_builtins():
                self._persist()

    def unlock(self, password: str) -> None:
        """校验口令并把图载入内存。错口令抛 WrongPassword，锁定态不变。"""
        with self._mutex:
            self.vault.unlock(password)
            payload = self._migrate_namespace_if_needed(self.vault.get_section("ontology"))
            graph = self._build_graph(payload)
            self.graph = graph
            if self._ensure_builtins():
                self._persist()

    def lock(self) -> None:
        with self._mutex:
            self.graph = None
            self.vault.lock()

    def change_password(self, current: str, new: str) -> None:
        with self._mutex:
            self.vault.change_password(current, new)

    def _require_unlocked(self) -> Graph:
        if self.graph is None:
            raise StoreLocked("本体已锁定，请先登录。")
        return self.graph

    def _ensure_builtins(self) -> bool:
        builtins = [
            ("decision-results", "allow", {"display_name_zh":"允许", "display_name_en":"Allow", "severity":0, "next_action":"execute"}),
            ("decision-results", "deny", {"display_name_zh":"拒绝", "display_name_en":"Deny", "severity":9, "next_action":"refuse"}),
            ("decision-results", "ask", {"display_name_zh":"需确认", "display_name_en":"Ask", "severity":5, "next_action":"pause"}),
            ("decision-results", "pause", {"display_name_zh":"暂停", "display_name_en":"Pause", "severity":5, "next_action":"pause"}),
            ("matchers", "glob", {"display_name_zh":"通配符匹配", "display_name_en":"Wildcard", "description_zh":"* 可匹配任意字符，例如 /文档/*"}),
            ("matchers", "exact", {"display_name_zh":"完全匹配", "display_name_en":"Exact", "description_zh":"只匹配完整资源名称"}),
            ("matchers", "prefix", {"display_name_zh":"开头匹配", "display_name_en":"Prefix", "description_zh":"匹配以指定文字开头的资源"}),
            ("actions", "file.read", {"display_name_zh":"查看文件", "display_name_en":"Read", "applies_to":"file", "risk_level":"low"}),
            ("actions", "file.write", {"display_name_zh":"编辑文件", "display_name_en":"Write", "applies_to":"file", "risk_level":"medium"}),
            ("actions", "file.delete", {"display_name_zh":"删除文件", "display_name_en":"Delete", "applies_to":"file", "risk_level":"high"}),
            ("actions", "app.launch", {"display_name_zh":"打开应用", "display_name_en":"Launch", "applies_to":"app", "risk_level":"low"}),
            ("actions", "app.control", {"display_name_zh":"控制应用", "display_name_en":"Control", "applies_to":"app", "risk_level":"high"}),
            ("actions", "network.connect", {"display_name_zh":"连接网络", "display_name_en":"Connect", "applies_to":"network", "risk_level":"medium"}),
            ("actions", "network.send", {"display_name_zh":"发送网络数据", "display_name_en":"Send", "applies_to":"network", "risk_level":"high"}),
            ("resource-types", "file", {"type_name":"file", "display_name_zh":"文件", "display_name_en":"File", "matcher_id":"glob", "actions":["file.read","file.write","file.delete"], "default_priority":0, "is_builtin":True}),
            ("resource-types", "app", {"type_name":"app", "display_name_zh":"应用", "display_name_en":"Application", "matcher_id":"glob", "actions":["app.launch","app.control"], "default_priority":0, "is_builtin":True}),
            ("resource-types", "network", {"type_name":"network", "display_name_zh":"网络连接", "display_name_en":"Network", "matcher_id":"glob", "actions":["network.connect","network.send"], "default_priority":0, "is_builtin":True}),
        ]
        added = False
        for collection, item_id, record in builtins:
            subject = node_uri(collection, item_id)
            if (subject, RDF.type, PO[CLASSES[collection]]) not in self.graph:
                object_to_graph(self.graph, collection, item_id, record)
                added = True
        return added

    def _validate(self, candidate: Graph) -> None:
        shapes = Graph().parse(SHAPES_FILE, format="turtle")
        ontology = Graph().parse(PROPERTIES_FILE, format="turtle")
        # Include the metamodel property declarations while keeping instance data separate.
        ontology += candidate
        conforms, report_graph, report_text = validate(
            ontology, shacl_graph=shapes, inference="rdfs", abort_on_first=False,
            allow_infos=False, allow_warnings=False, meta_shacl=False,
        )
        if not conforms:
            raise ValidationError(report_text or report_graph.serialize(format="turtle"))

    def _persist(self) -> None:
        """把内存中的图加密写回容器（原子替换由 vault 负责）。"""
        payload = self._require_unlocked().serialize(format="turtle", encoding="utf-8")
        try:
            self.vault.put_section("ontology", payload)
        except VaultError as exc:
            # 回滚由调用方负责（put/delete/rename 会恢复旧图）
            raise StoreError(f"容器写入失败：{exc}") from exc

    def list(self, collection: str) -> list[dict[str, Any]]:
        self._check_collection(collection)
        with self._mutex:
            graph = self._require_unlocked()
            nodes = set(graph.subjects(RDF.type, PO[CLASSES[collection]]))
            return [graph_to_record(graph, collection, self._id_from_uri(n)) for n in sorted(nodes, key=str)]

    def get(self, collection: str, item_id: str) -> dict[str, Any] | None:
        self._check_collection(collection)
        with self._mutex:
            graph = self._require_unlocked()
            subject = node_uri(collection, item_id)
            if (subject, RDF.type, PO[CLASSES[collection]]) not in graph:
                return None
            return graph_to_record(graph, collection, item_id)

    def put(self, collection: str, item_id: str, record: dict[str, Any], *, create_only: bool = False) -> dict[str, Any]:
        self._check_collection(collection)
        if not item_id or len(item_id) > 200:
            raise StoreError("id must be 1..200 characters")
        with self._mutex:
            current = self._require_unlocked()
            candidate = Graph()
            for triple in current: candidate.add(triple)
            subject = node_uri(collection, item_id)
            exists = (subject, RDF.type, PO[CLASSES[collection]]) in candidate
            if create_only and exists:
                raise FileExistsError(item_id)
            for triple in list(candidate.triples((subject, None, None))): candidate.remove(triple)
            # 联系方式不再单独加密：容器已整体加密（docs/05 §7.1）。
            object_to_graph(candidate, collection, item_id, dict(record))
            self._validate(candidate)
            old = self.graph
            self.graph = candidate
            try: self._persist()
            except Exception:
                self.graph = old
                raise
            return graph_to_record(self._require_unlocked(), collection, item_id)

    def delete(self, collection: str, item_id: str) -> bool:
        self._check_collection(collection)
        with self._mutex:
            current = self._require_unlocked()
            subject = node_uri(collection, item_id)
            if (subject, RDF.type, PO[CLASSES[collection]]) not in current: return False
            candidate = Graph()
            for triple in current: candidate.add(triple)
            candidate.remove((subject, None, None))
            # Protect referential integrity. Do not leave dangling subject references.
            inbound = list(candidate.triples((None, None, subject)))
            if inbound: raise StoreError(f"cannot delete; referenced by {len(inbound)} record(s)")
            self._validate(candidate)
            old = self.graph
            self.graph = candidate
            try: self._persist()
            except Exception:
                self.graph = old
                raise
            return True

    def rename(self, collection: str, old_id: str, new_id: str, record: dict[str, Any]) -> dict[str, Any]:
        """Rename a node and atomically retarget every inbound RDF reference."""
        self._check_collection(collection)
        if not new_id or len(new_id) > 200:
            raise StoreError("id must be 1..200 characters")
        with self._mutex:
            current = self._require_unlocked()
            old_subject = node_uri(collection, old_id)
            new_subject = node_uri(collection, new_id)
            if (old_subject, RDF.type, PO[CLASSES[collection]]) not in current:
                raise KeyError(old_id)
            if (new_subject, RDF.type, PO[CLASSES[collection]]) in current:
                raise FileExistsError(new_id)

            candidate = Graph()
            for triple in current:
                candidate.add(triple)
            # Move incoming references first so authorization and taxonomy edges stay connected.
            for subject, predicate, _ in list(candidate.triples((None, None, old_subject))):
                if subject != old_subject:
                    candidate.remove((subject, predicate, old_subject))
                    candidate.add((subject, predicate, new_subject))
            for triple in list(candidate.triples((old_subject, None, None))):
                candidate.remove(triple)

            object_to_graph(candidate, collection, new_id, dict(record))
            self._validate(candidate)
            old_graph = self.graph
            self.graph = candidate
            try:
                self._persist()
            except Exception:
                self.graph = old_graph
                raise
            return graph_to_record(self._require_unlocked(), collection, new_id)

    def evaluate(self, request: dict[str, Any]) -> dict[str, Any]:
        required = ("principal_id", "action_id", "resource_type_id", "resource_id")
        missing = [key for key in required if not request.get(key)]
        if missing:
            return {"result_id":"ask", "next_action":"pause", "reason_key":"decision.missing_input", "reason_params":{"fields":missing}, "cited_assertions":[], "context_keys_used":["source_trust"]}
        principal = self.get("principals", str(request["principal_id"]))
        action = self.get("actions", str(request["action_id"]))
        if not principal or not action:
            return {"result_id":"deny", "next_action":"refuse", "reason_key":"decision.unknown_principal_or_action", "reason_params":{}, "cited_assertions":[], "context_keys_used":["source_trust"]}
        resource_type = self.get("resource-types", str(request["resource_type_id"]))
        context = request.get("context") if isinstance(request.get("context"), dict) else {}
        missing_params = []
        resource_params = (resource_type or {}).get("params", [])
        if not isinstance(resource_params, list): resource_params = [resource_params] if resource_params else []
        for param_id in resource_params:
            param = self.get("params", str(param_id)) or {}
            name = str(param.get("param_name") or "")
            if param.get("required") is True and (not name or context.get(name) is None or context.get(name) == ""):
                missing_params.append({"name":name or str(param_id), "label":param.get("display_name_zh") or name or str(param_id)})
        if missing_params:
            return {"result_id":"ask", "next_action":"pause", "reason_key":"decision.required_context_missing", "reason_params":{"fields":[x["name"] for x in missing_params], "labels":[x["label"] for x in missing_params]}, "cited_assertions":[str(request["resource_type_id"])], "context_keys_used":["source_trust"]}
        try:
            candidates = self.list("authorizations")
            redlines = self.list("redlines")
        except Exception:
            return {"result_id":"pause", "next_action":"pause", "reason_key":"decision.policy_unavailable", "reason_params":{}, "cited_assertions":[], "context_keys_used":["source_trust"]}
        for redline in redlines:
            pattern = redline.get("redline_pattern", "")
            if pattern and _safe_match(pattern, str(request["resource_id"]), "glob"):
                return {"result_id":"deny", "next_action":"refuse", "reason_key":"decision.redline", "reason_params":{"redline_id":redline["id"]}, "cited_assertions":[redline["id"]], "context_keys_used":["source_trust"]}
        ancestry = {str(request["principal_id"])}
        cursor = principal
        for _ in range(32):
            parent_id = cursor.get("parent_id")
            if not parent_id: break
            parent_id = str(parent_id)
            if parent_id in ancestry: break
            ancestry.add(parent_id)
            cursor = self.get("principals", parent_id) or {}
        matched = []
        used_context_keys = {"source_trust"}   # 风险门槛总会读取它
        for rule in candidates:
            # Legacy rules without policyStatus remain active; scene-generated rules are drafts.
            if rule.get("policy_status", "active") != "active": continue
            if rule.get("revoked") is True or rule.get("grantee_id") not in ancestry: continue
            if str(rule.get("resource_type_id")) != str(request["resource_type_id"]): continue
            # A single-valued relation comes back from the graph as a bare scalar.
            # Normalise before use: iterating the string "file.read" would compare
            # single characters (rule never matches), and a scalar constraint list
            # would be dropped by _constraints_match (conditions silently ignored).
            rule_actions = rule.get("actions", [])
            if not isinstance(rule_actions, list): rule_actions = [rule_actions] if rule_actions else []
            if str(request["action_id"]) not in {str(x) for x in rule_actions}: continue
            if not _safe_match(str(rule.get("resource_pattern", "")), str(request["resource_id"]), str(rule.get("pattern_type", "glob"))): continue
            constraints = rule.get("constraints", [])
            if not isinstance(constraints, list): constraints = [constraints] if constraints else []
            constraints = [self.get("constraints", str(cid)) or {} for cid in constraints]
            if not _constraints_match(constraints, context): continue
            # 记录这条规则实际读取了哪些上下文字段，供审计最小化使用（docs/05 §10.1）
            for item in constraints:
                if not isinstance(item, dict): continue
                decoded = decode_constraint_value(item.get("constraint_value"))
                if isinstance(decoded, dict) and decoded.get("key"): used_context_keys.add(str(decoded["key"]))
            matched.append(rule)
        matched.sort(key=lambda r: int(r.get("priority", 0)), reverse=True)
        effects = {str(r.get("effect", "deny")).lower() for r in matched}
        risk = str(action.get("risk_level", "critical"))
        trust = str(context.get("source_trust", "low"))
        if risk == "critical" and trust != "high":
            return {"result_id":"deny", "next_action":"refuse", "reason_key":"decision.critical_risk_context", "reason_params":{"source_trust":trust}, "cited_assertions":[r["id"] for r in matched], "context_keys_used":sorted(used_context_keys)}
        if risk == "high" and trust not in {"high", "medium"}:
            return {"result_id":"ask", "next_action":"pause", "reason_key":"decision.high_risk_unknown_context", "reason_params":{}, "cited_assertions":[r["id"] for r in matched], "context_keys_used":sorted(used_context_keys)}
        if "deny" in effects: result, reason = "deny", "decision.explicit_deny"
        elif "ask" in effects: result, reason = "ask", "decision.confirmation_required"
        elif "allow" in effects: result, reason = "allow", "decision.explicit_allow"
        else: result, reason = "deny", "decision.default_deny"
        result_record = self.get("decision-results", result) or {}
        return {"result_id":result, "next_action":result_record.get("next_action", "refuse"), "reason_key":reason,
                "reason_params":{}, "cited_assertions":[r["id"] for r in matched], "context_keys_used":sorted(used_context_keys),
                "phase":request.get("phase", "pre_planning")}

    @staticmethod
    def _id_from_uri(uri: URIRef) -> str:
        return str(uri).rsplit(":", 1)[-1]

    @staticmethod
    def _check_collection(collection: str) -> None:
        if collection not in CLASSES: raise KeyError(collection)

def _safe_match(pattern: str, value: str, matcher: str) -> bool:
    if len(pattern) > 512 or len(value) > 8192: return False
    if matcher == "exact": return pattern == value
    if matcher == "prefix": return value.startswith(pattern)
    if matcher == "glob":
        from fnmatch import fnmatchcase
        return fnmatchcase(value, pattern)
    # Arbitrary regular expressions are intentionally not evaluated in this process.
    return False

_TIME_RE = re.compile(r"^(\d{1,2})\s*[:：点时]\s*(\d{1,2})?\s*(?:[:：]\s*(\d{1,2}))?\s*分?$")
_LATIN_CLOCK_RE = re.compile(r"^(\d{1,2})(?::(\d{2})(?::(\d{2}))?)?\s*(a\.?m\.?|p\.?m\.?)$", re.IGNORECASE)
_NUM_DATE_RE = re.compile(r"^(\d{1,4})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,4})\s*日?$")
_EN_MONTH_FIRST_RE = re.compile(r"^([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(\d{4})$")
_EN_DAY_FIRST_RE = re.compile(r"^(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?\s*,?\s*(\d{4})$")
_EN_MONTHS = {name: number for number, names in {
    1: ("january", "jan"), 2: ("february", "feb"), 3: ("march", "mar"), 4: ("april", "apr"),
    5: ("may",), 6: ("june", "jun"), 7: ("july", "jul"), 8: ("august", "aug"),
    9: ("september", "sep", "sept"), 10: ("october", "oct"), 11: ("november", "nov"),
    12: ("december", "dec")}.items() for name in names}
# 时间/日期前后缀与修饰词：中英文都要认，方向由操作符决定
_TEMPORAL_QUALIFIERS = (
    "不早于", "不晚于", "之前", "以前", "之后", "以后", "以前", "前", "后",
    "no earlier than", "no later than", "before", "after", "by", "around", "at",
)
_PERIOD_AM = ("上午", "早上", "早晨", "凌晨", "am")
_PERIOD_PM = ("中午", "下午", "傍晚", "晚上", "夜里", "pm")


def _parse_clock(text: str) -> tuple[str, float] | None:
    """解析时刻：`15:00`、`15:00:30`、`15点30分`、`下午3点`、`3 PM`、`3:30pm`。"""
    raw = text
    latin = _LATIN_CLOCK_RE.match(raw)
    if latin:
        hour = int(latin.group(1))
        if hour > 12: return None
        hour = hour % 12
        if latin.group(4).lower().startswith("p"): hour += 12
        minute, second = int(latin.group(2) or 0), int(latin.group(3) or 0)
        if minute > 59 or second > 59: return None
        return ("time", float(hour * 3600 + minute * 60 + second))
    period = ""
    lowered = raw.lower()
    for marker in _PERIOD_PM:
        if marker in {"pm"} and lowered.endswith(marker): period = "pm"; raw = raw[: -len(marker)].strip(); break
        if marker not in {"pm"} and raw.startswith(marker): period = "pm"; raw = raw[len(marker):].strip(); break
    if not period:
        for marker in _PERIOD_AM:
            if marker in {"am"} and lowered.endswith(marker): period = "am"; raw = raw[: -len(marker)].strip(); break
            if marker not in {"am"} and raw.startswith(marker): period = "am"; raw = raw[len(marker):].strip(); break
    match = _TIME_RE.match(raw)
    if not match: return None
    hour, minute, second = int(match.group(1)), int(match.group(2) or 0), int(match.group(3) or 0)
    if period == "pm" and 1 <= hour <= 11: hour += 12
    if period == "am" and hour == 12: hour = 0
    if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
        return ("time", float(hour * 3600 + minute * 60 + second))
    return None


def _parse_date(text: str) -> tuple[str, float] | None:
    """解析日期：ISO、斜杠、点号、中文、英文月份名。

    顺序有歧义的写法（如 `05/10/2026`，日月都可能）**不猜**，返回 None——
    宁可让条件编译失败并明确报出，也不要悄悄把日/月调换后去卡判定。
    """
    for pattern, order in ((_EN_MONTH_FIRST_RE, "mdy"), (_EN_DAY_FIRST_RE, "dmy")):
        match = pattern.match(text)
        if not match: continue
        if order == "mdy":
            month_name, day_text, year_text = match.group(1), match.group(2), match.group(3)
        else:
            day_text, month_name, year_text = match.group(1), match.group(2), match.group(3)
        month = _EN_MONTHS.get(month_name.lower().rstrip("."))
        if not month: return None
        try: day = date(int(year_text), month, int(day_text))
        except ValueError: return None
        return ("date", float(day.toordinal()))
    match = _NUM_DATE_RE.match(text)
    if not match: return None
    first, second, third = match.group(1), match.group(2), match.group(3)
    if len(first) == 4: year, month, day = int(first), int(second), int(third)
    elif len(third) == 4:
        # 日月顺序有歧义时不猜；只有一方 >12 才能确定
        if int(first) > 12 and int(second) <= 12: day, month = int(first), int(second)
        elif int(second) > 12 and int(first) <= 12: month, day = int(first), int(second)
        else: return None
        year = int(third)
    else:
        return None
    try: resolved = date(year, month, day)
    except ValueError: return None
    return ("date", float(resolved.toordinal()))


def parse_temporal(value: Any) -> tuple[str, float] | None:
    """把时间点/日期解析成 (kind, 可比较数值)，无法解析返回 None。

    中英文同等支持。时刻：`15:00`、`15:00:30`、`15点30分`、`下午3点`、`3 PM`、`3:30pm`。
    日期：`2026-10-10`、`2026/10/10`、`2026.10.10`、`2026年10月10日`、`Oct 10, 2026`、
    `10 October 2026`，以及 ISO 日期时间。kind ∈ {"time","date","datetime"}。
    纯数字不算时间——`400` 是预算，不是时刻。
    """
    if value is None or isinstance(value, (bool, int, float)): return None
    text = str(value).strip()
    if not text: return None
    lowered = text.lower()
    for qualifier in _TEMPORAL_QUALIFIERS:
        if lowered.startswith(qualifier): text = text[len(qualifier):].strip(); lowered = text.lower()
        elif lowered.endswith(qualifier): text = text[: -len(qualifier)].strip(); lowered = text.lower()
    if not text: return None
    clock = _parse_clock(text)
    if clock: return clock
    day = _parse_date(text)
    if day: return day
    try: moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError: return None
    if moment.hour or moment.minute or moment.second or moment.microsecond:
        return ("datetime", moment.timestamp())
    return ("date", float(moment.date().toordinal()))


def _comparable(parsed: tuple[str, float], target: str) -> float | None:
    """把已解析的时间统一到可比较的标量上（date 与 datetime 混比时按当日零点）。"""
    kind, value = parsed
    if kind == target: return value
    if {kind, target} == {"date", "datetime"}:
        if kind == "date": return datetime.combine(date.fromordinal(int(value)), time.min).timestamp()
        return float(datetime.fromtimestamp(value).date().toordinal())
    return None


def decode_constraint_value(raw: Any) -> Any:
    """Decode a stored constraint operand.

    Values reach the engine either as a plain scalar or as an rdf:JSON literal that
    RDFLib could not decode. Accept JSON first, then the Python literal form
    ("{'key': 'x'}") written by earlier versions, so historical rules stay executable
    instead of silently failing to match. Unparseable text is returned unchanged.
    """
    if isinstance(raw, (dict, list)):
        return raw
    text = str(raw)
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError, TypeError):
            return text

def _constraints_match(constraints: Any, context: dict[str, Any]) -> bool:
    for item in constraints if isinstance(constraints, list) else []:
        if not isinstance(item, dict): return False
        kind, expected = item.get("constraint_type"), item.get("constraint_value")
        if not isinstance(expected, (dict, list)):
            expected = decode_constraint_value(expected)
        if kind == "context_equals":
            key = expected.get("key") if isinstance(expected, dict) else item.get("key")
            value = expected.get("value") if isinstance(expected, dict) else expected
            if not key or context.get(key) != value: return False
        elif kind in {"numeric_lte", "numeric_gte"}:
            if not isinstance(expected, dict) or not expected.get("key") or expected.get("value") is None: return False
            actual = context.get(expected["key"])
            if isinstance(actual, bool): return False
            try: actual_value, limit = float(actual), float(expected["value"])
            except (TypeError, ValueError): return False
            if kind == "numeric_lte" and actual_value > limit: return False
            if kind == "numeric_gte" and actual_value < limit: return False
        elif kind in {"temporal_lte", "temporal_gte"}:
            if not isinstance(expected, dict) or not expected.get("key") or expected.get("value") is None: return False
            limit = parse_temporal(expected["value"])
            actual = parse_temporal(context.get(expected["key"]))
            if limit is None or actual is None: return False
            # 两边类型必须兼容：时刻比时刻、日期比日期；日期与日期时间按当日零点折算。
            kind_of, value_of = limit[0], _comparable(actual, limit[0])
            if value_of is None: return False
            if kind == "temporal_lte" and value_of > limit[1]: return False
            if kind == "temporal_gte" and value_of < limit[1]: return False
        elif kind == "context_exists":
            key = expected.get("key") if isinstance(expected, dict) else None
            if not key or key not in context or context[key] in (None, ""): return False
        elif kind == "source_trust_min":
            rank = {"low": 0, "medium": 1, "high": 2}
            if rank.get(str(context.get("source_trust")), -1) < rank.get(str(expected), 99): return False
        else: return False
    return True
