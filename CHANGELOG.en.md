# Changelog (English)

This is the English counterpart of `CHANGELOG.md`, required by the
[first principle](docs/00-first-principle-bilingual.md).

**Scope note (please read):** this English file covers changes **from 2026-10-02 onwards** — the
point at which the bilingual principle was adopted. Entries dated earlier exist only in
`CHANGELOG.md` (Chinese). They are not "missing English" by accident: translating the whole
historical log was judged a poor use of effort relative to user-facing material, and the Chinese
file remains the complete record. New entries are written in both files from now on.

---

## 2026-10-02

### Bilingual first principle established

The user made full-stack bilingual support a **first principle**: the interface, data labels,
backend messages, installation/user manuals, design documents and changelog must all exist in both
Chinese and English — not just the pages.

- Added `docs/00-first-principle-bilingual.md`: per-layer requirements, naming conventions,
  **executable checks**, explicit exceptions (user-authored content is not translated; machine keys
  stay English) and five implementation disciplines.
- Added `tests/test_bilingual_coverage.py`: a single inventory of the whole stack's bilingual gap,
  with a baseline that may only decrease.
- Honest status at the time: interface and data labels 🟢/🟡; backend messages, design documents,
  README/manuals and changelog still 🔴 Chinese-only.

### Backend messages made bilingual (70 → 0)

- New `backend/messages.py`: a bilingual `key → {zh, en}` catalog plus `msg_for(key, language)`;
  business code now raises `HTTPException(detail=messages.detail(key, **params))` and
  `@app.exception_handler(HTTPException)` resolves the key from the request.
  This avoids adding a `request` parameter to ~69 endpoints and also works for public endpoints.
- Two failed approaches are recorded for reference: setting `contextvars` in
  `BaseHTTPMiddleware`, and in a FastAPI global dependency — neither is visible inside endpoints.
- 66 message sites converted; the catalog test (`tests/test_messages_bilingual.py`) is 9/9.

### Fixed: language precedence disabled the whole localization layer

`config.display_language()` was `stored_language() or normalize_language(hint) or "zh"`, so the
on-disk setting always won and the `X-Display-Language` request header was **ignored**. Every
per-request localization (data labels, authorization scope labels, backend messages) was therefore
inert. Fixed to prefer the request header, with the stored setting only as a fallback.

Verified at the interface, not just in the workspace:

```
POST /v1/login  X-Display-Language: zh → {"detail":"请输入登录密码。"}
POST /v1/login  X-Display-Language: en → {"detail":"Enter the login password."}
```

### Contract notes made bilingual (13 → 0)

`contract_notes[].message` is user-visible (the "N contract notes" badge on the slice page) and was
Chinese-only. `note(code, field, level, **params)` now carries **the message key (the code) plus
params**; the text moved into the message catalog, and `_localize_scene_labels()` replaces
`message` at read time according to the display language.

### Documentation made bilingual

- `README.en.md` — a complete English counterpart (install, the two-port split and why, first-run
  password and encrypted container, service monitor, agent integration and MCP, scenario
  preferences and variants, backup and cross-machine use, API, security boundaries, indexes).
  The Chinese README's self-check list was also corrected (11 → 17 tests) and now points at the
  English file.
- `docs/06-remote-agent.en.md`, `docs/07-local-agent-access.en.md`,
  `docs/09-scenario-analysis-schema.en.md` — full English counterparts.

### Earlier work in the same session (recorded here for continuity)

- **Field tiers (three)**: `required` / `preference` / **`both`** — a field may be a standing
  stance *and* a per-run value. `_prune_preferences` no longer drops runtime-field preferences and
  `_compile_rules` keeps a `both` field's standing condition instead of downgrading it to `exists`.
  The prompt now requires a `role_reason` per field, and the interface shows the model's
  classification with a review badge and a three-way tier selector in both directions.
- **Four contract gaps found by two rounds of model-driven scenario derivation**: policies lacking
  an action dimension (which degraded "deny deleting" into vetoing everything), unguarded
  unconditional denies, cross-domain expansion, and silently dropping all but the first resource
  type. All fixed, each with a regression test.
- **Scenario analysis contract made executable**: `docs/09`, the JSON Schema in `schemas/`, and
  `backend/analysis_contract.py` with `validate_analysis()` — 13 violation classes caught
  automatically, recorded without blocking, and surfaced in the interface.
- **Interface**: i18n mechanism completed (symbol prefixes, suffix markers, interpolated strings,
  a `MutationObserver` for dynamically inserted DOM, asset version query strings to defeat browser
  caching), agent-authorization scope labels localized, origin policy made proxy-aware while still
  rejecting cross-site requests, and the scenario-preview jump-to-overview bug fixed
  (`location.search` assignment caused a full page reload).
- **Fixes**: a `NameError` on the hotel fallback path (my own regression, caught by the regression
  suite), preference operator/value mismatches rejecting a whole save, and confirmed scenarios
  lingering in the draft list.

### Defence in depth added

- `scripts/verify-deploy.sh` — byte-compares the installed copy against the workspace, after this
  class of "changed the source but the page did not change" mistake recurred four times.
- `tests/test_ui_consistency.py` — nav ↔ route ↔ render consistency.
- Both `docs/00` and the project disciplines now record the hard-won rules: verify against **what
  the server actually serves**, bump the asset version on every frontend change, never validate
  with a hand-written parser, and make idempotency checks specific to the artifact.

### Bilingual: exempt tool-generated lists + English version of the first principle

- **Tool-generated lists are exempt**: `docs/i18n-pending.md` is scan output for maintainers, and
  one copy per language would defeat its purpose. Added `EXEMPT_DOCS` to
  `test_bilingual_coverage.py` and a fourth exception to the principle document.
- **Added `docs/00-first-principle-bilingual.en.md`**: the first principle's own English version —
  the per-layer table, four exceptions, **six implementation disciplines** (two new this round:
  check the language resolution chain first, and report residual Chinese at whole-line level), the
  status table, the current gap, and the newly counted contract-note debt with its resolution.

Total bilingual gap **8 → 6** (5 design documents remain).

### Deploy and tests

### Design-document bilingual work: English docs/08

Added `docs/08-ios-app-plan.en.md` (13.3 KB): a complete English counterpart of the iOS plan — the
three decisions taken, the Python→Swift architecture mapping (including what is *not* ported and the
`web/` reuse), the P0–P8 phases with acceptance criteria, third-party dependencies (zero at
runtime), the three confirmed decisions (Files-app import/export, no merging, key travels with the
container), what is explicitly not done, the risk table, and the **evaluation conclusion: not being
built** (three reasons plus alternatives).

Deliberate omission this round: **`docs/04` was not translated.** It is a dense 46-item gap analysis,
and an incomplete translation would exist as a file that the inventory counts as covered while its
content is partial — gaming the metric rather than meeting the principle.

Total bilingual gap **6 → 5** (docs/02, 03, 04, 05 remain).

### Deploy and tests

### Design-document bilingual work: English docs/02

Added `docs/02-validation-and-runtime.en.md` (23.8 KB): a complete English counterpart of the
validation and runtime specification — validation conventions and namespaces, the 19 SHACL shapes,
field-name alignment, the decision algorithm (request structure, the **ten-step decision order**,
the output contract), the registry specification (eight categories, interface contract, per-category
requirements), the storage specification (partitions, transactions and revisions, privacy,
retention and backup, migration and compatibility), the consistency/error-handling table, and the
implementation boundaries.

**Method**: the SHACL Turtle block (~145 lines) was **reused verbatim** — it is language-neutral and
translating it would only risk inconsistency; only the ~120 lines of prose were translated. This is
the approach to follow for any document containing code blocks.

Total bilingual gap **5 → 4** (docs/03, 04, 05 remain).

### Deploy and tests

### Design-document bilingual work: English docs/05 (the highest-value one)

Added `docs/05-secret-and-sensitive-data-design.en.md` (27.9 KB): a complete English counterpart of
the ontology encryption / login / unlock design — why the skeleton changed, the threat model (T1–T3
covered and not covered), the architecture overview, the **container format specification** (the
two-section structure and its rationale, the algorithm table, the measured basis for the iteration
count, the exact AAD concatenation, the zero-dependency cross-platform paths, the **frozen test
vectors**), the three login/unlock/locked states and endpoints, the passphrase policy (8-character
floor plus three compensating rules plus measured cracking costs), the password-change transaction
flow with its failure-mode table, the credential model (no long-lived credential on disk), LLM
credentials moving into the container, the zero-plaintext invariant and residue handling, the
migration steps, the cross-platform route, audit grading, the interface design, the phased status,
open items and known residual risks.

