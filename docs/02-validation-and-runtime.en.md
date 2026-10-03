# Personal Ontology Governance System v3.0: validation and runtime specification

Version: 3.0
Status: design baseline
Basis: part one of the shared document (design overview, metamodel, ontology field tables)

This document is part two of the design split: SHACL validation, the decision algorithm, the
registry and the storage specification. Its core principles are open-world description, a single
runtime adjudication point, and fail-closed behaviour (when information is insufficient, nothing is
permitted).

## 1. Validation conventions

- RDF data is serialised as Turtle; instance URIs are stable identifiers, and field names map to
  `po:` properties in the metamodel.
- SHACL validation runs against the complete data graph. Referenced objects should use IRIs rather
  than free text standing in for relations.
- The shapes below turn the required entries of the field tables into `sh:minCount 1`; enumerated
  values are constrained with `sh:in`.
- `sh:closed false`: applications may add extension properties, and unknown predicates do not make
  data invalid. Security-sensitive core decision fields remain strictly constrained by the shapes.
- JSON object fields (such as `reason_params`, `input_params`, `extra`) are stored in RDF as
  `rdf:JSON` literals; an implementation may also use a dedicated property-graph encoding, but API
  round-trips must stay consistent.
- Custom type descriptors may be added, but must not masquerade as built-in types; `isBuiltin true`
  may only come from the code's built-in registry.

Namespaces:

```turtle
@prefix po:   <urn:personalontology:ontology#> .
@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
```

## 2. SHACL shapes (19)

Save this section as `ontology/shapes.ttl`. All shapes are node shapes; the integrity of
cross-node references (for example whether a grantee exists) is validated with `sh:class`.

