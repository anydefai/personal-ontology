from __future__ import annotations

from typing import Any
import json
from datetime import date, datetime
from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import XSD

PO = Namespace("urn:personalontology:ontology#")
BASE = "urn:personal-ontology:"

CLASSES = {
    "principals": "Principal", "resource-types": "ResourceTypeDescriptor",
    "params": "ParamDefinition", "actions": "Action", "authorizations": "Authorization",
    "constraints": "Constraint", "redlines": "Redline", "decision-results": "DecisionResult",
    "decisions": "Decision", "taxonomies": "Taxonomy", "taxonomy-items": "TaxonomyItem",
    "contexts": "Context", "interactions": "Interaction", "executions": "Execution",
    "contacts": "ContactPoint", "matchers": "Matcher", "notifiers": "Notifier",
    "crypto-providers": "CryptoProvider", "triggers": "Trigger", "notifications": "Notification",
    "evidence": "Evidence",
    "scenario-slices": "ScenarioSlice",
}

FIELDS: dict[str, dict[str, tuple[str, str]]] = {
    "principals": {"principal_type": ("principalType", "lit"), "display_name_zh": ("displayNameZh", "lit"), "display_name_en": ("displayNameEn", "lit"), "parent_id": ("hasParent", "principals")},
    "resource-types": {"type_name": ("typeName", "lit"), "display_name_zh": ("displayNameZh", "lit"), "display_name_en": ("displayNameEn", "lit"), "matcher_id": ("usesMatcher", "matchers"), "pattern_examples": ("patternExamples", "lit"), "actions": ("supportsAction", "actions"), "params": ("hasParam", "params"), "default_priority": ("defaultPriority", "lit"), "icon": ("icon", "lit"), "description_zh": ("descriptionZh", "lit"), "description_en": ("descriptionEn", "lit"), "is_builtin": ("isBuiltin", "lit")},
    "params": {"param_name": ("paramName", "lit"), "param_type": ("paramType", "lit"), "display_name_zh": ("displayNameZh", "lit"), "display_name_en": ("displayNameEn", "lit"), "required": ("paramRequired", "lit")},
    "actions": {"action_id": ("actionId", "lit"), "display_name_zh": ("displayNameZh", "lit"), "display_name_en": ("displayNameEn", "lit"), "applies_to": ("actionResourceType", "resource-types"), "risk_level": ("riskLevel", "lit"), "description_zh": ("descriptionZh", "lit"), "description_en": ("descriptionEn", "lit")},
    "authorizations": {"grantor_id": ("grantor", "principals"), "grantee_id": ("grantee", "principals"), "resource_type_id": ("appliesToResource", "resource-types"), "resource_pattern": ("resourcePattern", "lit"), "pattern_type": ("patternType", "lit"), "actions": ("allowsAction", "actions"), "effect": ("hasEffect", "effect"), "priority": ("priority", "lit"), "constraints": ("hasConstraint", "constraints"), "redlines": ("hasRedline", "redlines"), "source": ("source", "lit"), "term": ("term", "lit"), "revoked": ("revoked", "lit"), "revoked_at": ("revokedAt", "lit"), "created_at": ("createdAt", "lit"), "policy_status": ("policyStatus", "lit")},
    "constraints": {"constraint_type": ("constraintType", "lit"), "constraint_value": ("constraintValue", "lit")},
    "redlines": {"description_zh": ("descriptionZh", "lit"), "description_en": ("descriptionEn", "lit"), "redline_pattern": ("redlinePattern", "lit")},
    "decision-results": {"display_name_zh": ("displayNameZh", "lit"), "display_name_en": ("displayNameEn", "lit"), "severity": ("severity", "lit"), "next_action": ("nextAction", "lit"), "color": ("color", "lit"), "description_zh": ("descriptionZh", "lit"), "description_en": ("descriptionEn", "lit")},
    "decisions": {"interaction_id": ("interaction", "interactions"), "phase": ("phase", "lit"), "sequence": ("sequence", "lit"), "result_id": ("hasResult", "decision-results"), "reason_key": ("reasonKey", "lit"), "reason_params": ("reasonParams", "json"), "reason_display": ("reasonDisplay", "json"), "input_params": ("inputParams", "json"), "cited_assertions": ("citedAssertions", "lit"), "timestamp": ("timestamp", "lit"), "evidence_ids": ("citesEvidence", "evidence")},
    "taxonomies": {"display_name_zh": ("displayNameZh", "lit"), "display_name_en": ("displayNameEn", "lit"), "items": ("hasTaxonomyItem", "taxonomy-items"), "extensible": ("extensible", "lit"), "description_zh": ("descriptionZh", "lit"), "description_en": ("descriptionEn", "lit")},
    "taxonomy-items": {"display_name_zh": ("displayNameZh", "lit"), "display_name_en": ("displayNameEn", "lit"), "parent_id": ("parentTaxonomyItem", "taxonomy-items"), "extra": ("extra", "json")},
    "contexts": {"timestamp": ("timestamp", "lit"), "location": ("location", "lit"), "device": ("device", "lit"), "user_status_id": ("userStatus", "taxonomy-items"), "task_type_id": ("taskType", "taxonomy-items"), "source_trust": ("sourceTrust", "lit")},
    "interactions": {"parent_interaction_id": ("parentInteraction", "interactions"), "session_id": ("sessionId", "lit"), "user_input": ("userInput", "lit"), "parsed_intent": ("parsedIntent", "json"), "decision_ids": ("hasDecision", "decisions"), "execution_ids": ("hasExecution", "executions"), "status": ("status", "lit"), "started_at": ("startedAt", "lit"), "ended_at": ("endedAt", "lit")},
    "executions": {"interaction_id": ("interaction", "interactions"), "decision_id": ("executedAs", "decisions"), "action": ("action", "lit"), "params": ("params", "json"), "result": ("executionResult", "lit"), "error_message": ("errorMessage", "lit"), "executed_at": ("executedAt", "lit")},
    "contacts": {"contact_type": ("contactType", "lit"), "value": ("value", "lit"), "label": ("label", "lit"), "verified": ("verified", "lit"), "disclosure": ("disclosure", "lit"), "created_at": ("createdAt", "lit")},
    "matchers": {"display_name_zh": ("displayNameZh", "lit"), "display_name_en": ("displayNameEn", "lit"), "description_zh": ("descriptionZh", "lit"), "description_en": ("descriptionEn", "lit")},
    "notifiers": {"display_name_zh": ("displayNameZh", "lit"), "display_name_en": ("displayNameEn", "lit"), "priority": ("priority", "lit"), "enabled": ("enabled", "lit")},
    "crypto-providers": {"display_name_zh": ("displayNameZh", "lit"), "key_size": ("keySize", "lit"), "description": ("descriptionZh", "lit")},
    "triggers": {"event_type": ("eventType", "lit"), "condition": ("condition", "lit"), "action": ("triggerAction", "lit")},
    "notifications": {"channel_id": ("channelId", "lit"), "created_at": ("createdAt", "lit")},
    "evidence": {"evidence_type": ("evidenceType", "lit"), "created_at": ("createdAt", "lit"), "digest": ("digest", "lit")},
    "scenario-slices": {"original_text": ("originalText", "lit"), "status": ("scenarioStatus", "lit"), "analysis": ("analysis", "json"), "updated_at": ("updatedAt", "lit")},
}