**Method**: machine blocks — the container JSON, the AAD concatenation, the test vectors — were
**reused verbatim**. The test-vector plaintext (`测试向量：personal-ontology container v1`) is
**input bytes**, and translating it would make implementations produce different ciphertexts, so a
**fifth exception** was added to the principle document: **frozen test vectors and machine data are
not translated**.

Total bilingual gap **4 → 3** (docs/03 and 04 remain).

### Deploy and tests

### Design-document bilingual work: English docs/04 (only docs/03 left)

Added `docs/04-design-vs-implementation-gaps.en.md` (23.2 KB): a complete English counterpart of the
46-item gap check — the historical-snapshot banner, the baseline and conclusion, the P0 blocking
items (A1–A5), the missing generic metamodel (B1–B13), constraints and typed values (C1–C7), the API
contract and flows (D1–D14), validation/migration/code structure/frontend (E1–E14), the obsolete
documentation item (E11, with its re-judgement rationale), the **11 aligned items** (F1–F11, with
file and line evidence), the seven-step convergence order, and the read-only confirmation note.

Total bilingual gap **3 → 2**: **only `docs/03` (724 lines) remains.** The plan is to split it across
two rounds (first half, then second half), recording progress in the changelog each round so that a
partial file is never mistaken for a finished one.

### Deploy and tests

### Design-document bilingual work: docs/03 Part 1 (sections 1–14)

Added the **first half** of `docs/03-scenario-slices-design.en.md` (30.7 KB): goals and boundaries,
the inventory of existing objects and their layered treatment, the generic metamodel (structure
diagram, conceptual responsibilities, field definitions and conditions), information completeness and
proactive suggestions, the hotel-booking worked example, the data flow and joint validation (with
responsibility boundaries), the page and menu design, validation and security principles, the phased
implementation order, the class and property contract (ScenarioDefinition / ScenarioSlice /
ParamDefinition / SlotValue / Clarification / WorkflowStep / Constraint / Authorization lifecycle),
the draft generic API contract, the cross-scenario generality check (online shopping), decisions still
to be finalised, and the recommended default decisions.

**The file carries a `BILINGUAL-PARTIAL` marker** (a header comment stating "part 1 of 2, sections
15–26 pending"). The inventory recognises the marker and **still counts docs/03 as a gap**, so the gap
stayed at 2 this round — **a half-finished file is not treated as done.** The marker and its
convention are documented in both language versions of the principle document.

### Deploy and tests

### Full-stack bilingual target reached: gap reduced to zero (docs/03 Part 2)

Added the **second half** of `docs/03-scenario-slices-design.en.md` (sections 15–26): the draft RDF
class and property naming, SHACL validation boundaries (structural constraints for 8 shapes plus
illustrative Turtle), the compatibility and migration table for 17 existing classes, constraint
migration risk and checkpoints, items to confirm before implementation, the **draft RDF
domains/ranges/cardinalities (about 50 rows)**, dynamic values and canonical expressions, the legacy
constraint conversion table, the six executable migration phases, the **canonical API↔RDF field mapping
table (20 rows)** and state transitions, the code structure design (backend modules, draft routes, DTOs
and storage format, frontend modules, dependency order), the code design review checklist, and the
implemented version (preference scope and variants). The `BILINGUAL-PARTIAL` marker was removed.

**The full-stack bilingual gap went 2 → 0**, and two flaws in the inventory itself were fixed:
1. searching the whole file for the marker string misjudged explanatory prose as a partial translation
   → it now recognises only an **HTML comment in the file header**;
2. the contract-note count treated `note()`'s Chinese **docstring** as user-visible text → it now counts
   the real shape, `"message": "…Chinese…"`. That correction exposed **a genuine leftover**: the
   `not_an_object` message was hard-coded Chinese bypassing the catalog — now a message key in the
   catalog.

**Achieved-state semantics**: with the baseline at 0, the inventory requires the gap to be **exactly
0**; any new artefact lacking its other-language counterpart now fails immediately.

### Deploy and tests

### Release preparation: licence, ignore rules, front-page screenshot and path fixes

Preparation for publishing to GitHub (the Chinese README remains the default view):

- **Added `LICENSE`**: the full official GNU GPL-3.0 text (674 lines).
- **Added `.gitignore`**: explicitly excludes user data and credentials (`data/`, `*.po.json`,
  `*.key`, `session-token`, `agent-clients.json`, `settings.json`, `*.log`, `backup/`), plaintext
  graphs in the repository root, Python artefacts, and macOS/editor files.
- **README (both languages)**: added the **console overview screenshot**, a status line (v3.1 ·
  macOS only · single user · GPL-3.0), a one-sentence positioning statement, and a **licence**
  section (including the GPL-3.0 versus AGPL-3.0 trade-off).
- **`docs/images/`**: added a placeholder `overview.png` (1600×900, clearly marked for replacement)
  plus an explanatory file stressing that **screenshots must not contain real principals, scenarios
  or personal data**.
- **Fixed a release blocker**: five tests hard-coded the absolute path of the local workspace
  (`test_policy_actions`, `test_both_tier`, `test_temporal`, `test_hotel_fallback`,
  `test_multi_resource`) and now use `pathlib.Path(__file__).resolve().parent.parent`; four of them
  also gained a missing `import pathlib`. The other tests already used the correct form.
- **Removed personal traces**: the absolute workspace path in `CHANGELOG.md` was reworded.

Pre-publication audit: the workspace contains **no container, key, token, log, plaintext graph or
API-key-shaped string**; the only `.ttl` files are the metamodel and SHACL, which should be published.

### Deploy and tests

### Removing personal domain traces: namespace and identifier rename

Before publication, every trace of the old domain identifier was removed (code, ontology, metamodel, tests, documents
and scripts).

| Item | Old value | New value |
|---|---|---|
| RDF namespace | the old personal-domain namespace (fully removed from the repository) | `urn:personalontology:ontology#` |
| launchd labels | `tech.<old-domain>.personal-ontology` / `.backend` | `personalontology.personal-ontology` / `.backend` |
| iOS UTType (documents) | `tech.<old-domain>.personal-ontology.container` | `personalontology.personal-ontology.container` |

14 files, 22 occurrences. **Changing the namespace affects stored data**: every triple in the container
carries the old namespace, so changing only the code would make the ontology look empty. Therefore:

- **`scripts/rename-namespace.py`** renames the RDF namespace inside the encrypted container. The old
  namespace is **not hard-coded** — it is auto-detected from the container contents
  (`@prefix po: <…>`), so no trace of the old domain remains in the repository. It rewrites only the
  `ontology` section and leaves `model_service` byte-identical; it re-decrypts and verifies afterwards
  (same triple count, old namespace gone, `model_service` unchanged); and it is repeatable.
  It was exercised end to end on a **synthetic container**: dry run, migration, read-back verification
  and an idempotent re-run all pass.

**Deployment order (must not be reordered)**: stop the services → run the migration → sync the new code
to the installed copy → reinstall the LaunchAgent (unloading the old label) → start → verify. The
migration needs the container passphrase, so the user runs it.

Regression: vault 37/37, api_auth 42/42, policy_actions 7/7, both_tier 4/4, analysis_contract 10/10 and
the rest all green.

### Deploy and tests

### install.sh fix: the commands documented in the README did not work

`install.sh` copied only `backend/ ontology/ web/ assets/ requirements.txt README.md` and **missed
`tests/ scripts/ schemas/ docs/`**, while the README documents
`~/personal-ontology/.venv/bin/python tests/...` and `scripts/verify-deploy.sh`. A fresh install
following the documentation would therefore **not find those files**.

Fixed: installation now creates and copies `tests/ scripts/ schemas/ docs/` plus
`README.en.md / CHANGELOG.md / CHANGELOG.en.md / LICENSE / install.sh`. The installed copy was also
backfilled and the documented commands verified
(bilingual_coverage / api_auth 42/42 / vault 37/37 / i18n_rules 8/8 / ui_consistency 5/5 / temporal 50/50).

### Deploy and tests

### Correcting two residual Chinese strings in the English screenshot

`docs/images/overview-en.png` contained two Chinese strings (`最近 10/02 22:48` and
`已发布 · 智能体可读取 · 规则 4 条 · 更新于 …`). Their translation rules were **wrong**: the rule
expected `N 条规则` while the product actually renders `规则 N 条` — a **different word order**, so the
rule could never match.

The rules are fixed and verified (including the singular `规则 1 条 → 1 rule`), so the screenshot now
shows the **product's actual post-fix English rendering** for those two spots (font size derived from
the source Chinese pixel height and unified across all three; text and background colours sampled from
the original). Nothing else was touched. The scenario names 处理文件/预订机票 are user data and
correctly stay in Chinese per the exceptions.