```turtle
@prefix po:   <urn:personalontology:ontology#> .
@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

po:PrincipalShape a sh:NodeShape ; sh:targetClass po:Principal ;
  sh:property [ sh:path po:principalId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:principalType ; sh:minCount 1 ; sh:maxCount 1 ; sh:in ("person"^^xsd:string "agent"^^xsd:string "group"^^xsd:string "role"^^xsd:string "org"^^xsd:string) ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:hasParent ; sh:maxCount 1 ; sh:class po:Principal ] .

po:ResourceTypeDescriptorShape a sh:NodeShape ; sh:targetClass po:ResourceTypeDescriptor ;
  sh:property [ sh:path po:typeName ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:displayNameEn ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:usesMatcher ; sh:minCount 1 ; sh:maxCount 1 ; sh:class po:Matcher ] ;
  sh:property [ sh:path po:supportsAction ; sh:class po:Action ] ;
  sh:property [ sh:path po:hasParam ; sh:class po:ParamDefinition ] ;
  sh:property [ sh:path po:defaultPriority ; sh:minCount 1 ; sh:datatype xsd:integer ] ;
  sh:property [ sh:path po:isBuiltin ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:boolean ] .

po:ParamDefinitionShape a sh:NodeShape ; sh:targetClass po:ParamDefinition ;
  sh:property [ sh:path po:paramName ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:paramType ; sh:minCount 1 ; sh:in ("string"^^xsd:string "number"^^xsd:string "bool"^^xsd:string "date"^^xsd:string) ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ] ;
  sh:property [ sh:path po:displayNameEn ; sh:minCount 1 ] ;
  sh:property [ sh:path po:paramRequired ; sh:minCount 1 ; sh:datatype xsd:boolean ] .

po:ActionShape a sh:NodeShape ; sh:targetClass po:Action ;
  sh:property [ sh:path po:actionId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ] ;
  sh:property [ sh:path po:displayNameEn ; sh:minCount 1 ] ;
  sh:property [ sh:path po:actionResourceType ; sh:minCount 1 ; sh:class po:ResourceTypeDescriptor ] ;
  sh:property [ sh:path po:riskLevel ; sh:minCount 1 ; sh:in ("low"^^xsd:string "medium"^^xsd:string "high"^^xsd:string "critical"^^xsd:string) ] .

po:AuthorizationShape a sh:NodeShape ; sh:targetClass po:Authorization ;
  sh:property [ sh:path po:authorizationId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:grantor ; sh:minCount 1 ; sh:maxCount 1 ; sh:class po:Principal ] ;
  sh:property [ sh:path po:grantee ; sh:minCount 1 ; sh:maxCount 1 ; sh:class po:Principal ] ;
  sh:property [ sh:path po:appliesToResource ; sh:minCount 1 ; sh:maxCount 1 ; sh:class po:ResourceTypeDescriptor ] ;
  sh:property [ sh:path po:resourcePattern ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:patternType ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:allowsAction ; sh:minCount 1 ; sh:class po:Action ] ;
  sh:property [ sh:path po:hasEffect ; sh:minCount 1 ; sh:maxCount 1 ; sh:in (po:Allow po:Deny po:Ask) ] ;
  sh:property [ sh:path po:priority ; sh:minCount 1 ; sh:datatype xsd:integer ] ;
  sh:property [ sh:path po:source ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:term ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:revoked ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:boolean ] ;
  sh:property [ sh:path po:createdAt ; sh:minCount 1 ; sh:datatype xsd:dateTime ] ;
  sh:property [ sh:path po:hasConstraint ; sh:class po:Constraint ] ;
  sh:property [ sh:path po:hasRedline ; sh:class po:Redline ] .

po:ConstraintShape a sh:NodeShape ; sh:targetClass po:Constraint ;
  sh:property [ sh:path po:constraintType ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:constraintValue ; sh:minCount 1 ] .

po:RedlineShape a sh:NodeShape ; sh:targetClass po:Redline ;
  sh:property [ sh:path po:redlineId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:descriptionZh ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:descriptionEn ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:redlinePattern ; sh:minCount 1 ; sh:datatype xsd:string ] .

po:DecisionResultShape a sh:NodeShape ; sh:targetClass po:DecisionResult ;
  sh:property [ sh:path po:resultId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ] ;
  sh:property [ sh:path po:displayNameEn ; sh:minCount 1 ] ;
  sh:property [ sh:path po:severity ; sh:minCount 1 ; sh:minInclusive 0 ; sh:maxInclusive 10 ; sh:datatype xsd:integer ] ;
  sh:property [ sh:path po:nextAction ; sh:minCount 1 ; sh:in ("execute"^^xsd:string "pause"^^xsd:string "refuse"^^xsd:string) ] .

po:DecisionShape a sh:NodeShape ; sh:targetClass po:Decision ;
  sh:property [ sh:path po:decisionId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:phase ; sh:minCount 1 ; sh:in ("pre_planning"^^xsd:string "pre_execution"^^xsd:string) ] ;
  sh:property [ sh:path po:hasResult ; sh:minCount 1 ; sh:maxCount 1 ; sh:class po:DecisionResult ] ;
  sh:property [ sh:path po:reasonKey ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:inputParams ; sh:minCount 1 ; sh:datatype rdf:JSON ] ;
  sh:property [ sh:path po:timestamp ; sh:minCount 1 ; sh:datatype xsd:dateTime ] ;
  sh:property [ sh:path po:citesEvidence ; sh:class po:Evidence ] .

po:TaxonomyShape a sh:NodeShape ; sh:targetClass po:Taxonomy ;
  sh:property [ sh:path po:taxonomyId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ] ;
  sh:property [ sh:path po:displayNameEn ; sh:minCount 1 ] ;
  sh:property [ sh:path po:hasTaxonomyItem ; sh:minCount 1 ; sh:class po:TaxonomyItem ] ;
  sh:property [ sh:path po:extensible ; sh:datatype xsd:boolean ; sh:maxCount 1 ] .

po:TaxonomyItemShape a sh:NodeShape ; sh:targetClass po:TaxonomyItem ;
  sh:property [ sh:path po:itemId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ] ;
  sh:property [ sh:path po:displayNameEn ; sh:minCount 1 ] ;
  sh:property [ sh:path po:parentTaxonomyItem ; sh:maxCount 1 ; sh:class po:TaxonomyItem ] .

po:ContextShape a sh:NodeShape ; sh:targetClass po:Context ;
  sh:property [ sh:path po:contextId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:timestamp ; sh:minCount 1 ; sh:datatype xsd:dateTime ] ;
  sh:property [ sh:path po:userStatus ; sh:minCount 1 ; sh:class po:TaxonomyItem ] ;
  sh:property [ sh:path po:taskType ; sh:class po:TaxonomyItem ] ;
  sh:property [ sh:path po:sourceTrust ; sh:minCount 1 ; sh:in ("high"^^xsd:string "medium"^^xsd:string "low"^^xsd:string) ] .

po:InteractionShape a sh:NodeShape ; sh:targetClass po:Interaction ;
  sh:property [ sh:path po:interactionId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:sessionId ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:userInput ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:status ; sh:minCount 1 ; sh:in ("in_progress"^^xsd:string "completed"^^xsd:string "interrupted"^^xsd:string) ] ;
  sh:property [ sh:path po:startedAt ; sh:minCount 1 ; sh:datatype xsd:dateTime ] ;
  sh:property [ sh:path po:endedAt ; sh:maxCount 1 ; sh:datatype xsd:dateTime ] .

po:ExecutionShape a sh:NodeShape ; sh:targetClass po:Execution ;
  sh:property [ sh:path po:executionId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:interaction ; sh:minCount 1 ; sh:class po:Interaction ] ;
  sh:property [ sh:path po:executedAs ; sh:minCount 1 ; sh:class po:Decision ] ;
  sh:property [ sh:path po:action ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:executionResult ; sh:minCount 1 ; sh:in ("success"^^xsd:string "failure"^^xsd:string "exception"^^xsd:string) ] ;
  sh:property [ sh:path po:executedAt ; sh:minCount 1 ; sh:datatype xsd:dateTime ] .

po:ContactPointShape a sh:NodeShape ; sh:targetClass po:ContactPoint ;
  sh:property [ sh:path po:contactId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:contactType ; sh:minCount 1 ; sh:in ("phone"^^xsd:string "email"^^xsd:string "address"^^xsd:string) ] ;
  sh:property [ sh:path po:value ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:label ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:verified ; sh:minCount 1 ; sh:datatype xsd:boolean ] ;
  sh:property [ sh:path po:disclosure ; sh:minCount 1 ; sh:in ("self_only"^^xsd:string "internal"^^xsd:string "external"^^xsd:string) ] ;
  sh:property [ sh:path po:createdAt ; sh:minCount 1 ; sh:datatype xsd:dateTime ] .

po:MatcherShape a sh:NodeShape ; sh:targetClass po:Matcher ;
  sh:property [ sh:path po:patternType ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ] ;
  sh:property [ sh:path po:displayNameEn ; sh:minCount 1 ] .

po:NotifierShape a sh:NodeShape ; sh:targetClass po:Notifier ;
  sh:property [ sh:path po:channelId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ] ;
  sh:property [ sh:path po:displayNameEn ; sh:minCount 1 ] ;
  sh:property [ sh:path po:enabled ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:boolean ] .

po:CryptoProviderShape a sh:NodeShape ; sh:targetClass po:CryptoProvider ;
  sh:property [ sh:path po:cryptoName ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:displayNameZh ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:keySize ; sh:minCount 1 ; sh:minInclusive 16 ; sh:datatype xsd:integer ] .

po:TriggerShape a sh:NodeShape ; sh:targetClass po:Trigger ;
  sh:property [ sh:path po:triggerId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:eventType ; sh:minCount 1 ; sh:in ("time_expired"^^xsd:string "person_left"^^xsd:string "context_changed"^^xsd:string "risk_event"^^xsd:string) ] ;
  sh:property [ sh:path po:condition ; sh:minCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path po:triggerAction ; sh:minCount 1 ; sh:in ("revoke"^^xsd:string "escalate"^^xsd:string "notify"^^xsd:string) ] .

```

