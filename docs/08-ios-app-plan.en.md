# iOS app implementation plan (native Swift, fully on-device)

Status: direction decided, work not started
Goal: run the ontology **standalone** on iPhone / iPad (no dependency on a running Mac), iOS 18.7+
Constraints: **zero third-party runtime dependencies**; an independent data copy, moved by manual
export/import

## 1. The three decisions taken

| Decision | Content | Impact |
|---|---|---|
| Form | **B: native Swift, fully on-device** (the engine runs on the phone) | 4,665 lines of Python backend must be rewritten layer by layer |
| Data | **An independent copy on the phone**, the container moved by hand via AirDrop / the Files app | **No sync protocol and no conflicts**; the container is ciphertext, so transferring it *is* encrypting it |
| Dependencies | **Zero third-party at runtime** (system frameworks only) | Rules out embedding CPython; the Turtle subset must be hand-written |

## 2. Architecture mapping (Python → Swift)

| Existing module | Lines | iOS counterpart | Notes |
|---|---|---|---|
| `vault.py` | 315 | `ContainerCrypto.swift` | CryptoKit `AES.GCM` + CommonCrypto `CCKeyDerivationPBKDF` |
| `model.py` | 134 | `OntologyModel.swift` | 13 collections, field-type mapping |
| `store.py` | 541 | `GraphStore.swift` + `DecisionEngine.swift` | Graph read/write + decision engine (default deny, deny>ask>allow, redlines, risk gate) |
| `field_names.py` | 549 | `FieldNaming.swift` | English machine keys + bilingual display names + alias normalisation |
| `scenario_llm.py` | 225 | `ScenarioAnalyzer.swift` | `URLSession` against an OpenAI-compatible endpoint, no SDK |
| `api.py` (business part) | 1510 | `Services.swift` + `LocalServer.swift` | Entity CRUD, scenario confirmation, rule compilation, decision auditing |
| `api.py` (auth/session) | — | simplified | Single machine, single user: unlocking *is* the session; no tokens or session table |
| `manager.py` / `agent_gateway.py` / `peercred.py` / `agent_access.py` | 828 | **not ported** | See §6: on iOS, App Intents replace MCP |
| `web/*` (app.js/app.css/i18n.js/index.html, 188 KB) | — | **reused as is** | Hosted in WKWebView pointing at the local loopback service; **zero UI rewrite** |
| `ontology/*.ttl` | 273 | bundled resources | Metamodel + SHACL subset rules |

## 3. Phased tasks and acceptance criteria

### P0 Encrypted container (1–2 weeks) — **the go/no-go gate**
- Read `format/version/sections` and decrypt with `AAD = po-container-v1|section|version|salt|iterations|nonce`
- Write back via "temporary file + replace", preserving atomicity
- **Acceptance**: using the frozen test vectors in `docs/05` §3.5, produce **byte-identical**
  ciphertext on a real device
- **Tests**: a wrong passphrase is rejected; section independence (changing one does not affect the
  other); a version mismatch errors out rather than being misread
- **Stop if it cannot pass**: that means the format still has ambiguities and the Mac side must
  clarify them first

### P1 Canonical Turtle subset (1–2 weeks)
- Support only the constructs **we serialise ourselves**: prefixes, IRIs, string/number/boolean/date
  literals, `rdf:type`, JSON literals, multi-valued properties