**Lesson**: static source scanning cannot catch gaps of this kind — the concatenation order only exists
at runtime — so **a rendered screenshot is a valid end-to-end check**.

### Deploy and tests

### Professional-judgment track, R1: the data model stands up

Three new layers for professional-skill scenarios — **all purely additive; the daily-life track is
untouched**:

| Collection | Purpose | Key fields |
|---|---|---|
| `domain-packs` | Domain packs: industry vocabulary and follow-up templates | bilingual display names, version, lifecycle, **the four-slot structure**, field vocabulary, follow-up templates |
| `scenario-definitions` | Scenario definitions: reusable professional task skeletons | bilingual display names, **may reference several domain packs** (cross-domain), **premise-field skeleton**, version |
| `knowledge-entries` | Judgment entries | points at a slice, **premise / conclusion / exception / basis**, authority level, applicability, review state and reviewer |

`scenario-slices` gained only two fields: `scenario_definition_id` (relation) and `scenario_profile`
(JSON). **Leaving them empty preserves the previous behaviour**, so **no existing data was migrated**.

Built-in data (seeded idempotently on unlock): **one legal domain pack `legal.cn`** plus **three scenario
skeletons** (acquisition assessment / employment compliance / contract review), each with bilingual
labels, premise fields and four-slot naming.

**New test `tests/test_professional_model.py`: 23/23 passing.** It covers the built-in data and its
idempotence, multi-valued relations reading back as arrays, bilingual slots, **existing slices behaving
exactly as before when no profile is set**, a professional slice attaching to a scenario definition, and
entry relations and JSON round-tripping.

**A real trap found and fixed along the way**: a new collection **must not reuse an existing
predicate**. `po:isBuiltin` carries `rdfs:domain ResourceTypeDescriptor` and `po:updatedAt` carries
`rdfs:domain ScenarioSlice`; with RDFS inference enabled during validation the new nodes were **inferred
into the wrong classes**, producing twelve confusing SHACL violations. Unique predicates
(`packIsBuiltin` / `definitionIsBuiltin` / `definitionUpdatedAt` / `entryUpdatedAt`) fixed it.
**Lesson**: `rdfs:domain` declarations make predicate reuse **not free** — check domain and range before
adding a collection.

Full regression: the 18 existing suites are green; the bilingual gap is 0.

### Deploy and tests

### Professional-judgment track, R2: mode entry, judgment-entry editor and the instance page

Without touching the daily-life code path, the professional track gained an entry point and hand-entry:

- **A mode switch at the top of the scenario-slice and scenario-instance pages**: "Daily-life
  scenarios" / "Professional scenarios". Daily mode keeps its original renderers (unchanged) while
  professional mode **branches off early** into new functions.
- **The professional slice page**: pick a built-in skeleton (acquisition assessment / employment
  compliance / contract review) or create a new judgment rule set, then fill in the scenario's
  **premise-field skeleton** plus conclusion, exception, basis and authority level (statute / judicial
  interpretation / precedent / personal experience).
- **Entries start as drafts** and must be explicitly enabled from the list; they can also be moved back
  to draft or deleted, reusing the existing draft-to-active discipline.
- **The professional instance page** lists only **enabled** entries, showing their scenario, premise,
  conclusion, basis and authority level.
- **No new backend endpoints**: everything reuses the generic collection CRUD
  (`knowledge-entries` / `scenario-definitions`).
- The asset version `?v=` moves to **20261004a**.

**Bilingual**: 37 new entries; `test_i18n_coverage` reports **55 uncovered (baseline 60)**, five fewer
than before this change. Two traps were handled: (1) the scanner strips a trailing full stop, so the
source string and the runtime node differ and the entry would never apply — trailing full stops were
removed from the new captions; (2) Chinese glued to digits inside templates produces fragment strings —
Chinese words are now split into their own nodes.

**New `tests/test_professional_ui.py`: 18/18 passing**, covering the mode entry, the early branch with
the original renderers still present, reuse of generic endpoints with no bespoke endpoint added, the
four-slot editor and the review flow, the bumped asset version, and entries for the key professional
strings.

The full regression is **19 suites green**, and as per discipline the **files the server actually
serves** were verified: the served app.js contains the new mode, index.html carries `?v=20261004a`, and
the served i18n.js contains the new entries.

### Deploy and tests

### Two live defects fixed: the professional-mode entry did nothing, and restarting the backend raised Internal Server Error

**1. Clicking "Professional scenarios" on the scenario-slice page did nothing.**
The mode buttons' click handlers were bound only inside the two **professional** renderers; the entry on
the **daily** path was never bound. Fixed with **event delegation**: one listener registered at init
responds no matter which renderer drew the buttons, and the per-render bindings were removed so a click
cannot trigger multiple renders.

**2. Restarting the backend from Service monitor raised Internal Server Error and then required a new
login.** The root cause was **a regression I introduced during the bilingual work**: `manager.py`
called
`display_language(request.headers.get("x-display-language"))`
without **importing the function**, so the call raised `NameError`. `py_compile` and importing the module
cannot catch a `NameError` inside a function body — only a real call exposes it — and the manager
endpoints had **no test coverage at all**, so it stayed broken. The import is restored and
`tests/test_manager_endpoints.py` (24 checks) was added: (1) an AST-based static check that no backend
module uses a shared helper it has not imported — a general guard for this class of bug; (2) an
assertion that `display_language` really resolves in the manager namespace; (3) the read-only endpoint
works online (`/manager/health`); (4) the control endpoints (status/start/restart/logs) are
**registered** — calling them would really restart the backend, so they do not belong in a test.

**End-to-end verification** with a real session token:

```
POST /manager/restart  →  {"ok":true,"message":"治理后端已重启。"}   HTTP 200
```

(previously 500). The full regression is now **20 suites green**.

### Deploy and tests

### Fixing "frontend changes take no effect": the console HTML was cached by the browser

**Symptom**: after the professional-mode entry was fixed, clicking it still did nothing.

**Root cause**: `manager.py` served the console HTML **without any cache header**:

```
return FileResponse(WEB_DIR / "index.html")
```

Browsers therefore cache `index.html` itself — and the `?v=` asset version lives inside that HTML. So
the page kept loading an **old app.js**, and no frontend change could ever take effect. This is the same
root cause behind several earlier "my change didn't apply" reports in this project.

**Fix**: the console HTML now returns `Cache-Control: no-store, no-cache, must-revalidate` and
`Pragma: no-cache`. The versioned assets (`app.js`, `app.css`, `i18n.js`) keep their long cache via
`?v=`; only the HTML is uncached.

**Verified** against the server's actual response headers:

```
HTTP/1.1 200 OK
cache-control: no-store
pragma: no-cache
asset version in HTML: assets/app.js?v=20261004a
```

`tests/test_manager_endpoints.py` gained two assertions (**25/25**): the HTML must carry `no-store` and
must reference the current asset version — so this class of problem is caught by the regression suite.

### Deploy and tests

### Professional track R2.1: engineering words replaced with plain language, plus a copyable example

User feedback: on the professional page they "did not know how to type anything" and "did not understand
what a judgment rule set is" — a wording problem. The UI used engineering terms (judgment rule set /
entry / premise / conclusion / exception) while the person's own mental model is simply four parts.

**Now four plain parts**: "My judgment" / "Start entering my judgments" instead of rule set;
"Situation" instead of premise; "My judgment" instead of conclusion; "Does not apply when" instead of
exception; "Basis" plus "Source" (statute / judicial interpretation / precedent / personal experience);
"Confirm and enable" / "Back to draft" for the review states.

**Three additions that lower the barrier**:
- a **real example printed on the page** (acquisition assessment: target industry Internet, deal size
  CNY 800m, jurisdiction Shanghai → judgment → does not apply → basis);
- a **"Fill in the example above" button** that populates the form so you can see what a filled-in entry
  looks like;
- **example placeholders** in every input, and guidance-style empty states and alerts.

**Process and lessons**:
- The first attempt edited the example sentence by text slicing and **cut across a function boundary**,
  breaking app.js. It was restored with `git checkout` and redone as an **atomic replacement of the whole
  function**, with the div balance (15/15) and the following functions verified intact.
  Lesson: for these very long single-line templates, replace whole functions — never slice text.
- A leftover probe backend of mine on port 8899 made `test_agent_access` and `test_mcp_e2e` fail
  spuriously; after cleanup they are back to 24/24 and 17/17. Lesson: clean up temporary processes.
- `test_professional_ui`'s asset-version assertion now matches a **prefix**, so future bumps need no test
  edit.

Asset version → **20261004b**; bilingual uncovered count **56 (baseline 60)**; all **20 suites green**.

### Deploy and tests

### Removing the self-invented acquisition example (confirmed by the user) and making built-in data correctable