### 2.1 Field-name alignment

The metamodel's supplementary property declarations live in `ontology/personal-properties.ttl`.
Mapping uses lowerCamelCase, for example `reason_key` → `po:reasonKey` and `execution_result` →
`po:executionResult`. To avoid mistaking OWL's multi-valued `rdfs:domain` for "any one of these",
resource types support actions through `po:supportsAction`, actions target resource types through
`po:actionResourceType`, principal hierarchy uses `po:hasParent`, and taxonomy hierarchy uses
`po:parentTaxonomyItem`. In `Authorization`, `effect` points at `po:Allow` / `po:Deny` / `po:Ask`
through `po:hasEffect`. If the API uses strings, conversion happens only at the serialisation
boundary.

## 3. The decision algorithm

### 3.1 Request structure

```json
{
  "request_id": "uuid",
  "principal_id": "principal:alice",
  "action_id": "file.read",
  "resource": {"type": "file", "id": "/docs/plan.md"},
  "context": {"timestamp": "RFC3339", "source_trust": "high"},
  "phase": "pre_execution"
}
```

When a required field is missing, a type does not match, or the identity or resource cannot be
resolved, the result is `pause` (more information needed) — never a default allow.

### 3.2 Decision order

Each request runs the following deterministic flow, and every step writes decision evidence:

