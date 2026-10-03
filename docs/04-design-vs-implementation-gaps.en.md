# Gap list: `docs/03` scenario-slice design vs the current implementation

> **Historical snapshot (please read)** — this document is a gap check as of a particular moment, and
> its status markers no longer describe the present. In particular, every item concerning the
> "resource type / action / authorization rule catalogue pages" is **void** (those three pages were
> removed; see the status correction at the top of `docs/03`). The four contract gaps found in the
> 2026-10-02 iteration (policies missing the action dimension, unconditional deny, cross-domain
> expansion, lost multiple resource types) are **all fixed**, and the current contract and tolerance
> rules are defined by `docs/09-scenario-analysis-schema.md`. This document is kept only to trace the
> reasoning of the time.

# Gap list: `docs/03` scenario-slice design vs the current implementation

What was checked and against which baseline:

| Item | Content |
|---|---|
| Design baseline | `docs/03-scenario-slices-design.md` (709 lines; self-described as "design draft, not yet implemented", with only §26 marked implemented) |
| Implementation baseline | workspace `backend/` (7 modules), `web/` (3 files), `ontology/` (2 files), not under version control |
| Method | extract testable requirements section by section → static code inspection + read-only probing of the running local services and the actual RDF graph |
| Currency of the design baseline | `docs/03` §7 claims "keep the resource type / action / authorization rule pages", **a claim the latest (v3.1) design cancels**: neither `README.md` nor `web/index.html` has those three menu entries. UI requirements follow the actual v3.1 design, and the obsolete part of §7 is listed separately in §5.1 |
| Verdict legend | ✅ aligned ／ ⚠️ partially implemented or different in form ／ ❌ not implemented (including 2 measured defects) |

**Conclusion**: 46 testable requirements were checked — ❌ 32, ⚠️ 14; a further 11 are aligned (see §6)
and 1 was judged obsolete documentation rather than an implementation gap (see §5.1). The full generic
metamodel of `docs/03` (ScenarioDefinition / SlotValue / Clarification / WorkflowStep + a canonical
constraint executor + migration) is **essentially not implemented**; what actually exists is the
vertical slice from §26 ("scenario slices + preference variants"), plus `policyStatus`, scenario
rehearsal and MCP feedback.

---

## 1. P0: blocking (correctness and security)

| # | Problem | Current state and evidence | Verdict |
|---|---|---|---|
| **A1** | **Scenario-generated constraints are serialised incorrectly in RDF, so the rules never match** | `api.py:308`, `447-450` write `constraint_value` as a dict; `model.py:83` takes the `lit` branch (not the `json` branch), so `Literal(dict, datatype=RDF.JSON)` lands as Python repr with single quotes. Measured on the local graph: `ns1:constraintValue "{'key': 'check_in_date'}"^^rdf:JSON`, and `toPython()` returns a `Literal` rather than a dict; `json.loads` at `store.py:292` necessarily fails on single quotes → `_constraints_match` returns `False`. Measured comparison: the in-graph string form gives `matches=False`, the same content as a dict gives `matches=True`. **Consequence: even if these 4 draft authorizations were switched to active by hand, their conditions could never hold and decisions would always fall through to `default_deny`.** | ❌ |
| **A2** | **Saving a scenario-instance edit always 500s (`NameError`)** | `api.py:416` references `suffix` before `api.py:417` assigns it (the generator is evaluated immediately inside `list(...)`). Measured with a stub store, without touching real data: `NameError: cannot access free variable 'suffix'`. Whenever a confirmed scenario's resource has parameters (true for both local scenarios), `PATCH /v1/scenario-slices/{id}/instance` and the `/feedback` endpoint that depends on it (`instance_preference` mode) both fail. | ❌ |
| **A3** | **No graph-level transaction: confirmation and deletion are step-by-step writes** | `confirm` calls `store.put` separately for the resource, action, params, constraints and authorizations (`api.py:241-315`), and each put independently does "copy the whole graph → validate → persist"; a failure midway does not roll back what was already written. `delete_scenario_instance` deletes one by one and swallows `StoreError` (`api.py:325-344`). §24.1/§24.2/§25 explicitly require "batch writes validated and persisted in a single graph transaction; a failure leaves no partial principal/resource/action/rule". | ❌ |
| **A4** | **No separate "activate authorization" confirmation point; the generic PATCH bypasses the guard, and the UI has nowhere to activate** | The design's three confirmation points (confirm params / save draft / enable rules, §8 and §14 item 5) lack the third: there is no `/{id}/activate`; enabling means editing the `policy_status` field, while the generic `PATCH /v1/authorizations/{id}` (`api.py:677-691`) validates nothing, writes no audit and does not check scenario state. §24.2 requires that "PATCH cannot bypass the scenario-state guard or the policy-enable guard". **Consequence: the only control that can change `policy_status` lives in the authorization-rule form whose navigation entry was removed (see 5.1); the slice page only shows a "draft only, not yet in effect" badge and the instance editor has no enable control → today's interface cannot enable any scenario-generated rule at all.** | ❌ |
| **A5** | **Preferences are compiled into hard constraints, conflicting with "a preference must not become a hard limit"** | `api.py:388-398` turns `instance_preferences` into conditions unconditionally, and `444-451` writes them as Constraints; on the decision side `_constraints_match` treats every constraint as "not satisfied means no match", and `strength` is used only in the analysis JSON and the rehearsal (`api.py:623`). §3.3/§8 require a preference to be used only for ordering or hints. | ❌ |