The user pointed out that the "acquisition assessment" example I had shown was **not their logic** — and
they were right. I had **invented** that example, because the DeepSeek share link never yielded any
content (I tried three times). They then pasted the full text: a skill model for "M&A valuation
judgment" containing **industry weight tables, dynamic-threshold arithmetic, multi-signal cross
validation, exception overrides, signal priority, confidence backtesting, a decision package,
authorization limits and billing tiers**. What I built — a condition, a conclusion and a free-text
exception — **cannot express that logic**; the gap analysis was delivered separately.

**What this round removed**:
- the **example sentence** on the professional page (my invented industry/deal-size/jurisdiction);
- the **"fill in the example" button** and its filling logic;
- the invented **placeholders** (Internet / CNY 800m / Shanghai / three years);
- the invented **`premise_fields`** in the seeded data for all three built-in skeletons;
- when premise fields are empty the page now says: "this scenario has no premise fields defined yet, so
  just write the judgment; premise fields will appear once the skill framework is ready".

**A structural problem fixed along the way**: built-in seeding used to be **create-only**, so anything I
seeded into a container **could not be removed**. `domain-packs` and `scenario-definitions` are now
**authoritative from code**: when their content differs, the record is rewritten — which makes retracting
a bad seed effective while leaving user records alone.

**Tests updated**: `test_professional_model` used to assert "premise-field skeleton defined" — exactly the
invented content. It now asserts that built-in skeletons **carry no invented premise fields**, freezing
this decision as a regression guard.

**The same mistake twice**: I hard-coded the asset version in a test again (first
`test_professional_ui`, then `test_manager_endpoints`). Both are now dynamic: the former matches a
prefix, the latter compares the version in the workspace's `index.html` against the served HTML — which
incidentally makes it a genuine "has the deployment been synced?" check.

Asset version → **20261004c**; all **20 suites green**; bilingual uncovered **55 (baseline 60)**.

### Deploy and tests

### Skill-framework executor R3': making professional judgment actually computable

After the user pasted the full logic (Lawyer Zhang's M&A valuation judgment), the agreed priority was
**make it truly compute** (option A).

New `backend/skill_framework.py` (234 lines) turns a professional judgment framework into a
**declarative, executable** structure covering all five parts of the user's design:

| Framework part | Role |
|---|---|
| `inputs` | input field definitions (name/type/enum values) |
| `industry_map` + `industry_weights` | step 1: industry → category → weight set |
| `thresholds` | step 2: base threshold plus conditional adjustments (**arithmetic**) |
| `signals` | named boolean signals that may declaratively reference the dynamic threshold |
| `combination_rules` | step 3: several signals ANDed → conclusion plus severity |
| `exception_rules` | step 4: conditions → overrides (reduce a weight / adjust the threshold / force a conclusion) |
| `signal_priority` | step 5: signal priority, used to order matched combination rules |

**The decision package** carries the conclusion, severity, confidence (passed through), a **six-step
reasoning path**, evidence (including the dynamic threshold), matched rules, which signals fired and why
the others did not, and the framework version it cited.

**Safety follows the project's existing discipline**: conditions use only **registered operators**
(`eq/neq/gt/gte/lt/lte/in/not_in/contains`) and an unknown operator **never allows**, with a stated
reason; derivations are **declarative references** (for example "compare against the dynamic threshold")
and **no arbitrary formula or code is executed**; a missing field or a type mismatch simply fails to match
and says why, rather than passing silently.

**`tests/test_skill_framework.py` (18/18) encodes the user's framework and case verbatim** and asserts —
successfully — the same decision package they wrote: **conclusion 估值偏高, severity 高, dynamic
threshold 1.45, P/E 45 > 30×1.45=43.5, six reasoning steps, no exception triggered because the technology
is only partly patented, and evidence listing 43.5.** It also covers the failure paths: regulation
tightening plus a financial-sector target forces the conclusion through an exception override, and both
an unregistered operator and a missing field refuse to match.

**Stated plainly**: the executor is **not yet wired to the API or the UI** — that is the next step
(having the professional preview page call it). What this round proves is that the framework **can express
your logic**, and it can.

All **21 suites green**.

### Deploy and tests

### R3'.1: the skill framework wired to the API and the interface (the decision package is now visible)

**Backend**
- `scenario-definitions` gained **`framework`** (the skill framework JSON) plus **`confidence` /
  `confidence_status` / `confidence_basis`**.
- New **`POST /v1/scenario-definitions/{id}/evaluate`**: read the definition's framework, judge one set of
  inputs, return the decision package. No framework → **409 with an explicit message**; unknown definition
  → 404; invalid input → 422; a broken framework → 422 stating the reason. Four new bilingual backend
  messages were added, with the English path covered by a test.
- **A data-loss hazard I had planted myself is fixed**: the previous round's "built-in records are
  authoritative from code" rewrite also **wiped fields the user had added**. It now clears **only the
  fields the seed declares**, so a `framework` or `confidence` configured on a built-in scenario survives
  upgrades — verified by a test that seeds again and checks they are still there.

**Interface** — the professional-mode **preview page**:
- choose a scenario; if no framework is configured it offers a **paste-the-framework-JSON** box and a
  "Save framework" button;
- with a framework configured, the case-data inputs are **rendered dynamically from the framework's
  `inputs`** (number / enum / text);
- pressing Evaluate shows the **decision package**: conclusion, severity, confidence with its basis, the
  cited framework version, the **step-by-step reasoning path**, and an evidence table (factor, value,
  benchmark, dynamic threshold, source);
- the page states plainly that a preview **writes no decision record and executes nothing**.

**New `tests/test_skill_evaluate_api.py` (15/15)**: writes Lawyer Zhang's framework through PATCH, calls
the evaluate endpoint, and receives the decision package matching the user's design (估值偏高 / 高 /
threshold 1.45 / six steps / evidence 43.5 / confidence 0.78), plus the 409, 404 and 422 failure paths,
the **English rendering of the error**, and the "re-seeding keeps user fields" guarantee.

**The same class of mistake, a second time**: in the new endpoint I wrote `detail(...)` while this project
conventions call `messages.detail(...)`, producing a `NameError` — the same class of bug as
`display_language` in `manager.py`. The static guard's `WATCHED` set now **includes `detail`**, so
"used but not imported" is caught by tests from now on.

All **22 suites green**; asset version → **20261004d**.

### Deploy and tests

### Fix: professional mode "seemed absent" (no switch on the preview page, and mode reset on reload)

The user reported that the preview page looked unchanged. Investigation found **two design defects**, not
caching:

1. **The daily preview page had no mode switch.** The switch only appeared on the scenario-slice and
   instance pages, while the preview page carried it only **in professional mode** — so from the daily
   preview there was no way to switch over at all, a self-contradictory entry point.
2. **`professionalMode` lived only in memory**, so a reload dropped back to daily mode and the
   professional features appeared not to exist.

Fix: the mode is persisted in `localStorage` (key `po.professionalMode`) and survives reloads and page
changes, and both render branches of the daily preview page (empty state and populated) now carry the
switch, so all five pages can switch.

**Recorded from the process**: the first attempt at this patch failed. My replacement anchored on
`"SCENARIO PREVIEW"` while the actual text is `"SAFE DRY RUN"`, and I had **not asserted each
replacement**, so the script aborted mid-way and saved nothing (fortunately without corruption). The redo
asserts every replacement and verifies the counts before writing (2 in the preview page, 7 in total).
**Lesson: batch text replacements must assert each edit and check the total before writing.**

`test_professional_ui` gained two assertions (**24/24**): the mode choice is remembered, and the preview
page carries a switch too.

All **22 suites green**; asset version → **20261004e**.

### Deploy and tests

### R5': confidence and backtesting (the decision package is no longer "unverified")

This is step two of the design: import historical cases, run the framework over them, compare against the
actual outcomes, and derive a confidence.

**New `backend/skill_backtest.py` (61 lines)**: runs `judge()` per case and compares against the case's
`actual_result`, with the **comparison rule stated explicitly** — the conclusion must equal
`actual_result` **exactly**, no fuzzy matching — returning the sample size, matches, mismatches, the
**accuracy** and up to 20 mismatch details. **Confidence levels** are defined with the first two
implemented and the rest reserved: `unverified` → `backtested` → `preliminary` (≥10 caller feedbacks, not
implemented) → `stable` (≥100) → `certified` (third-party). **With no cases the confidence stays
"unverified"** and the caller decides, matching the design.

**New `POST /v1/scenario-definitions/{id}/backtest`** accepting `{"cases":[…], "persist":true}`; when
`persist` is set, `confidence`, `confidence_status` and `confidence_basis` are written back to the
scenario definition. Failure paths are explicit: no framework → 409; malformed cases → 422 naming which
case is missing what.

