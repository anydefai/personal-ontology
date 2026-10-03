# Scenario analysis data structure (the `analysis` contract)

This document freezes the structure of a **scenario-slice analysis result**. It is stored in the
`analysis` field of a `scenario-slices` record (an `rdf:JSON` literal in RDF) and is the
**contract between the model's output and the backend compiler**.

> Note the division of labour: `docs/05` freezes the **encrypted container format**, while this
> document freezes the **analysis result structure**. The two are independent. This document
> contains no keys or encryption details.

## 1. Top-level fields

| Field | Type | Meaning |
|---|---|---|
| `title` | string | Scenario title |
| `scope` | object | `{mode:"global"｜"segmented", dimension?, label?}` |
| `resource_types` | array | Resource types this scenario handles, `[{name, description?, existing_id?}]` |
| `actions` | array | Actions of this scenario, `[{name, description?, risk?, existing_id?}]` |
| `required_inputs` | array | Fields to collect on every run (see §2) |
| `facts` | array | Standing preferences (see §2) |
| `questions` | array | Model follow-ups `[{question, field?, reason?}]`; answers are fed back and the analysis re-runs |
| `policies` | array | Authorization policy drafts (see §3), compiled into authorization rules on confirmation |
| `segmentation` | object | Preference scope (see §4), `segmentation_schema_version=1` |
| `generated` | object | **Written by the backend**: what was materialised (see §5); the model must not emit it |
| `demoted_fields` | array | **Written by the backend**: items demoted because they do not fit a runtime field |

## 2. Field tiers (three) — every field must carry `role` and `role_reason`

| `role` | Meaning | Must appear in |
|---|---|---|
| `required` | The value differs per run and nothing can run without it | `required_inputs` **only** |
| `preference` | A standing stance, unrelated to this run, compiled into a decision condition | `facts` **only** |
| `both` | A standing stance **and** a per-run value | **Both** arrays at the same time |

`role_reason` is a one-sentence justification that the interface shows the user for review.

**Why `both` is needed**: `_prune_preferences` used to drop preferences whose field was a runtime
field, and `_compile_rules` downgraded such a field's condition to `exists`, so fields like "only
book within the next 30 days + a specific date" were **inexpressible**. Now a `both` field stays in
the required list **and its standing condition is not downgraded** (`numeric_lte` and friends
compile as usual).

- `required_inputs[]`: `{name, label, type, required, help?, role, role_reason?}`
- `facts[]`: `{name, label, value, type, source, role, role_reason?}`
  - `source="user"` the user stated it; `source="suggestion"` a model suggestion (excluded from the
    preference fallback)

## 3. Policies (`policies[]`)

```
{ subject, resource, effect: "allow"|"deny"|"ask", actions: [action names], conditions: [...] }
```