---

## 2. P1: missing generic metamodel (§3, §10, §15, §19)

| # | Design requirement | Current state and evidence | Verdict |
|---|---|---|---|
| **B1** | The `ScenarioDefinition` class and collection land together | No such class in `CLASSES` (`model.py:11-21` is still "21 classes + scenario-slices", matching the §2 inventory); no `scenario-definitions` collection. Scenario-definition capability is compressed into the `analysis` JSON of a single slice record. | ❌ |
| **B2** | The `ScenarioSlice` property set | Only `scenarioId/originalText/scenarioStatus/analysis/updatedAt` (`model.py:45`); missing `usesScenarioDefinition`, `ownerPrincipal`, `normalizedGoal`, `hasSlotValue`, `hasClarification`, `hasInteraction`, `hasAuthorization`, `revision`, `createdAt`. `revision` exists only as `analysis.instance_revision`. | ⚠️ |
| **B3** | The `SlotValue` class and its six-state machine | No class, no collection; values live directly as ordinary JSON arrays in `analysis.segmentation.global_preferences` / `variants[].preferences`. All of §10.3's `state/provenance/confidence/source_text/confirmed_by` are missing. | ❌ |
| **B4** | The `Clarification` class | No class, no collection. Follow-ups are the model's `questions` array (`scenario_llm.py:157`) and answers are fed back through `analyze`'s `answers` parameter (`api.py:149-159`); nothing is persisted and there is no `requirement_level` / `status` / answer-slot linkage. | ❌ |
| **B5** | The `WorkflowStep` class and `confirmation_policy` | Entirely absent. Process semantics such as "ask me before paying" or "show the terms before submitting a booking" have no representation. | ❌ |
| **B6** | Extended `ParamDefinition` attributes | Only `param_name/param_type/required/display_name_*` (`model.py:26`); missing `scope`, `applies_to_ids`, `value_schema`, `unit`, `collection_policy`, `sensitivity`, `examples`, `validation_schema`, `display_order` (§10.3, §19, §23). | ❌ |
| **B7** | `Action.hasInputParam` / `hasOutputParam` | Not implemented; actions and field definitions still do not distinguish input from output. | ❌ |
| **B8** | Extended `Constraint` attributes | Still `constraintType` / `constraintValue` (`model.py:29`); missing `constraintPath`, `constraintOperator`, `typedValue`, `constraintUnit`, `constraintMode`, `constraintSource` (§10.4, §19). | ❌ |
| **B10** | Backfill `policyStatus=active` for legacy Authorizations | No data backfill was done; instead a code default covers it, `rule.get("policy_status", "active")` (`store.py:239`), which does not match §17's "backfill a compatible value" or §25's "explicitly handle legacy data without state per the migration rules" (the semantics happen to be safe, but it is not auditable). | ⚠️ |
| **B11** | The scenario state machine and its legal transitions | The `ScenarioSliceShape` enum has only `draft/analyzed/confirmed` (`shapes.ttl:149`), missing `clarifying/ready/active/completed/abandoned`; §23.1's transition guards (ready requires all required information, a revision falls back to clarifying and re-runs validation) are not implemented. | ❌ |
| **B12** | The ScenarioSlice ↔ Interaction relation | `analyze` never writes an Interaction (no `put("interactions", ...)` anywhere in the repository); §6's data-flow step 1 ("create an Interaction and keep the original text") and §24.2's "analyze writes the original Interaction" are not implemented. | ❌ |
| **B13** | Revision increments and idempotence/concurrency control | `confirm` and `/instance` do not increment revision; there is no idempotency key; `store.put` has no `expected_revision`, so a concurrent overwrite does not return 409 (§11.2, §24.3). | ⚠️ |