ID_FIELDS = {"authorizations": "authorizationId", "decisions": "decisionId", "executions": "executionId", "contacts": "contactId", "triggers": "triggerId", "notifications": "notificationId", "evidence": "evidenceId", "taxonomies": "taxonomyId", "taxonomy-items": "itemId", "resource-types": "typeName", "actions": "actionId", "matchers": "patternType", "notifiers": "channelId", "crypto-providers": "cryptoName", "principals": "principalId", "params": "paramId", "redlines": "redlineId", "decision-results": "resultId", "contexts": "contextId", "interactions": "interactionId", "scenario-slices": "scenarioId"}
INPUT_ID_FIELDS = {"authorizations":"authorization_id", "decisions":"decision_id", "executions":"execution_id", "contacts":"contact_id", "triggers":"trigger_id", "notifications":"notification_id", "evidence":"evidence_id", "taxonomies":"taxonomy_id", "taxonomy-items":"item_id", "resource-types":"type_name", "actions":"action_id", "matchers":"pattern_type", "notifiers":"channel_id", "crypto-providers":"name", "principals":"principal_id", "params":"param_id", "redlines":"redline_id", "decision-results":"result_id", "contexts":"context_id", "interactions":"interaction_id", "constraints":"constraint_id", "scenario-slices":"scenario_id"}

