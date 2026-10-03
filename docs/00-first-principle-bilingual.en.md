# First principle: full-stack bilingual (Chinese + English)

> **This principle takes precedence over every other design trade-off.** Any new artefact that
> lacks the other language is considered **unfinished**.

## 1. The principle

**Every artefact that faces a user or a maintainer** must exist in both Chinese and English, and
must be **complete, usable and unmixed** in each. Not just page text, but:

interface text, backend messages, data labels and object names, scenario-analysis output,
installation manual, user manual, design documents and the changelog.

## 2. Per-layer requirements and mechanisms

| Layer | Requirement | Mechanism | Executable check |
|---|---|---|---|
| **Interface text** | No Chinese characters appear in English mode | `DICT` + `RULES` in `web/i18n.js` (five forms covered: icon prefixes, suffix markers, embedded numbers/indices, mixed English+Chinese single strings, attributes) | `tests/test_i18n_coverage.py` (baseline may not rise), `test_i18n_text.py`, `test_i18n_rules.py` |
| **Backend messages** | HTTP errors and notices follow the request language | A message catalog (key → zh/en) selected by `X-Display-Language` | `tests/test_messages_bilingual.py` |
| **Data labels / object names** | Principals, resource types, actions and field labels are bilingual | Paired metamodel fields `*_zh` / `*_en`, selected at read time (`_localize_scene_labels`, `SCOPES_EN`) | `tests/test_label_localization.py` |
| **Scenario-analysis output** | The model produces the language it analysed in; known fields are localised at read time | Prompt `{LANG_LABEL}`; `field_names.default_label(name, language)` at read time | `tests/test_label_localization.py` |
| **Documents** | Every document has both versions | A sibling file `docs/NN-name.en.md` (existing Chinese files need no renaming); paired `.zh.md`/`.en.md` is also accepted | `tests/test_bilingual_coverage.py` |
| **README / install / user manuals** | Both versions | Sibling files such as `README.en.md` (README done) | `tests/test_bilingual_coverage.py` |
| **Changelog** | Every change recorded in both | `CHANGELOG.en.md` (**covers 2026-10-02 onwards**; earlier entries are Chinese-only and this is stated in the file) | `tests/test_bilingual_coverage.py` |

### Exceptions (stated explicitly, to avoid an endless obligation)

- **User-authored content is not translated**: descriptions, notes and custom names typed by the
  user are kept in the language the user wrote. **System-generated** content must be bilingual;
  user-**entered** content is not required to be.
- **Code comments and internal identifiers**: implementation details, not required to be bilingual
  (design documents are).
- **Machine keys** (such as `check_in_date`) are always English and are never translated — an
  existing convention.
- **Long documents may be translated in rounds, but must be marked**: put a `BILINGUAL-PARTIAL`
  comment at the top of the file stating which sections are done. The inventory recognises the
  marker and **still counts the document as a gap**, so a file that exists but is incomplete is never
  treated as covered.
- **Frozen test vectors and machine data are not translated**: for example the test-vector
  plaintext in `docs/05` §3.5 (`测试向量：…`) — it is **input bytes**, and translating it would make
  implementations produce different ciphertexts. Such content must be copied verbatim in documents,
  with the reason stated.
- **Tool-generated lists and indexes are not translated** (such as `docs/i18n-pending.md`): they are
  scan output serving maintainers, and having one per language would defeat their purpose. The
  exemption list is `EXEMPT_DOCS` in `tests/test_bilingual_coverage.py`.

## 3. Implementation disciplines (lessons paid for in blood)

1. **Verify against what the server actually serves, not the workspace file.** Two layers sit in
   between: file synchronisation and browser caching. Any frontend change must be verified with
   `curl http://127.0.0.1:8765/assets/... | grep <marker>`.
2. **Bump the asset version on every frontend change** (the `?v=` in `web/index.html`). Otherwise
   the browser keeps using the old file and the change appears not to exist.
3. **Do not validate with a hand-written parser.** Evaluate the dictionary and rules with real Node
   execution (`window.PO_I18N_EN`), not brace counting — the latter does not understand regex
   character classes and has produced wrong conclusions twice in this project.
4. **Make idempotency checks specific to the artefact.** A generic substring test for "does this
   already exist" caused a write to be skipped while the script still reported success.
5. **Locate localization problems by checking the language resolution chain first.** A wrong
   precedence in `config.display_language` silently disabled every downstream localization; adding
   dictionary entries one by one only treats symptoms.
6. **Report residual Chinese at the level of the whole line.** The DOM often merges fragments into
   one text node, so adding entries per keyword frequently fails to match the actual string.

## 4. Status (2026-10-02)

| Layer | Status |
|---|---|
| Interface text | 🟡 Mechanism complete, 200+ historical gaps filled; a few interpolated/long strings remain (see `docs/i18n-pending.md`) |
| Data labels / object names | 🟢 Implemented (top-level and segmentation preferences, field labels, authorization scope labels) |
| Scenario-analysis output | 🟢 Model output follows the analysis language; localised at read time |
| Backend messages | 🟢 **Complete**: `backend/messages.py` plus exception-handler resolution, all 66 sites converted |
| Design documents | 🟡 `docs/06`, `07`, `09` and this document have English versions; 6 remain |
| README / install / user manuals | 🟢 `README.en.md` complete |
| Changelog | 🟢 `CHANGELOG.en.md` from 2026-10-02 onwards |
| Coverage defences | 🟢 `tests/test_bilingual_coverage.py` inventories the whole stack; the baseline may only decrease |

## 5. Current gap (measured by `tests/test_bilingual_coverage.py`)

```
Backend messages containing Chinese:        0
Contract-note messages (user visible):      0
Design documents missing English:           0
README missing English:                     0
Changelog missing English:                  0
──────────────────────────────────────────────
Total gap                                   0  (achieved)
```

Run that test after every change: if the gap rises, the change is missing a language and the test
fails. Driving the gap to 0 completes this principle.

## 6. Relationship to other documents

- This document is the **first principle** and outranks specific design trade-offs.
- Implementation details of each layer live in `docs/09-scenario-analysis-schema.md` (the data
  contract) and in the header comment of `web/i18n.js` (the interface translation mechanism).

## 7. Newly discovered and recorded debt: contract-note messages

While writing the English `docs/09` it emerged that `contract_notes[].message` in
`backend/analysis_contract.py` — **visible to users** through the "N contract notes" badge — was
Chinese-only (~13 items) and was not covered by any inventory. It was therefore recorded as
**newly counted debt**, not a regression.

**Resolved (round 10)**: `note()` now carries only the **message key (the code) plus params**, with
the text back in `backend/messages.py`. `note()` still writes a Chinese `message` for compatibility
with read paths that are not localised, and `_localize_scene_labels()` replaces `message` at read
time according to the display language. Verified: English renders correctly with parameters.