- **Acceptance**: unpack a container exported from the Mac and **compare triple by triple** after
  parsing (the same approach as the migration script's checks)
- **Tests**: round-trip identity (parse → write → parse again, equal sets)

### P2 Domain model + validation (2–3 weeks)
- Swift models for the 13 collections; the field-naming contract (including bilingual display names
  and alias normalisation)
- SHACL subset validation: `sh:property` / `sh:path` / `sh:minCount` / `sh:maxCount` / `sh:datatype`
  / `sh:in` / `sh:nodeKind`
- **Acceptance**: the same conclusion for each of the 6 test cases on the Mac side
- **Tests**: deleting a referenced node must fail; a missing required field must fail

### P3 Decision engine (1–2 weeks)
- Default deny; deny > ask > allow; redlines first; principal inheritance; matcher allowlist (regex
  disabled)
- Constraint types: `context_equals` / `numeric_lte` / `numeric_gte` / `context_exists` /
  `source_trust_min` / `temporal_lte` / `temporal_gte`
- Temporal parsing in both languages (`15:00` / `下午3点` / `3 PM` / `Oct 10, 2026` /
  `2026年10月10日`), and **ambiguity is never guessed**
- **Acceptance**: all 50 assertions in `tests/test_temporal.py` pass on the Swift side
- **Tests**: a missing required field never reaches rule matching (it returns "information needed")

### P4 Scenario pipeline (3–4 weeks)
- Prompt construction (following the display language), `URLSession` calls, JSON parsing and
  tolerance
- Scenario confirmation → rule compilation (**condition-level tolerance**: a bad condition drops
  only itself; only when all are bad is the policy skipped)
- Preference normalisation and pruning (runtime fields, relative times)
- **Acceptance**: for the same Chinese or English description, the Mac and iOS produce identical
  `policies` / `facts` / `required_inputs` structures
- **Tests**: bad-condition tolerance; idempotence (re-generating does not create duplicate rules);
  re-analysis does not lose ownership

### P5 Local service + console (1–2 weeks)
- `Network.framework` serves HTTP on `127.0.0.1`, implementing the endpoints the console actually
  calls
- WKWebView loads `http://127.0.0.1:<port>/`, hosting the existing `web/`
- **Acceptance**: every console page works (overview / scenarios / decisions / model service /
  display & language)
- **Tests**: language switching works; the 401/409 contract matches the Mac

### P6 iOS integration (2–3 weeks)
- **Data protection**: set the container file to `NSFileProtectionComplete` (unreadable while the
  device is locked — stronger than the Mac today)
- **Keychain / Secure Enclave**: implement **T5** from `docs/07` §7 here — both unlocking and
  approval require Face ID / Touch ID
- **Export/import**: a custom `UTType` (for example
  `personalontology.personal-ontology.container`), supporting open-in-place from the Files app,
  AirDrop and "export a copy"
- **Tests**: the container cannot be read while the device is locked; importing a damaged file gives
  a clear error and does not damage existing data

### P7 Agent surface: App Intents (1–2 weeks)
- Expose through `AppIntents`: query the scenario catalog, check authorization, rehearse a scenario
  instance
- Reachable from Shortcuts / Siri / Spotlight, **replacing MCP** (iOS does not let a third-party
  client start a stdio subprocess)
- **Acceptance**: a Shortcut can complete a "can this principal perform this action" check

### P8 Testing and release (2–3 weeks)
- Real devices (including iPad), low power / background / locked screen, large-container performance
- TestFlight, App Store copy and privacy notes (**no connection to our own servers**, only to the
  model service the user configured)

**Total 14–22 weeks (4–6 months).**

## 4. Third-party dependencies

**Runtime: 0.** All system frameworks: `CryptoKit`, `CommonCrypto`, `Network`, `WebKit`, `SwiftUI`,
`Security`, `LocalAuthentication`, `AppIntents`, `UniformTypeIdentifiers`, `BackgroundTasks`.

The only component that must be written from scratch is the **Turtle subset parser** (there is no
mature Swift RDF library). No C libraries such as Serd/Redland — we control the serialisation
format, so the subset can be kept very small.

## 5. The three confirmed decisions (pre-work questions closed)

### 5.1 Export/import goes through the **Files app**

- A custom `UTType` (suggested `personalontology.personal-ontology.container`, extension `.po.json`)
- `Info.plist`: `CFBundleDocumentTypes` (containing that UTType) +
  `LSSupportsOpeningDocumentsInPlace = YES`
  → tapping the container in the Files app **opens and writes back in place**, instead of importing a
  copy every time
- **Export**: share sheet → "Save to Files", or "export a copy"
- **First use**: pick a container under "On My iPhone" in the Files app; create one if there is none
- Note: opening in place means **the same file**, so writes must keep the "temporary file + atomic
  replace" discipline, or the Files app / iCloud may read a half-written file

### 5.2 **No merging**: the two containers evolve independently

- No diff / merge / three-way merge; the two containers are two independent ontologies
- The interface must therefore avoid misleading users: show the **container name and path** currently
  open, and state clearly that "this copy and the one on your Mac are two independent datasets"
- Suggested: show the last-modified time and size (principal/scenario/rule counts) when opening, so
  it is easy to confirm the right file was picked

### 5.3 The model-service key **travels with the container**

- As on the Mac today: the API key lives in the container's `model_service` section (the whole
  section is AES-256-GCM encrypted), so **no keychain is needed** and nothing is stored separately