- **`actions` is required**: each value must be a **name** that appears in this scenario's `actions`.
  Different stances for different actions must be split into several policies ("allow viewing, deny
  deleting" = two policies). If it is missing or the names do not match, the policy falls back to
  "all actions".
- `conditions[]`: `{field, operator, value?}`, `operator ∈ {equals, lte, gte, exists, ...}`.
- **An unconditional deny is forbidden**: when `effect="deny"`, `conditions` is empty and the
  scenario has other policies, that policy is **skipped and recorded in `compile_report`** (deny has
  the highest priority, so an unconditional denial would veto every action).

## 4. Preference scope (`segmentation`)

```
{mode:"global"|"segmented", dimensions:[{field,label,type}], global_preferences:[], variants:[]}
```

A preference item: `{field, label, type, value, operator, strength:"must"}`.
`operator` supports `equals/lte/gte/exists`; **when the value is not numeric, `lte/gte` degrades to
`equals` automatically** (rather than rejecting the whole save). If a field is in
`required_inputs` and is not declared a standing preference, its condition is downgraded to `exists`.

## 5. `generated` (written by the backend)

| Field | Meaning |
|---|---|
| `resource_type_id` / `resource_type_ids` | The first / all materialised resource-type ids |
| `created_resource_type` / `created_resource_type_ids` | Types this scenario **created** (as opposed to reused) |
| `action_ids` / `created_action_ids` | Action ids, and the ids of actions it created |

The first resource type keeps the name `scene_<suffix>_resource`, the rest are `..._resource_N`;
actions keep `scene_<suffix>_action_<n>`. **Deleting a scenario deletes only the types and actions
it created** (reused shared vocabulary is kept).

## 6. Backward compatibility

| Situation | Behaviour |
|---|---|
| A policy lacks `actions` | Falls back to all of the scenario's actions (old data keeps its behaviour) |
| A field lacks `role` | The analysis exit fills in a default tier (required field → `required`, preference → `preference`) |
| Normalisation renamed a field (`budget_max` → `price_max`) | `role` is carried over through an alias table built from the `changes` rename records (`_carry_role`) |
| `role="both"` but the field is in `NEVER_RUNTIME` | It is **not** downgraded and stays in the required list |

## 7. Known model behaviour pitfalls (found by two rounds of scenario-slice derivation)

1. **A policy lacking the action dimension** → "deny deleting" degrades into an unconditional deny →
   vetoes every action (now forbidden at the contract level).
2. **An unconditional deny** → as above (now intercepted and reported).
3. **Cross-domain expansion** → a "files" scenario swallowed the resource types and actions of
   "network connection" (the prompt now constrains this).
4. **Losing multiple resource types** → only `types[0]` was materialised and the rest were silently
   dropped (fixed: every type is materialised).
5. **Putting a field that decides rule boundaries into the required list** → for example the
   operation type (view/edit/delete) is both something known only per run and something rules must
   distinguish. Requiring a per-field `role_reason` exists precisely so this kind of misjudgement
   becomes **visible to a human**.

## 8. Related files

- Implementation: `backend/scenario_llm.py` (prompt and parsing), `backend/api.py`
  (`_compile_rules`, `_normalize_segmentation`, `confirm_scene`), `backend/field_names.py`
  (normalisation and `role` carrying)
- Tests: `tests/test_policy_actions.py`, `tests/test_multi_resource.py`, `tests/test_both_tier.py`
- Container format and encryption: `docs/05-secret-and-sensitive-data-design.md`

## 9. An executable contract

This document is more than prose; two executable pieces accompany it:

**(1) A machine-readable schema** — `schemas/scenario-analysis.schema.json` (JSON Schema 2020-12).
It allows programmatic validation and lets **another implementation** (for example a Swift client,
if the iOS work is ever resumed) align to the contract instead of reverse-engineering the Python.

**(2) Runtime validation** — `validate_analysis()` in `backend/analysis_contract.py`, called at the
analysis exit (`scenario_llm.analyze`), writing its result into `analysis.contract_notes`.

The stance matches the existing tolerance: **a violation does not block the analysis**, it is only
recorded and surfaced in the interface. Each note contains:

| Field | Meaning |
|---|---|
| `code` | A stable identifier (for interface/i18n mapping), e.g. `policy_missing_actions` |
| `field` | The exact location, e.g. `policies[2]`, `required_inputs.城市` |
| `message` | Human-readable description — **currently Chinese only; making it bilingual is pending** (see the first-principle document) |
| `level` | `warn` (the backend already tolerated it) or `error` (a human should look) |

Violations it can catch automatically: missing title / no resource types / no actions / **a policy
missing `actions`** / **a policy referencing an unknown action** / **an unconditional deny** / a
field missing `role` / an invalid `role` value / a field name that is not an English key / a
duplicate field name within one list / `both` that is not in both lists / `required` that is in the
preference list / `preference` that is in the required list.

In the interface, the slice page's "Model's field classification" summary line shows an
**`N contract notes`** badge, and expanding it lists them one by one.

**Tests**: `tests/test_analysis_contract.py` (10/10), covering the five pitfalls recorded in §7.
**Why it matters**: when the model changes version or vendor, you learn immediately whether its
output is still compliant — no need to rediscover problems through another round of derivation.