def node_uri(collection: str, item_id: str) -> URIRef:
    return URIRef(f"{BASE}{collection}:{item_id}")

def datatype(value: Any) -> URIRef:
    if isinstance(value, bool): return XSD.boolean
    if isinstance(value, int): return XSD.integer
    if isinstance(value, float): return XSD.decimal
    if isinstance(value, dict) or isinstance(value, list): return RDF.JSON
    # Records read back from the graph expose dateTime fields as datetime objects.
    # Without these branches a rewrite would downgrade them to xsd:string and fail
    # the SHACL datatype constraint.
    if isinstance(value, datetime): return XSD.dateTime
    if isinstance(value, date): return XSD.date
    if isinstance(value, str) and "T" in value and len(value) >= 19: return XSD.dateTime
    return XSD.string

def object_to_graph(graph: Graph, collection: str, item_id: str, record: dict[str, Any]) -> None:
    subject = node_uri(collection, item_id)
    graph.add((subject, RDF.type, PO[CLASSES[collection]]))
    id_field = ID_FIELDS.get(collection)
    if id_field:
        graph.add((subject, PO[id_field], Literal(item_id, datatype=XSD.string)))
    for field, value in record.items():
        mapped = FIELDS.get(collection, {}).get(field)
        if not mapped or value is None:
            continue
        predicate_name, kind = mapped
        predicate = PO[predicate_name]
        values = value if isinstance(value, list) and kind not in {"json", "lit"} else [value]
        for part in values:
            if kind in CLASSES:
                graph.add((subject, predicate, node_uri(kind, str(part))))
            elif kind == "effect":
                graph.add((subject, predicate, PO[{"allow":"Allow", "deny":"Deny", "ask":"Ask"}.get(str(part).lower(), "Deny")]))
            elif kind == "json":
                graph.add((subject, predicate, Literal(json.dumps(part, ensure_ascii=False), datatype=RDF.JSON, normalize=False)))
            elif isinstance(part, (dict, list)):
                # Object values mapped to a literal field (for example constraintValue)
                # must still be serialized as real JSON text: handing a Python object to
                # Literal() stores str()/repr output ("{'key': 'x'}"), which json.loads
                # cannot read back.
                graph.add((subject, predicate, Literal(json.dumps(part, ensure_ascii=False), datatype=RDF.JSON, normalize=False)))
            else:
                graph.add((subject, predicate, Literal(part, datatype=datatype(part))))

# 这些字段在语义上就是多值的：即使图中只出现一次，也必须返回列表。
# 否则单条规则会读出字符串，调用方按字符迭代（曾导致 1 个约束被当成 39 个）。
MULTI_VALUED: dict[str, tuple[str, ...]] = {
    "authorizations": ("actions", "constraints", "redlines"),
    "resource-types": ("actions", "params"),
}


def graph_to_record(graph: Graph, collection: str, item_id: str) -> dict[str, Any]:
    subject = node_uri(collection, item_id)
    record: dict[str, Any] = {"id": item_id}
    id_field = INPUT_ID_FIELDS.get(collection)
    if id_field:
        record[id_field] = item_id
    reverse = {PO[p]: (field, kind) for field, (p, kind) in FIELDS.get(collection, {}).items()}
    for pred, obj in graph.predicate_objects(subject):
        if pred not in reverse: continue
        field, kind = reverse[pred]
        if kind in CLASSES: value = str(obj).rsplit(":", 1)[-1]
        elif kind == "effect": value = {PO.Allow:"allow", PO.Deny:"deny", PO.Ask:"ask"}.get(obj, "deny")
        elif kind == "json":
            try: value = obj.toPython()
            except Exception: value = str(obj)
            # RDFLib can expose rdf:JSON literals as serialized text; the API
            # and UI need the decoded object or array instead.
            if isinstance(value, str):
                try: value = json.loads(value)
                except json.JSONDecodeError: pass
        else:
            try: value = obj.toPython()
            except Exception: value = str(obj)
        if field in record:
            record[field] = [*record[field], value] if isinstance(record[field], list) else [record[field], value]
        else: record[field] = value
    for field in MULTI_VALUED.get(collection, ()):
        if field not in record: record[field] = []
        elif not isinstance(record[field], list): record[field] = [record[field]]
    return record
