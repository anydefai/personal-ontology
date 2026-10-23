# UI Design: From "Scene Tool" to "Personal Ontology" (v0.2, English)

> English counterpart of `docs/08-ui-design.md`. This version reflects **what was actually built**
> (BUILD 20261012H) and marks every deviation from the original v0.1 design.

## 1. Information architecture: two groups, 11 entries

```
My world
  Overview · Me · Circles · Commitments · Places · Assets · Knowledge

Rules & capabilities
  Boundaries · Devices · Scenes · Records
```

(Implementation note: the sidebar keeps the existing scene pages as separate entries rather than
folding them into a single "Scenes" entry; the group headers are `我的世界` / `规则与能力`.)

Old-menu mapping: Principals → merged into Circles/Devices; Personal profile → Me; scene pages and
delivery → under Rules & capabilities; decision records → Records; account security → avatar menu.

## 2. Three global interaction rules

1. **Mask first.** Profile items, asset identifiers and contact values are masked by default; viewing
   plaintext requires a confirmation step.
2. **Every action leaves a trace.** Authorizations, views, exports and edits are recorded, with a
   visible entry point ("who has seen this").
3. **Refusals must explain themselves.** Any "no" names the rule, the circle, and the field involved.

## 3. Shared list-page skeleton

Title + one-line subtitle + primary action; card per record showing only the five facts needed to
decide; empty state that tells the user what to do first; no fabricated demo data.

## 4. Circles

- List: name, type badge, sensitivity badge, member count, my role, one-line default boundary.
- Detail: rename/default-boundary editor, member table (relationship only: role, strength, last
  interaction), add-member form, remove-member with a confirmation that states the consequence.
- Circle-scoped grants are described in the detail page; enforcement lives in the engine (a rule whose
  `grantee_id` is a circle id matches every member).

**Deviation from v0.1:** the "change log" tab is still plain text, not a rendered history.

## 5. Me (profile items)

- One card per profile, masked summary, then a per-item list: name, masked value, sensitivity,
  verified badge, field key, [view] and [delete].
- [view] opens the app modal: first "this view will be recorded", then the plaintext plus
  "recorded · view #N" (or an explicit "recording failed").
- [delete] removes a single field; deleting the profile itself cascades its items.

## 6. Assets and the ledger

- Assets: cards with kind badge, masked identifier, custodian, value summary, expiry badge.
- Transactions: a section below the assets list showing totals, the latest 20 rows, amount colouring,
  and a "record one" modal. Transactions live in a separate encrypted section (`ledger`) and are
  explicitly marked as never authorized outward.

**Deviation from v0.1:** transactions are a section on the same page, not a tab; there is no
password prompt to open them (per decision 3).

## 7. Boundaries (界)

Read-only overview: four stat cards (active / draft / paused / revoked, with "how many are
circle-scoped") and grouped rule lists showing recipient (circle vs individual), effect, status,
resource, actions, condition count, source, revocation state.

**Deviation from v0.1:** enabling/pausing still happens on the scene pages; this page is a console,
not an editor.

## 8. Devices (器)

Lists devices and agents from the ontology (name, kind, trust badge, state, last seen, scopes) with a
"sync from client list" action. The sync mirrors metadata only; secrets stay in the original file.

## 9. Small screens

Deferred by decision 4. The design intent is bottom tabs (Overview / Me / Circles / Boundaries / More)
and two-line cards instead of tables.

## 10. Empty states, loading, errors

| Situation | Message / action |
|---|---|
| No circles | "No circles yet. Create 'Family' first, then add people." |
| No profile items | "No per-item data yet. Use 'Split into items'." |
| No transactions | "No transactions yet. Pick a few rows from a bank statement." |
| Loading | skeleton cards, no spinners |
| Write rejected | "Validation failed: <specific attribute and reason>" (parsed from the SHACL report) |
| Forbidden | "Blocked by the 'Work' circle boundary: contacts may not be read." |

## 11. Build status at BUILD 20261012H

Built and wired to the backend: Me, Circles (incl. circle-scoped authorization), Commitments, Places,
Assets (incl. ledger), Knowledge, Boundaries, Devices. 18 backend suites + UI 26/26 + frontend syntax
10/10 pass before every deploy.

Outstanding: 6 native `confirm` dialogs, circle change-log rendering, mobile adaptation for the four
personal pages, English version of the metamodel doc set.

## 12. Decisions (locked)

| # | Question | Decision |
|---|---|---|
| 1 | Are 11 entries too many? | No |
| 2 | Principals as a first-level menu? | Remove; merge into circles/devices |
| 3 | Password prompt for the ledger? | No; already encrypted, just collapsed |
| 4 | Mobile in phase 1? | Later |
