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