1. **Normalise the input**: validate fields and time formats; resolve the principal's verification
   status, the resource type and the action id.
2. **Load a consistent snapshot**: read authorisations, principal inheritance, redlines, the
   registry and the context from one revision; record `policy_revision`.
3. **Apply redlines**: if any enabled redline matches the principal, action, resource or context,
   deny immediately. Redlines precede ordinary allow/ask/deny authorisations.
4. **Build the candidate authorisation set**: include the principal's own rules and those inherited
   through parent groups, roles and organisations; detect cycles, stop inheriting and record the
   configuration error.
5. **Filter candidates**: the authorisation is not revoked and not expired, the principal and action
   match, the resource type is the same, the registered matcher matches, and time and other
   constraints hold. A constraint that cannot be executed counts as unsatisfied.
6. **Merge effects**: if a matching deny is among the candidates, deny wins; otherwise if any ask is
   present, pause; otherwise at least one matching allow is needed to allow; with no matching rule,
   deny (default deny). Equal priority does not change the deny > ask > allow order. Priority is
   only used for explanation and to pick the primary cited rule, and must never override a deny or a
   redline.
7. **Risk gate**: a `critical` action needs an explicit allow and no unknown or low-trust critical
   context; for a `high` action an unknown constraint returns pause. Risk must never be downgraded
   because a registry entry is missing.
8. **Emit the decision**: map to a registered `DecisionResult`, including the result, `next_action`,
   reason key and parameters, the matched authorisations and evidence, a summary of the input
   snapshot, the policy revision and the timestamp.
9. **Re-check before execution**: before actually executing, decide again with `pre_execution`
   against the latest snapshot. If the principal, resource, action, policy revision or relevant
   context changed, the earlier allow is void.
10. **Record execution**: call the action executor only on an explicit allow; record success,
    failure or exception. The decision itself performs no resource operations.

### 3.3 Output contract

```json
{
  "decision_id": "decision:uuid",
  "result_id": "allow|deny|ask",
  "next_action": "execute|refuse|pause",
  "reason_key": "decision.explicit_allow",
  "reason_params": {},
  "phase": "pre_execution",
  "policy_revision": "sha256:…",
  "cited_assertions": ["authorization:…"],
  "timestamp": "RFC3339"
}
```

The API's `result_id` follows registered result ids; the three names above are the default built-in
results. Display text is produced from `reason_key` plus the language pack, and the audit record
also stores the text displayed at the time, so later translation changes cannot alter history.

## 4. Registry specification

The registry has eight categories: Resource, Action, Constraint, DecisionResult, Matcher, Taxonomy,
Notifier and CryptoProvider. Built-in entries are loaded at application start and are read-only;
extensions are stored in the ontology graph and pass SHACL validation.

### 4.1 Common registry entries

Every entry needs a stable `id`, `version`, Chinese and English names, a description, an enabled
state, a source, and creation/update times. Ids are unique within their category. Before enabling,
dependency references and capability declarations must be validated; retirement uses a disabled or
deprecated state, and existing audit records stay readable.

### 4.2 Registry interface contract

- `list(category, include_disabled=false)`: returns entries stably ordered by id.
- `get(category, id, version?)`: reads a specified version immutably.
- `validate(category, definition)`: SHACL plus type-specific checks, returning a machine-readable
  list of problems.
- `register(category, definition, expected_revision)`: optimistic concurrent write; a revision
  conflict returns 409.
- `deprecate(category, id, expected_revision)`: stops new references without breaking historical
  ones.
- `resolve(category, id)`: returns only enabled, compatible versions; not finding one must be an
  explicit error.

### 4.3 Requirements per category

- **Resource**: type name, matcher, parameter definitions, available actions, priority. A custom
  resource type must not declare arbitrary code entry points.
- **Action**: risk level and applicable resource type are mandatory; executor code is managed
  separately from action metadata.
