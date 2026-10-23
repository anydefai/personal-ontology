# Circles and Profile Items: Schema and Migration (v0.1, English)

> English counterpart of `docs/07-circles-and-profile-items-design.md`. Structure follows the Chinese
> version; long prose is condensed, all decisions and field lists are complete.
> Scope: extend the personal ontology from "scenes and rules" to "first-principles things about a
> person", and fix two structural defects.

## 0. Goals

- Let authorization target a **circle** (a group of people), not only an individual.
- Split profile data into **per-item nodes**, so each item can be authorized and audited separately.
- Bring data that currently sits in plaintext files (agent clients) into the encrypted ontology.
- Model the remaining categories (commitments, places, assets, reputation) without building UI yet.

## 1. Conventions

All new collections share: `display_name_zh`, `display_name_en`, `note`, `source`, `sensitivity`,
`created_at`, `updated_at`. Primary keys follow `ID_FIELDS`; collection → class follows `CLASSES`;
field → predicate follows `FIELDS`.

> Rule learned the hard way: **use class-specific predicates** for new classes. `po:updatedAt` carries
> `rdfs:domain po:ScenarioSlice`, so any node written with `updated_at` is inferred to be a scene slice
> and then fails the ScenarioSlice SHACL shape.

## 2. Nine new collections

### 1. `circles`
`circle_id`* · `display_name_zh`* · `circle_type`* (family/friend/work/class/service/org/other) ·
`my_role` (my role inside this circle) · `sensitivity` · `default_grant_note`

### 2. `circle-members`
`member_id`* · `circle_id`* (→circles) · `principal_id` (→principals) · `contact_ref` (→contacts) ·
`display_name_zh`* · `member_role` · `strength` (close/normal/distant) · `last_interaction_at` ·
`source`

**Rule:** store the relationship only — never the other person's ID numbers, address, or family.