---

## 3. P1: constraints and typed values (§3.3, §18, §20, §21)

| # | Design requirement | Current state and evidence | Verdict |
|---|---|---|---|
| **C1** | Operator allowlist `eq/neq/lt/lte/gt/gte/in/contains/between/before/after/exists` | Only `context_equals`, `numeric_lte`, `numeric_gte`, `context_exists` and `source_trust_min` are implemented (`store.py:298-316`); 8 are missing. §18 item 4 requires "confirm each allowlisted operator is implemented; an unimplemented type must leave the rule unenablable". | ❌ |
| **C2** | Migration mapping for legacy constraints (`context_equals`→path+`eq`, `source_trust_min`→`rank_gte` with a fixed rank table) | Not implemented; `source_trust_min` still exists directly as a runtime type (`store.py:313-315`). | ❌ |
| **C3** | Typed values: an amount carries `{amount, currency, basis}`; dates and durations are separated | Values are bare scalars only (`facts`/`conditions` in `scenario_llm.py` have just `value`), with no currency or pricing basis; §20.1's blocking follow-up ("per night or for the whole stay") does not exist. | ❌ |
| **C4** | A single source of truth between `Constraint` RDF and a canonical expression | Partially improved: the decision side does read the node back from the URI before decoding (`store.py:244-247`), so **the "reads an embedded dict" problem §17.1 describes no longer applies to the current code**; but the decoded result is still the old `constraint_type/constraint_value` structure, with no `constraints.py` and no versioned canonical JSON Schema. | ⚠️ |
| **C7** | Block release on incompatible units or mismatched types | There is no notion of units, hence no unit validation; a type mismatch degrades to "no match" (safe, but silent, and it produces none of the review reports §16/§25 require). | ❌ |

---

## 4. P1: API contract and flows (§4, §6, §11, §24)

| # | Design requirement | Current state and evidence | Verdict |
|---|---|---|---|
| **D1** | `analyze` request = `user_input / scenario_slice_id / principal_id / answers / locale` | Actually `text / scenario_id / answers / title_override` (`api.py:138-159`); no `principal_id`, no `locale`. | ⚠️ |
| **D2** | Layered response `recognized / inferred / suggestions / clarifications / validation / next_state` | Returns only `{"scenario": {...}}`, with everything packed into the `analysis` JSON (`api.py:170`). | ❌ |
| **D3** | `POST /{id}/answers` | No such endpoint; the function is replaced by "call `/analyze` again with `answers`" (`api.py:149-159`). §24.2 designs creating a draft and answering follow-ups as distinguishable operations. | ⚠️ |
| **D4** | `POST /{id}/validate` (structural / semantic / executability / conflict report) | No separate validation endpoint. | ❌ |
| **D5** | `POST /{id}/confirm` | The actual path is `POST /v1/scenario-slices/confirm` with the id in the body (`api.py:176-178`). The function exists; the path differs from the contract. | ⚠️ |
| **D7** | `POST /{id}/execute` | Not implemented (§24.2 allows it in a later version). | ❌ |
| **D10** | Two separate sources for completeness checking (model-required vs model-suggested) | `questions` carries `importance/suggested_answers` and `facts` carries `source` (`scenario_llm.py:157`), but neither the API nor the interface groups them: the draft preview does not distinguish "user's words / model recognition / system suggestion / validation problem". | ⚠️ |
| **D11** | A suggestion must be in `suggested` state and only becomes a constraint once adopted | There is no state machine; `answers` are only free text fed back to the model, and a suggestion may be written straight into a preference in the next round. | ❌ |
| **D12** | Follow-ups in rounds, with the number of questions per round controlled | Not implemented: whenever `previous` exists, `questions` is cleared (`scenario_llm.py:191-193`), i.e. "one supplement and it is over". | ❌ |
| **D13** | Blocking items cannot be skipped | No `blocking/recommended/optional` concept; the rehearsal only reports a missing `required` as `incomplete` (`api.py:562`, `624-625`). | ❌ |
| **D14** | Record `owner_principal_id` (do not invent an identity before it is resolved) | The owner is not recorded at all; `confirm` only takes `grantor_id/grantee_id` (`api.py:234-236`), so principal selection happens at confirmation rather than analysis. | ❌ |