- **Constraint**: register executable, purely functional constraints; declare the input schema,
  determinism and a timeout ceiling. A timeout or exception counts as unsatisfied.
- **DecisionResult**: declares a 0–10 severity and `execute/pause/refuse`; a built-in allow-class
  result must not be redefined to bypass high risk.
- **Matcher**: only reviewed matcher implementations; regular expressions must bound pattern
  length, input length and runtime, and catastrophic backtracking is forbidden. A matcher error is
  not a successful match.
- **Taxonomy**: defines an id, its items and whether it is extensible; deletions use deprecation and
  ids are never reused.
- **Notifier**: declares channels and capabilities; secrets are held by the secret store and the
  configuration graph stores only secret references.
- **CryptoProvider**: declares only algorithm and key metadata; key material never enters RDF, the
  ontology files or ordinary configuration logs.

## 5. Data storage specification

### 5.1 Data partitions

1. **Schema graph**: metamodel, SHACL shapes and built-in vocabulary versions; shipped with the
   application, read-only.
2. **Ontology graph**: custom resource types, taxonomies and user-extended rule definitions; version
   revisions supported.
3. **Business graph**: instance data — principals, authorisations, contexts, interactions,
   decisions, executions, evidence.
4. **Secret store**: encryption keys, notifier credentials and sensitive integration configuration;
   never stored mixed with the RDF graphs.

### 5.2 Transactions and revisions

- Authorisation changes, revocations and registry edits must be committed in one transaction and
  increment a monotonic `revision`.
- A decision reads a transactionally consistent snapshot; the decision record stores the `revision`
  actually used.
- Runtime caches are keyed by revision and publish an invalidation event after commit. When a cache's
  version cannot be confirmed, bypass the cache and read authoritative storage.
- Changes use append-only audit events while current state may be materialised; a revision event
  contains the actor, time, change summary and before/after hashes.
- Concurrent writes use `expected_revision`; conflicts are never overwritten automatically.

### 5.3 Privacy, retention and backup

- `ContactPoint.value` is encrypted at the application layer before storage; ordinary logs may
  record only irreversible redactions or a stable HMAC, never plaintext.
- User input, context and execution errors may contain sensitive content; the storage interface
  supports per-field encryption, retention periods and deletion/anonymisation policies.
- Audit evidence should keep the minimum necessary information; when the original text cannot be
  kept, store a digest, source, timestamp, integrity hash and the reason for deletion.
- Backups are encrypted with the key held separately from the backup; a backup includes graph data,
  revisions, SHACL/metamodel versions and migration metadata.
- After a restore, verify integrity first, then run SHACL and referential-integrity checks; if they
  fail, start read-only and refuse to let authorisation decisions pass.

### 5.4 Migration and compatibility

- Every schema/ontology migration has a unique version, a predecessor version, a repeatable flag and
  verification steps.
- Migrations run as "back up → verify the backup → migrate a temporary copy → SHACL validate →
  atomic switch".
- When no downgrade migration exists, restore the pre-migration backup; never experiment
  irreversibly on the original data.
- Unrecognised extension predicates are preserved; a critical authorisation field that cannot be
  interpreted invalidates that rule and produces a diagnostic — it is never treated as allow.

## 6. Consistency and error handling

| Situation | Handling |
|---|---|
| SHACL validation fails | Reject the write; return shape, focus node, path, severity and message |
| A referenced object is missing | Reject the write; when reading old data, mark the related rules invalid |
| A matcher/constraint is unregistered or fails | That candidate rule does not match; a high-risk request pauses or denies, never allows |
| A registry version conflict | Return the conflict and the current revision; the caller re-reads and resubmits |
| Storage is unavailable or the snapshot is inconsistent | Decisions are unavailable; the executor is not called |
| The decision result type is missing | Use the built-in deny/pause safety result and raise a configuration warning |

## 7. Implementation boundaries

This document gives the baseline for data validation and runtime design. The merged metamodel must
load `ontology/personal-properties.ttl` so that the properties referenced by the shapes have
explicit RDF property types and applicability. SHACL covers structure and local constraints;
authorisation merging, inheritance cycle detection, redline matching and pre-execution re-checks are
implemented by the decision engine and cannot be replaced by OWL reasoning or SHACL alone.