### 3. `profile-items`
`item_id`* · `profile_id`* (→profiles) · `field_key`* · `label_zh`* · `value` · `kind`
(text/phone/id/date/bool) · `sensitivity` (normal/sensitive/**critical** for IDs) · `verified` ·
`verified_at` · `last_used_at`

### 4. `commitments`
`commitment_id`* · `title`* · `kind`* (appointment/deadline/contract/warranty/renewal/promise) ·
`counterparty_kind` (principal/circle/external) · `counterparty_ref` · `start_at` · `due_at` ·
`status` (pending/done/expired/cancelled) · `remind_before_days` · `sensitivity`

### 5. `places`
`place_id`* · `label_zh`* · `kind`* (home/work/family/frequent/travel) · `address_text` ·
`geo` (optional, not collected by default) · `radius_m` · `sensitivity` (default sensitive)

### 6. `assets`
`asset_id`* · `label_zh`* · `kind`* (account/property/vehicle/insurance/subscription/debt/tax) ·
`identifier_masked` (**masked only**, e.g. `**** 1234`) · `value_summary` (range or summary) ·
`expires_at` · `custodian` · `sensitivity` (default restricted)

### 7. `asset-transactions` (ledger section — decided: store detail)
`transaction_id`* · `asset_id`* · `occurred_at`* · `amount`* · `direction` · `counterparty` ·
`category` · `summary` · `balance_after` · `source` · `sensitivity` (restricted, never exported)

Boundary: transactions live in a **separate encrypted section** (`ledger`), never in the main graph,
never in any outward authorization.

### 8. `devices`
`device_id`* · `label_zh`* · `kind`* (phone/computer/tablet/vehicle/home/wearable/**agent**) ·
`agent_client_id` · `trust_level` (trusted/limited/blocked) · `last_seen_at` · `capabilities`

### 9. `reputation`
`item_id`* · `kind`* (profile_public/publication/citation/review/credential) · `title`* · `venue` ·
`at` · `url` · `visibility`

## 3. Three extensions to existing collections

| Extension | Meaning | Compatibility |
|---|---|---|
| `authorizations.grantee_kind` | `principal` (default) / `circle` | old rows default to principal on read |
| `contacts.owner_profile` | which profile this contact belongs to | nullable |
| principal ↔ circle | resolved via `circle-members`, no duplicated field | avoids double writes |

## 4. Relationship map

```
profiles ──┬── profile-items ──┬── contacts (owner_profile)
           │                   └── referenced by scene "prefill"
           └── principal_id → principals

circles ──── circle-members ──┬── principals
                              └── contacts

authorizations ── grantor → principals
               └─ grantee → principals | circles (grantee_kind)

commitments ── counterparty → circles | principals
devices ────── agent_client_id → agent clients (migrated into the ontology)
```

## 5. Migration A: `profiles.items` → `profile-items`

1. Add the collection (CLASSES / FIELDS / ID_FIELDS) and an assertion that all three are registered.
2. One-shot, idempotent migration: for each profile item create a node
   (`profile_id`, `field_key` derived from keywords: 姓名→name, 证件→id_no, 手机→phone,
   邮箱→email, 地址→address, else `field_<n>`), copy value/kind/verified, IDs default to `critical`.
3. Keep `profiles.items` untouched (rollback = delete the `profile-items` collection).
4. Switch reads to the new collection; keep a read-only fallback to the old array.

Acceptance: item count and values identical before/after; idempotent on re-run; per-item read works.

## 6. Migration B: circles and circle-scoped authorization

1. Add `circles`, `circle-members`, `authorizations.grantee_kind`.
2. Creating a circle also creates a **group principal** with the same id — required because
   `po:grantee` has `rdfs:range po:Principal`; without it the write fails SHACL.
3. Engine change: when evaluating, add the caller's circles to the ancestor set, so a rule whose
   `grantee_id` is a circle id matches all members. Rule format unchanged, old data unchanged.
4. Deleting a circle: refuse with 409 if any rule still points at it; otherwise delete members,
   the circle, and its group principal.
5. Audit: member add/remove writes a change record and reports the number of affected rules.

Acceptance: member allowed, outsider denied, removal takes effect immediately, deletion guarded.

## 7. Gap fixed along the way: agent clients into the ontology

`data/agent-clients.json` is plaintext. `devices` mirrors its **metadata only** (name, state,
scopes, timestamps); secrets stay in the original file. Authentication path unchanged.

## 8. Order and cost

| # | Change | Files | Est. |
|---|---|---|---|
| 1 | `profile-items` + migration | model, api, app.js | 1 d |
| 2 | `circles` + circle grants | model, api, store.evaluate, app.js | 2 d |
| 3 | `devices` mirror | model, api, app.js | 0.5 d |
| 4 | `commitments` / `places` | model, api, app.js | 1.5 d |
| 5 | `assets` + ledger UI / `reputation` | model, api, app.js | 1 d + 1 d |

Each collection is ~30 lines of modelling; a SHACL shape adds ~10 more.

## 9. Decisions (locked, Oct 2026)

| # | Question | Decision |
|---|---|---|
| 1 | Can a principal be in several circles? | **Yes** (many-to-many) |
| 2 | Does a circle inherit sub-circles? | **No** (keeps inference simple) |
| 3 | Default sensitivity for ID items? | **critical** |
| 4 | Import contacts' notes? | **Yes** (see exception below) |
| 5 | Store transaction detail? | **Yes** (`asset-transactions`) |

Still open (non-blocking): transaction retention policy; whether notes influence relationship strength
(recommended: no).

## 10. Costs we accepted

**Cost 1 — notes bring third-party privacy into the ontology.** Mitigation: `restricted`, never
authorized, excluded from export, deletable per row, global switch to skip notes on import.

**Cost 2 — transaction volume.** One person's 1–3k rows/year; the whole-graph + full SHACL rewrite
would slow down. Mitigation: a **separate encrypted section** (`ledger`); writing transactions
rewrites only that section, verified by a byte-for-byte comparison of the ontology section.

## 11. Acceptance tests to add

- `test_profile_items`: counts/values identical, idempotent, per-item CRUD.
- `test_circle_grants`: member allowed, outsider denied, removal effective, guarded deletion.
- `test_devices_sync`: metadata mirrored, secrets absent, auth path untouched.
- Existing suites must not regress (model changes affect SHACL — run shapes first).