---

## 5. P2: validation, migration, code structure and frontend

| # | Design requirement | Current state and evidence | Verdict |
|---|---|---|---|
| **E1** | Add 4 shapes (ScenarioDefinition / SlotValue / Clarification / WorkflowStep) | `shapes.ttl` has none of those 4 target classes (only 20 shapes, including one `ScenarioSliceShape`). | ❌ |
| **E2** | `ScenarioSliceShape` constrained per §16 | Only 5 property constraints (`shapes.ttl:147-151`); the status enum does not match §23.1, and the cross-object rule that `confirmed` must not contain unresolved blocking questions does not exist. | ⚠️ |
| **E3** | Extend `ParamDefinitionShape` / `ConstraintShape` | Neither is extended (`shapes.ttl` still has the old fields); neither `valueSchema`/`scope`/`collectionPolicy` being required nor "the operator must be a registered allowlist entry" is expressed. | ❌ |
| **E4** | `policyStatus` required in `AuthorizationShape` | It has `sh:in (draft/active/suspended)` but as an optional `maxCount 1` (`shapes.ttl:49`), relying on a code default; §16 requires new rules to have it. | ⚠️ |
| **E5** | Transaction-level semantic validation (blocking answered before ready / an answer must have a linked answer slot) | There is no object to carry such validation. | ❌ |
| **E6** | Migration script, backfill and inventory report (§17, §21, §22) | No `migration.py`, and no inventory/backfill/report script of any kind; none of §22's six phases is implemented. | ❌ |
| **E7** | Split out `backend/scenarios/` (dto/service/analyzer/completeness/catalog/validator/compiler/constraints/migration) | Not split; analysis orchestration and RDF compilation all live in `api.py` (729 lines) plus `scenario_llm.py`, and none of the 8 modules §24.1 names exists. | ❌ |
| **E8** | `LLMProvider` as a protocol/interface, vendor-independent | Partially satisfied: there is a `configured()` guard and a clear error rather than a fabricated result when unconfigured (`api.py:173-174`, `scenario_llm.py:153-154`); but there is no Protocol/interface and it is bound to the OpenAI-compatible JSON shape. | ⚠️ |
| **E9** | Split out `web/modules/` (including `dynamic-form.js`) | `web/` has only `app.js`/`app.css`/`index.html`, no `modules/`. Note: `catalog-forms.js` was cancelled along with the catalogue pages and no longer applies; part of `dynamic-form.js` still applies to the scenario-instance editor. | ❌ |
| **E10** | Metadata-driven dynamic forms (amounts / date ranges / repeated items / unknown schema read-only) | `app.js` has fixed `COLLECTIONS` field configuration driving generic forms (for example the authorization form at `app.js:14`), but it does not render from `ParamDefinition/valueSchema` and supports neither amounts (value + currency + basis), nor date ranges, nor repeated items. Note: field types are only `string/number/bool/date` (`api.py:369-370`), and that requirement is now carried only by the scenario-instance editor. | ⚠️ |
| **E12** | Grouped display by source; suggestions offered as "adopt / modify / skip / not applicable"; different buttons and a secondary explanation for confirming a draft versus enabling rules | None implemented; `policy_status` is currently just a dropdown in the authorization-rule form (whose navigation entry is gone, see 5.1). | ❌ |
| **E13** | Page state driven by the server's `status` + revision, resumable after a refresh | The scenario draft itself is persisted (a refresh retrieves it), but the dialogue state machine lives only in browser memory, with no status-driven recovery. | ⚠️ |
| **E14** | Privacy policy visible: what is sent to a remote model, redaction, retention of original text (§13.3, §18.3) | There is a sending notice and the statement that "principal and authorization data are not sent with the request" (README), but no redaction switch and no retention-period setting. | ⚠️ |

### 5.1 Obsolete documentation items (not counted as implementation gaps)