**Interface**: the professional preview page gained a "Confidence and backtesting" section showing the
current confidence, a box to paste cases, a Run-backtest action with agreement rate and mismatch details,
and a Save-as-confidence action. Once saved, **decision packages carry the confidence** — the loop is
closed.

**New `tests/test_skill_backtest.py` (16/16)**: builds 50 cases of which 39 agree, yielding an
**accuracy of 0.78**, the number from the design; it also covers no cases → unverified, explicit errors
for missing fields, persistence through the API, and that the **decision package can read it back**.

All **23 suites green**; asset version → **20261004f**.

### Deploy and tests

### Steps 1–2 backend: natural language to a skill-framework draft

The model service was verified live (`deepseek-flash`; the connection test returned "connected, the model
responded").

**New `backend/skill_draft.py` (117 lines)**: per steps one and two of the design, a natural-language
description is turned into a model-drafted framework, with the module explicitly not overstepping: the
prompt requires that **anything the description does not mention stays empty and nothing is invented**
(matching the design's own note that the model does not know the expert's specific judgments); the model's
output passes through **normalisation** before being returned (only known parts kept, unknown fields
dropped, type mismatches skipped); **an unconfigured model raises an explicit error (503)** rather than
returning a fabricated draft; and `adjustment_log` starts empty, to be filled as the expert adjusts each
part — step three being the real source of professionalism.

**New `POST /v1/scenario-definitions/{id}/draft`** accepting `{"description": "…"}` and returning the draft
with a note.

**New `tests/test_skill_draft.py` (11/11)** replaces the model call with a stub, needing neither network
nor real data; it covers six normalisation discards, the too-short-description error and the 404 / 422 /
503 failure paths.

**Two mistakes this round, both recorded**: (1) wrong import names (`read_model_service` /
`model_endpoint` while the actual exports are aliases of `_read` / `endpoint`), which **took the backend
down** until fixed to match `scenario_llm.py`; (2) **I deployed without running the tests first** — exactly
the discipline I had written down one round earlier. Running the tests would have caught the import error
immediately, so the workflow is now test-first, and it will be followed strictly.

All **24 suites green**.

### Deploy and tests

### Rebuilding the interface around Lawyer Zhang's scenario: `web/pro.js` (steps 1-4)

The user asked for a rebuild **according to the design** and pointed out that I had simplified it on my own
initiative — downgrading five parts to a four-slot form and "the expert adjusts each item" to "paste some
JSON". This round replaces the professional-mode scenario-slice page wholesale with the design's four
steps: (1) choose a scenario and write a paragraph, then **draft the framework** through the ready
`/draft` endpoint; (2) **visually edit the five parts** — input definitions, industry weight table,
dynamic thresholds, combination rules with signals, exception rules and signal priority, all with
add/remove rows; (3) an **adjustment log** where each change records what changed and why, stored in
`adjustment_log`, the source of professionalism in the design; (4) evaluate and backtest on the Skill
preview page to obtain a confidence.

**The key change of method, and the root cause of three earlier failures**: the new interface lives in a
**separate file, `web/pro.js` (357 lines)**, rather than being spliced into the 500-line `app.js`. `app.js`
changes in exactly **one place** — professional mode calls `window.POPro.renderSlices(view)` — and the old
interface is **kept as a fallback** so a failed pro.js load cannot white-screen the page. `index.html` gains
one script tag, loaded after app.js. Edits go into memory first, and saving rebuilds the framework from
memory and PATCHes it.

**Prompt refinement**, addressing the sparse drafts seen in live testing: dimensions, conditions, signals
and exceptions mentioned in the description must all become entries; weights without given numbers default
to equal shares and threshold adjustments to zero as **placeholders to adjust**; only parts the description
never touches stay empty.

**Two things stated plainly**: (1) the prompt change is **on disk but the backend was not restarted**, so
"draft the framework" still uses the old prompt and the new one takes effect at the next restart — which
avoids logging the user out again; (2) `pro.js`'s interface text is **Chinese only** for now, because the
bilingual scanner covers only `index.html` and `app.js`; the next round brings pro.js into the scanner and
adds the English entries.

All **24 suites green**; the server is confirmed to serve the new files (`pro.js` HTTP 200, 22,535 bytes;
app.js delegates).

### Deploy and tests

### Fix: daily-life and professional scenarios were mixed together

The user reported that unconfirmed drafts from the professional side **appeared among the daily-life
scenarios**. The cause: the daily side never excluded professional slices — the professional side filtered
on `scenario_profile.kind === "professional"` while the daily side filtered on nothing at all.

The fix adds one shared predicate and applies it in four daily places: the scenario-slice draft list (which
also corrects the sidebar count), the scenario-instance page, the preview page, and the dashboard's "my
scenarios", to-dos and counts.

**Existing data needs no migration**: professional slices already carry `scenario_profile`; only the
interface failed to filter them.

The UI test gained two assertions (**26/26**): the daily side must carry `!isProSlice(x)` in all four
places, and the predicate is shared.

This was also the first time I drew the boundary between the two profiles at the **list-filtering** level;
previously only the professional side filtered, one-directionally, which was a design oversight.

All **24 suites green**; asset version → **20261004i**.

### Deploy and tests

### Professional scenarios can now be added (previously locked to the three built-ins)

The user asked why step one offered only one of three scenarios and whether it could be extended. The cause
was that the three skeletons were seeded in R1 with **no way to create a scenario**, leaving the list
fixed.

The fix, inside `web/pro.js` step one, adds **create, rename and delete** for scenario definitions:
creating sends a name to `POST /v1/scenario-definitions`, attaches it to the existing domain pack and
selects it immediately; renaming PATCHes `display_name_zh` and `display_name_en`; delete appears only for
**non-built-in** scenarios. Along the way a field-name error was corrected: the domain pack field is
**`domain_pack_ids` (an array)**, not `domain_pack_id` — verified with a probe outside production data for
create, rename and delete before touching the interface.

This maps onto the design's four layers: domain pack → **scenario definition (shareable, now creatable)** →
scenario slice (the personal judgment asset) → judgment entries.

UI tests are at **29/29** (adding: the separate file and its four steps, the create/rename/delete entries,
the `domain_pack_ids` field name, and the single integration point with fallback). All **24 suites green**;
asset version → **20261004j**.

### Deploy and tests

### A + B done: the new prompt is live and pro.js is inside bilingual coverage

**A (backend restart)**: the refined prompt is live (backend healthy, manager HTTP 200). "Draft the
framework" now returns a draft **with a skeleton**: dimensions and conditions mentioned in the description
become entries, weights without numbers become **even shares**, threshold adjustments become **zero
placeholders** to be adjusted, and only parts never touched stay empty.

**B (pro.js bilingual)**: the scanner now includes `web/pro.js` (previously only `index.html` and `app.js`),
and it writes the **complete uncovered list** to `/tmp/i18n-uncovered.json` — taken **from the scanner
itself**, not guessed, which was exactly the lesson from the previous round's wrong-script extraction. The
Chinese code comments in pro.js were converted to English (i18n exempts comments, removing ten noise
entries at once), **61 English entries** were added, and the numeric prefixes of seven panel titles were
split into their own elements — otherwise the runtime text node "1 · 输入定义" would not match the
dictionary key "输入定义", leaving the metric satisfied while the interface stayed untranslated. The result:
**pro.js has 0 uncovered strings**, total 58 against a baseline of 60.

All **24 suites green**; asset version → **20261004k**.

**Still to come from the design**: `boundaries` (amount limit, allowed scenarios, no resale), the
**first-layer authorisation decision** (token audience, scenario scope, amount limit, no resale),
`owner_signature` / `owner_credentials` / `valid_until`, and billing tiers.

### Deploy and tests

### Option A landed: engineering vocabulary replaced with wording a domain expert understands

The user pointed out that the input definitions asked a lawyer to choose `string`, when an expert is a
domain expert and not a modelling engineer. With option A confirmed (rework the existing editor; the data
format unchanged), `web/pro.js` was rewritten as a whole (451 lines).

**Types went from three technical names to six descriptions of what they hold**: `string` → "a description
or a name"; `number` → "a number"; `enum` → "pick one of a few options"; plus three that were missing
entirely — **Yes/No**, **several at once**, and **amount** — each with a generic example (no domain content
invented).

**The rest of the vocabulary was replaced too**: input definitions → "what I need to know"; signals →
"what I watch"; thresholds → "the baseline"; combination rules → "when several observations occur
together"; exception rules → "exceptions"; priority → "which observation matters more"; adjustment log →
"my adjustment log".

**The worst offender is gone**: a signal's value used to require writing `{"ref":"field","times":"threshold"}`
by hand; it is now a **"× baseline" checkbox plus a "multiplied by which field" box**, so the expert never
writes JSON (confirmed: zero occurrences served).

**Exception rules now show only the inputs the chosen kind needs**, and the operators were translated from
`gt/gte/lt/lte/eq/neq/in/not_in/contains` to greater than / at least / less than / at most / equal to /
not equal to / is one of / is not one of / contains.

**The preview page supports the new types** (`app.js`): Yes/No becomes a **real boolean** and several-at-once
becomes an **array** — otherwise they would reach the evaluator as strings and the semantics would be wrong.

**Bilingual**: pro.js has **0 uncovered strings**, with 105 English entries added and three Chinese comments
converted to English. For hints **ending in `）`**, an extra "runtime original" key was added, because the
scanner strips a trailing `）` and the stripped form alone would leave the English unused.

**Stated plainly**: three hints still contain characters such as `→` or `+0.15`, which the scanner splits
into several runs, so their English keys do not match the runtime text node and **those three stay Chinese
in English mode**; rewriting them without those characters next round fixes it.

This is a front-end-only change: **no restart and no re-login needed**. All **24 suites green**; asset
version → **20261004m**.

### Deploy and tests

### C1 + C2: boundaries for outside calls and the first-layer authorisation decision

The user asked for the rest of the design, and this round lands its most important layer: **"may it be
called at all"**.

**C1 - boundaries** (stored on the scenario definition, separate from the judgment content):
`boundaries = {max_amount, allowed_scenarios, confidentiality}`, with a new "boundaries for outside calls"
panel in the interface, saved together with the framework.

**C2 - first-layer authorisation** (new `backend/authorization.py`, 76 lines, plus
`POST /v1/scenario-definitions/{id}/authorize`): it checks that boundaries are declared, that the caller and
purpose are identified, that the purpose falls inside the allowed list, that the caller promises not to
resell, that an amount ceiling is declared, and that the amount is readable. Failing any of those refuses
the call. **Exceeding the ceiling is not a refusal** — it raises the outcome to "confirm", the design's own
wording being that a 1.5bn call against a 1bn ceiling becomes "needs confirmation" and the owner decides.
The implementation therefore marks the ceiling check as **non-blocking**; it can only promote allow to
confirm, never to deny. Outcomes are `allow` / `confirm` / `deny`, each with per-check detail for the
interface and for auditing.

**New `tests/test_authorization.py` (16/16)**: allowed; over-ceiling becomes confirm; purpose out of range
refused; no no-resale promise refused; missing caller or amount refused; no boundaries declared means
default refusal; and all three outcomes through the API.

**A2 finished**: hints containing `→`, `+0.15` or `=` were rewritten so the scanner treats each as one run,
which means those English entries now actually take effect (three of them previously did not, because they
were split into fragments).

All **25 suites green**; asset version → **20261004n**; the authorisation route is registered.

**Note**: this round included backend changes and **the backend has been restarted, so you will need to log
in once more.**

### Deploy and tests

### Fix: the scenario-instance page lost the professional-mode switch

The user reported that after choosing "daily-life scenario" on the scenario-instance page, the
professional-scenario button was gone, so there was no way back.

**This was the third instance of the same class of bug**: the mode switch was duplicated inside individual
render functions, so any branch that forgot it left its page unreachable — the first time was the preview
page, and I only patched that one page rather than the cause.

**This time the cause is fixed**: the router now carries a fallback that, for the three pages supporting
professional mode, adds the switch when the rendered output lacks it, with a `querySelector` guard so a page
that already drew it does not get a duplicate. Future pages of this kind only need their id added to that
list, instead of every render function being patched.

UI tests **31/31** (a new assertion pins the fallback so the bug cannot return); all **25 suites green**.
This is a front-end-only change: **no restart and no re-login needed**; asset version → **20261004p**.

### Deploy and tests

### (1) professional_insight, (2) signature/credentials/validity, (3) billing tiers, (4) feedback loop

The last four pieces of the design all concern the **outbound deliverable, the decision package**, so they
were implemented together.

**(1) Professional insight**: scenario definitions gain `insight`, and the package carries
`professional_insight`; the interface gains a "what is attached when delivering outside" panel covering
insight, credentials and validity in days.

**(2) Delivery identity**: `owner_credentials`, an `audit_id` (`AUDIT-date-random`), `valid_until` computed
from `valid_days` (default one day, matching the design's example), and a `content_fingerprint` (SHA-256 over
the judgment core, reproducible).

**The digital signature is not implemented** — it needs a key pair — and this round **does not pretend
otherwise**: the package states `owner_signature: null` with `signature_status: "not_implemented"`, and the
fingerprint is labelled a content fingerprint rather than a signature.

**(3) Billing tiers** (`apply_tier`, following section twelve of the design): basic gives the conclusion and
severity; standard adds evidence; professional adds the reasoning path and threshold; audit adds confidence
and its basis, the professional insight, credentials, audit id, validity, content fingerprint, matched rules
and signal reasons. An unknown tier degrades to **basic** (give less rather than more) while an explicitly
invalid tier returns **422**. Tiers are a caller-side concept, so the interface does not show them — the
owner always sees the full package.

**(4) Feedback loop** (`confidence_from_feedback` plus
`POST /v1/scenario-definitions/{id}/feedback`): ten feedbacks reach `preliminary`, a hundred reach `stable`,
and fewer stay `unverified`; agreement is the share judged accurate; the result is written back to the
definition with a plain-language basis. The design's `certified` level requires third-party audit and is not
self-declared here.

**New `tests/test_package_and_feedback.py` (21/21)**: the four tiers' contents, unknown-tier degradation,
fingerprint reproducibility, the audit layer's insight/credentials/audit id/validity, 422 for invalid tiers
and invalid feedback, nine feedbacks still unverified, the tenth reaching preliminary, and the write-back
with its basis.

**Two mistakes this round, both recorded**: the tier lists **omitted `threshold`**, so trimming dropped it and
`test_skill_evaluate_api` failed — I changed an output shape without re-running the existing tests; and a test
password of seven characters was rejected by the eight-character rule.

All **26 suites green**; asset version → **20261004q**; **the backend was restarted, so another login is
needed.**

### Deploy and tests

### Fix (second attempt): the scenario-instance page still lacked the professional switch in daily mode

The user reported that the previous fix **did not take effect**. Investigation showed the page ids were
correct (`scenario-slices`, `scenario-instances`, `scenario-preview` all match the router), so my guess about
a wrong id was wrong, and although the router fallback did run against that list, the buttons still did not
appear.

**This round stops relying on the fallback**: the switch is now drawn **inside the daily instance renderer
itself**, in both of its `view.innerHTML` assignments (the empty state and the populated state), matching what
the preview page already did. The router fallback stays as a second line of defence.

**More importantly, the "structural assertion" I added last round was vacuous**: it looked for the daily
function by a name mapping (`renderProfessionalInstances -> renderInstances`) while the real name is
`renderScenarioInstances`, so it checked nothing and **always passed** — worse than having no test, because it
gave me false confidence. The criterion is now taken from the function body itself: any render function whose
body contains the professional-mode branch must also contain `proModeButtons()`, with an assertion that at
least three such renderers were inspected, so it can never go vacuous again.

**And it was verified in reverse**, which is the most important lesson here: removing the buttons from the
instance page makes the test fail with `['renderScenarioInstances']` (33/34), and restoring them passes
(34/34). The test genuinely catches this bug.

All **26 suites green**; front-end only, so **no restart and no re-login**; asset version → **20261004r** —
and please do a hard reload (`Cmd+Shift+R`), since a single-page app will not swap app.js without one.

### Deploy and tests

### Bringing (1)-(4) into the interface (they were backend-only and invisible)

The user asked where these were and could not find them — rightly so, because the insight field existed but
the package never displayed it, the audit id, validity, fingerprint and signature were computed but shown
nowhere, and tiers and feedback were API-only.

**This round adds the missing interface**: the Skill preview page gains a "which tier to deliver" selector
(audit / professional / standard / basic), passed as `tier` with the evaluation so the difference between
tiers is visible; a "delivery details for this call" block below the result showing the tier, professional
insight, credentials, audit id, valid-until, content fingerprint and an honest "digital signature: not
implemented yet"; and a "was this judgment accurate" block with accurate / not accurate buttons that call
`/feedback` and echo back the accumulated count, agreement rate and resulting confidence level — so the
feedback loop is clickable in the interface.

Four Chinese comments were converted to English to remove scanner noise, and 26 English entries were added,
leaving **56 uncovered against a baseline of 60**.

UI tests are at **37/37** (three new assertions: the delivery block renders, four tiers are selectable, the
feedback entry exists). All **26 suites green**; front-end only, so **no restart and no re-login**; asset
version → **20261004s**.

### Deploy and tests

### A visible build marker, to tell whether the browser is running stale assets

The user reported twice that the new interface was not visible, while each time I verified the server really
was serving the new files (`pro.js` with the delivery panel twice, `app.js` with the tier and feedback
controls four times, `no-store` in effect). Suspicion therefore moved to **the browser still running an old
app.js**, since a single-page app does not swap its assets on its own.

**The diagnostic added this round**: a fixed "界面版本 20261004t" marker in the bottom-right of the page. It
lives in the HTML shell, which is always `no-store`, so it necessarily reflects the server's current version.
If the marker shows an older version or is missing, the browser is serving cached assets, and that is visible
at a glance.

The manager test gained a self-check that the shell's marker matches the asset version, which would otherwise
indicate an unsynchronised deployment (this test failed before the deploy and passed after, because I ran it
first).

All **26 suites green**; asset version → **20261004t**.

### Deploy and tests

### A persistent save bar at the bottom, and relocating items (2)-(4)

Two pieces of user feedback: on the scenario-slice page, having selected a scenario that already has a
framework, edits could not be saved because no save button was visible; and a question about why items
(2)-(4) lived on the preview page.

**The save-button problem was my layout**: the only save button was at the **top** of the page while the
editing panels are below it, so after scrolling down to edit it was out of sight. There is now a
**persistent save bar at the bottom** ("changes are not saved automatically" plus the button), and the save
action is bound to **every** `[data-save-framework]` element, so both work.

**Items (2)-(4) moved**, following the table the user approved: the tier moved from a dropdown on the
preview page to a **default delivery tier** inside the delivery note on the **scenario-slice** page, which
the preview reads; feedback moved from two buttons on the preview to a **statistics-only** block on the
**scenario-instance** page, since feedback is submitted by the caller through the API; and the delivery
identity information is **no longer shown on the preview**, replaced by a line stating that this is a dry run
which records no decision and produces no audit id or digital signature. The reasoning is the user's own: a
dry run must not carry an audit id and signature, the tier is what the caller bought rather than something
the owner picks per run, and "was this accurate" is the caller's answer to give.

**Along the way**: the shell's build marker became the English `BUILD 20261004v`, since a version number
should not enter the translation dictionary where every release would need a new entry — a trap I set
myself last round; one Chinese comment became English and one placeholder became a bare number, leaving
**59 uncovered against a baseline of 60**.

UI tests are at **41/41**, including a **stale assertion** fixed (it still looked for the tier in its old
place) and four new ones: the bottom save bar, the preview no longer showing delivery identity, the tier
living on the slice page, and the instance-page statistics.

All **26 suites green**; front-end only, so **no restart and no re-login**; asset version → **20261004v**.

**Still outstanding, stated plainly**: the **decision-record page** does not yet show each real decision's
delivery identity (audit id, expiry, fingerprint, signature) — it is currently only in the API response.

### Deploy and tests

### Billing: the four tier prices are entered by the user, plus a billing demo

The user clarified that prices are entered by the end user in the interface, not supplied during development.

**The scenario-slice page's delivery note gained a pricing area**: a billing mode (per call or monthly) and a
unit price for each of the four tiers, left blank meaning "not priced yet" and editable at any time. It is
stored in `boundaries.pricing`, so **no backend change and no restart** are needed.

**The scenario-instance page gained a billing demo**, matching the earlier agreement that billing would be
demonstrative first: choose a tier, press "simulate one call", and it shows the amount due, the unit and an
example caller, or states that the tier has no price yet. It is explicitly labelled demo data that records
nothing and produces no real invoice. The button is handled by **event delegation** rather than by inserting a
handler into the long template, which is the trap hit in earlier rounds.

The `billing` field in the audit log (section eight of the design) stays deferred to the network stage, since
adding it now would be billing a dry run — the same class of mistake the user pointed out before.

**Two mistakes this round, both recorded**: the delegation listener **missed its closing brace** and broke
app.js's syntax, repaired with git and redone correctly — the lesson being to run `node --check` immediately,
and, worse, that three suites were "green" at the time because they read app.js as **text** and never execute
it, which is a genuine blind spot. Second, in the previous command a failing `node --check` broke the `&&`
chain so **the i18n insert never ran**, and I failed to notice the missing line in the output, which is why the
uncovered count would not fall; it is now added.

All **26 suites green**; asset version → **20261004w**; front-end only, so no restart and no re-login.

### Deploy and tests

### First cut: the personal judgment asset moves to the **slice** layer

Following the layering the user confirmed, this round lands the **data model** part.

Recap of the problem: I had attached the skill framework to `scenario-definitions` (the shareable layer)
while the design puts it on `scenario-slices` (the personal layer) — which is exactly why the user could not
see a draft list.

**Change in `backend/model.py`**: slices gain **ten fields** — `framework`, `boundaries`, `insight`,
`owner_credentials`, `valid_days`, `confidence`, `confidence_status`, `confidence_basis`, `feedback_total`
and `feedback_accurate` — with predicates such as `sliceFramework`, deliberately distinct from the
definition layer's `skillFramework`, so the two never overwrite each other.

**New `tests/test_slice_framework.py` (9/9)**: slices carry every personal-asset field; the framework
predicates differ between layers; the definition's field count is untouched; a personal slice with a
framework can be created and its framework, boundaries and insight read back; **one scenario definition can
carry several slices** (an internet edition and a manufacturing edition); and the definition layer is not
overwritten by a slice's framework, so the two stay cleanly separated.

**Method, and the lesson**: my previous two attempts broke `model.py` because I performed in-line string
surgery on a large file and validated only at the end. This time the candidate was written to a temporary
file, compiled, imported as a module for structural validation, and only then moved into place — and for a
dictionary I **appended** (`FIELDS[...].update(...)`) rather than performing surgery. The first append
tripped on my own over-strict check (it flagged predicates that are legitimately reused across collections),
and because the assertion fired before writing, the file was unharmed; after correcting the check it passed
first time.

**Stated plainly**: this round covers **only the data model**; the interface and the judgment endpoints do
not yet take the framework from the slice, so the interface looks unchanged. Next is wiring the five
judgment endpoints to `slice_id`, turning the slice page into a two-level "choose a scenario template, then
choose or create my slice" interface, and migrating the existing framework automatically.

All **27 suites green**; the model change coexists safely without a restart.

### Deploy and tests

### Second cut: judgment endpoints become slice-scoped, with one-click migration

**Six new slice-layer endpoints**: evaluate, draft, backtest, judgment-feedback and authorize all scoped to
`/v1/scenario-slices/{slice_id}/…`, plus `migrate-from-definitions`. The definition-layer endpoints are
unchanged and remain for templates and backwards compatibility.

**Migration** creates a slice for every definition that has a framework but no slice carrying one, moves the
framework, boundaries, insight, credentials, validity and confidence onto it, and then **clears those personal
fields from the definition** so the shareable layer stays clean. Built-in definitions have no framework and
are untouched.

**New `tests/test_slice_api.py` (18/18)**: judgment reads the slice's framework, returns slice_id and source
definition, takes the default tier from the slice's boundaries, authorises against the slice's boundaries
(over-limit becomes confirm), writes backtest and feedback results to the slice, and the migration creates,
moves, clears and is idempotent on a second call.

**Two real bugs fixed this round**: `slice_id` was being dropped by the tier filter because the `ALWAYS`
whitelist lacked it; and the slice feedback route was **shadowed** by the pre-existing daily route
`/v1/scenario-slices/{id}/feedback`, which FastAPI matches first, so the new endpoint never ran — it now lives
at `/judgment-feedback`. The lesson, caught here by a test, is to check for an existing path of the same shape
before adding a route.

**One assertion of mine was wrong while the code was right**: the `professional` tier deliberately does not
include credentials or an audit id, since the design places those in the audit tier; the assertion now reads
them from the audit tier, with an extra assertion pinning that rule.

**Stated plainly**: the interface is **not yet** the two-level selector (scenario template, then my slice), so
what you see is unchanged; that plus slice-scoped preview is next.

All **28 suites green**.

### Deploy and tests

### Third cut: the interface becomes a two-level choice of scenario (template) and my slice (personal asset)

**The slice page (`pro.js`) is now a two-level selector**, with the relationship spelled out as the user
asked: a scenario is a shared template carrying none of your judgment, while a slice is your personal
judgment asset, and one scenario can carry several slices (an internet edition, a manufacturing edition).
The page shows a scenario picker and, beneath it, my slices with their state (framework present, confidence),
plus a box and button to create a new slice, and a line stating that both saving and drafting write to the
currently selected slice. On load it calls the **idempotent migration**, so the framework previously attached
to a definition moves onto a slice automatically; saving, drafting, boundaries, pricing, insight, credentials
and validity all read from and write to the slice.

**The preview page (`app.js`) now judges by slice**: its list is the professional slices and all five
endpoints point at `/v1/scenario-slices/{slice_id}/…`, with feedback on `/judgment-feedback`.

**The method finally held**: read the real text first, replace whole functions by their boundaries
(`renderSlices`, lines 285–329) rather than guessing scattered anchors, and validate a candidate file with
`node --check` before replacing it — four front-end edits passed first time.

**Test problems fixed this round, all my own over-narrow assertions**: the version assertion hard-coded a date
and now compares dynamically against the workspace `index.html` (which doubles as a deployment self-check);
the "saves to the slice" assertion checked negatively for the definition path, which is legitimately used for
creating and deleting scenarios, and now checks positively; and the preview assertion depended on a Chinese
comment I had just replaced, so it now checks the endpoint and data source.

Three UI assertions added, three stale ones corrected; **58 uncovered against a baseline of 60**; the backend
was restarted with all six slice routes registered; all **28 suites green**; asset version → **20261005a**.

### Deploy and tests

### "Delivery and feedback" promoted to a top-level menu page, placed below "Skill preview"

The user pointed out that the billing demo did not belong on the scenario-instance page and proposed a better
structure directly.

**Changes**: `web/index.html` gains a sidebar entry "对外交付与反馈" immediately after "场景预演"; `app.js`
adds a `delivery` branch to the router and to the mode-switch fallback list, and a new `renderDelivery(view)`
showing a table of my slices (slice, scenario, default tier, **tier pricing**, caller feedback, confidence),
a **billing demo** (choose a slice and tier, simulate one call, see the amount due from your own prices), and
a note on what a real call carries. The old "delivery and caller feedback" block is **removed from the
scenario-instance page** so it is not duplicated, and in daily mode the page shows a friendly empty state with
the mode switch.

**This also answers the A/B question I asked earlier**: with a dedicated page, the billing demo travels with
it instead of being squeezed onto an "enabled state" page that is about what the judgment looks like
externally, not about money.

The method held again: read the real text, validate a candidate with `node --check`, then replace — passing
first time. The assertions were updated in step, since moving the block necessarily invalidated the old one.

**57 uncovered against a baseline of 60**, having removed one more Chinese comment; UI tests **48/48**; all
**28 suites green**; front-end only, so **no restart and no re-login**.

### Deploy and tests

### A + B: decision records show delivery identity, and front-end syntax checking joins the tests

**B first (small)**: a new `tests/test_frontend_syntax.py` (7/7) runs `node --check` over every `web/*.js`
and verifies that every script the shell references exists — closing the blind spot where, on 2026-10-04, I
broke app.js's syntax and three "green" UI suites never noticed because they only read app.js as text.

**A (decision records showing delivery identity)** surfaced a key fact: the judgment package was **never
recorded at all** — `/evaluate` is a dry run and by design writes nothing — so the decision-records page had
no professional deliveries to show. The distinction was therefore built first: a new
`/v1/scenario-slices/{id}/deliver` judges and **writes a decision record** carrying the audit id, expiry,
content fingerprint and signature status as a snapshot in the record's `reason_params`. The interface gained a
"create a formal delivery" action on the Delivery and feedback page, and the **Decision records** page now
shows a table of deliveries: time, slice, conclusion, severity, tier, **audit id**, **valid until**,
**content fingerprint** and **digital signature**.

**Four real problems hit and fixed, all recorded**: `decisions.phase` is SHACL-constrained to
`pre_planning`/`pre_execution`; a decision requires exactly one `result_id` (using `allow`, with the real
conclusion in `reason_display`); `cited_assertions` is typed as a dateTime and rejected the audit id, so that
field was dropped; and I was **shadowed by a generic collection route once more** — `GET /v1/deliveries`
collides with `/v1/{collection}` — so the listing now filters the existing `GET /v1/decisions`, adding no
route at all. The `/feedback` shadowing was the same class of bug I had literally just written the lesson
for, and this is its third recording.

**One judgement of mine was wrong and is corrected**: I said the app had no decision-records page; it already
had one (sidebar line 31). My added menu duplicated it, so mine is removed and the original kept, while my new
`renderDecisions` still takes over that page id.

Five new assertions in total; all **29 suites green**; 60 uncovered, level with the baseline; **the backend
was restarted, so one more login is needed.**

### Deploy and tests

### The slice page gains a "my slices" list (answering "where is the draft list")

The user asked why the three built-in scenarios plus one with a framework showed no draft list, and why the
scenario-instance list did not contain them either.

**What is actually going on (not a bug, but my interface failing to explain, plus a missing list)**: the three
built-ins (acquisition assessment, labour compliance, contract review) are **scenario templates** — shared and
carrying nobody's judgment — so **they have no drafts by nature**; the drafts (slices) are what you create. The
one "with a framework" is a **slice migrated** from a definition. In professional mode I had turned slices into
a **dropdown** rather than a list, and the **scenario-instance** page lists **enabled judgment entries**
(optional fine-grained `knowledge-entries`), not slices.

**This round adds a "my slices" list** on the slice page, above the editor, with columns for name, framework
present or not, confidence, pricing (how many tiers set) and actions (select, delete), and an empty state that
says plainly: this scenario has no slice of yours yet — start one with New slice above; a scenario is only a
shared template and your judgment lives in the slice. That answers the question directly.

**On i18n**, this time both the **runtime full text** (the node after JS string concatenation) and the
scanner's split fragments were added, since patching only the fragments — a trap I have hit repeatedly — makes
the metric pass while the interface stays untranslated.

**60 uncovered, level with the baseline**; UI tests **53/53**; asset version → **20261005b**; front-end only,
so **no restart and no re-login**.

### Deploy and tests

### Line-based input format: the parser is done (lawyers do not write JSON)

The user pointed out that a lawyer will not write JSON but is far more likely to type **one line at a time**,
so converting JSON is of little value, and asked whether the import format needs to be explained. It does,
and the format belongs **next to the input box**.

**This round tackles the hard part: the line parser** — a new, self-contained `backend/line_format.py`
(249 lines) touching no existing file. It supports six inputs, all in plain Chinese phrases with no quotes and
no nesting: field definitions (`市盈率 ｜ 数字`), the baseline and its adjustments
(`监管环境=收紧 → -0.10`), named signals (`市盈率超阈值 = 市盈率 大于 行业平均市盈率 × 基准线`), combined
judgments (`… 且 … → 估值偏高（高）`), exceptions (`… → 团队流失权重 ×0.5` or `直接判 估值偏高`) and priority
(`A > B > C`). It tolerates full-width or half-width separators, Chinese or Latin punctuation, stray spaces,
`#` comments and blank lines, and **a bad line only affects that line**: the parser returns a per-line report
with line number, original text and reason while importing the rest.

**New `tests/test_line_format.py` (17/17)**, whose most important check is the closed loop: Zhang's M&A
valuation framework written **one line at a time**, parsed, then judged — yielding 估值偏高 / 高 / threshold
1.45 / 45 > 30×1.45=43.5 / no exception triggered, **exactly matching the design document**. That proves the
line format can carry the design.

**A real parser defect was found and fixed**: the priority separator `>` also appears inside signal names such
as `客户集中度>70`, which split them wrongly; the separator now requires spaces around it, with a clear error
message otherwise.

**Next, the interface**, following the confirmed plan: a small per-part line box with the format shown inside,
plus a paste box that treats content starting with `{` as JSON and everything else as lines, showing a preview
and report before confirming, and storing the pasted original in `framework.source` so nothing is lost.

### Deploy and tests

### Fix: content in the line boxes was not saved (my two-button dependency was designed wrong)

The user reported pasting content, pressing Save my framework, seeing the slice appear in the list, and then
finding nothing displayed when selecting it.

**Cause**: Save my framework reads only the panels below and **not** the line boxes, so saving without first
pressing Import into the panels stored an **empty framework** — hence a slice that "exists" but opens empty.
**The root cause is my design**: the dependency between those two buttons should not be something the user has
to remember.

**Two fixes**: Save my framework now imports the line boxes first and then saves (calling import-lines with
save, then storing boundaries and the delivery note), and any unparsed lines are surfaced explicitly with line
number and reason instead of being silently dropped. Second, an empty framework no longer reads as
"framework configured" — a bug I had promised to fix earlier and missed: a new `hasFramework()` treats a
framework as configured only when some part actually has content, matching exactly the "exists but opens
empty" symptom.

UI tests **56/56**; all **31 suites green**; front-end only, so **no restart and no re-login**.

### Deploy and tests