- Consequence: swapping containers swaps the model-service configuration, so "export takes all
  configuration with it" holds
- What still needs separate handling is the **container passphrase itself**: by default it is entered
  on every unlock; an optional "remember the passphrase with Face ID" (passphrase in the keychain,
  protected by biometrics) is the same work as T5 and belongs in P6

## 6. Things explicitly not done

- ❌ **An MCP service**: iOS background restrictions mean a third-party client cannot start a stdio
  subprocess; App Intents replace it
- ❌ **iCloud automatic sync**: conflicts with the "independent copy, moved by hand" decision
- ❌ **A merge tool for two containers**: merging was declined; they evolve independently (see §5.2)
- ❌ **Multi-user / multi-principal login**: still a single-user, single-machine model
- ❌ **A cross-machine agent authorization list**: that is a Mac-side mechanism for same-machine
  processes and is not needed on iOS

## 7. Risks

| Risk | Notes | Mitigation |
|---|---|---|
| Effort misestimation | Concentrated in P4 (most coupled to product detail) | Each phase is independently shippable; work can stop at a usable state at any point |
| Behaviour drift between platforms | Mac and iOS each have their own engine | **A shared test set**: port the Python tests one by one to XCTest; a failure on either side is a bug |
| Container format evolution | A future `version` bump would need both sides changed | The format is frozen; an upgrade must change both sides and ship a migration |
| The Turtle subset proves insufficient | If Mac-side serialisation introduces new constructs | P1 acceptance uses triple-by-triple comparison, which surfaces it immediately |

---

## Evaluation conclusion: not being built (2026-10-02)

After evaluation this plan is **not being built**. The reasons, most important first:

1. **The original motivation does not hold at the platform level.** The plan started from "an
   ontology on the iPad, working with an iPad agent (WorkBuddy / Muse), controlling iPad apps".
   Verification showed that **no third-party app on iOS can drive another third-party app** — there
   is no public API, and the only cross-app automation is App Intents / Shortcuts, which the
   **system** must schedule. WorkBuddy for iPad and Muse Code (a terminal CLI) can only "connect to
   a host", and structurally cannot reach an ontology installed in an iPad app. This is not a
   product difference; it is Apple's sandbox design.

2. **Two independent containers conflict with "a single authority".** The chosen data strategy is
   "an independent copy, no merging, separate evolution", while the ontology's core value is being
   the **single source of truth**. An authority that forks is no longer an authority, and in time it
   produces unanswerable questions such as "which counts — this rule on the phone or that one on the
   Mac?".

3. **The long-term cost of cross-platform drift exceeds the benefit.** The full version is 4–6
   months and requires **permanently maintaining two engines** (Swift and Python); behaviour drift is
   the plan's own top risk. For a single-maintainer personal tool that is a lasting heavy tax.

**Alternatives (confirmed)**:

- **Make the single-machine version complete and stable** — keep deepening the governance core (the
  ontology's decisions, rules and auditing) on macOS; "ask the ontology before an agent acts on an
  app" already works there today.
- **Mobile viewing**, if really needed, via a **2–3 week thin client** (tunnel + the existing HTML
  console), which creates **no second source of truth**.
- **On iPad only App Intents remain**: a Shortcut calls the ontology's decision intent and the
  ontology acts as the policy decision point; the "agent" is the system (Shortcuts + Apple
  Intelligence) rather than a third-party agent. The controllable actions are limited to the
  Shortcuts actions each app chooses to expose.
- Remote agent access (`streamable_http` MCP) is not an iOS topic; it belongs to the "the ontology
  runs on a host" line.

**The rest of this document is kept** as evidence and design reference for that evaluation; if the
premises change (for example if Apple opens a cross-app automation API), it can be re-evaluated on
this basis.