| # | Original design requirement | Finding |
|---|---|---|
| **E11** | §7: "top-level menu order: overview, principals, scenario slices, **resource types, actions, authorization rules**, decision records"; "catalogue editing pages: keep the resource type, action and authorization rule pages" | **That requirement is void and the implementation matches the latest design.** The latest (v3.1) menu is: overview / principals / scenario slices / scenario instances / scenario rehearsal / decision records / configuration & monitoring (`README.md:15,30,32`; `web/index.html:20-31`). Catalogue data (resource types, actions, params, constraints, authorizations) no longer has standalone management pages; it is **generated by scenario slices and maintained inside the scenario-instance editor**, which edits `ParamDefinition` directly ("this is a ParamDefinition in the metamodel"), the preference scope and the variants. The absence of those three sidebar entries is therefore a design outcome, not a defect; the support for those three collections in `app.js`'s `renderCollection`/`labels` is uncleaned legacy code (no navigation entry, no reachable path). |

---

## 6. Aligned items (11)

| # | Design requirement | Evidence |
|---|---|---|
| F1 | `Authorization.policyStatus` has three states and only active takes part in decisions | `model.py:28`, `shapes.ttl:49`, `store.py:239` (draft/suspended never allow) |
| F2 | Scenario-generated rules default to draft | `api.py:310`, `scenario_llm.py:206`; all 4 local authorizations measured as `draft` |
| F3 | Preference scope global/segmented and `segmentation_schema_version=1` | `api.py:36-76`, `231`, `377` |
| F4 | Rehearsal matches variants exactly by dimension, asks for missing dimensions, and returns `not_applicable` when nothing matches | `api.py:567-584`, `626-629` |
| F5 | A rehearsal has no side effects and writes no decision | `api.py:543`, `636` return `preview:true, side_effects:false` |
| F6 | Dimension fields are automatically synced as runtime required fields and stored separately from preference values | `api.py:225-229`, `360-364`; `required_inputs` and `segmentation` are separate |
| F7 | An authorization that cannot be expressed per variant becomes an ask and pauses | `api.py:454-456` (`effect=ask`, `policy_status=suspended`) |
| F8 | The MCP catalog returns the full `segmentation`; updating a variant's feedback requires `variant_id`; the user's words and the revision enter the evolution log | `mcp_server.py:67-68`, `99-101`; `api.py:512-517`, `495`, `462-468` |
| F9 | Scenario routes are registered before the generic `/{collection}` route | Scenario routes at lines 138-636, generic routes from line 638 (`api.py`) |
| F10 | With no model configured, a clear error is returned and no fabricated result is generated | `scenario_llm.py:153-154`, `api.py:173-174`; `/v1/scenario-slices/provider` exposes configuration status |
| F11 | An unknown operator or unregistered constraint must not lead to allow | `store.py:316` (unknown type `return False`), `store.py:285-286` (regex matcher disabled) |

---

## 7. Suggested convergence order

Ordered as "close security and correctness first, then fill in the metamodel, then polish experience",
matching the dependency order of §24.5:

1. **A1 constraint serialisation** — fix the write path in `model.py` or map `constraint_value`
   uniformly to the `json` type; add an API↔RDF round-trip test. Otherwise every scenario rule is
   dead.
2. **A2 instance-edit 500** — move the `suffix` assignment at `api.py:417` above line 416; add
   regression tests for `/instance` and `/feedback`.
3. **A3 graph-level transaction** — add a "batch write + whole-graph validation + single persist"
   interface in `store.py` and make `confirm`/`delete` use one transaction.
4. **A4 enable endpoint + enable entry point** — add
   `POST /v1/scenario-slices/{id}/activate` (validate + audit), forbid the generic PATCH from
   changing `policy_status` directly, and give the scenario instance/slice page an explicit "enable
   rules" action (with the catalogue pages cancelled, this is the only sensible place).
5. **C1/C2 + A5** — implement the operator allowlist and the `hard/preference` distinction so
   preferences do not enter decision merging.
6. **Metamodel backbone (B1, B3, B4, B5)** — build the 4 classes and collections per §10, migrate the
   existing `analysis` JSON losslessly into real nodes first, and only then discuss the module split
   of §24.1.
7. **Contract and frontend (D2-D5, E7, E9, E10, E12)** — unify the layered API response and frontend
   modularisation last.

> Note: this list only checks and grades; it modified no implementation file. A1 and A2 were both
> confirmed empirically under read-only conditions (A2 ran against a stub store in a temporary
> directory and never touched `~/personal-ontology/data`). E11 was re-judged as "obsolete
> documentation" per the latest design and is not counted as a gap; if any other section of `docs/03`
> still conflicts with the v3.1 design, the latest design document prevails and this list should be
> re-run.
