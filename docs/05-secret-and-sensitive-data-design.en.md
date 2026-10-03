# Ontology encryption, login and unlock design (v2.1, review draft)

Status: design draft, awaiting review.
This draft supersedes v2 (KDF undecided, login still used an api-token file) and v1 (field-level
encryption with a key on the same disk; skeleton abandoned).

**Decisions taken**: KDF is PBKDF2 (zero dependencies on iOS); LLM credentials move under container
protection; **login becomes password-based**, replacing `data/api-token`.

---

## 0. Why the skeleton changed

v1 encrypted only `ContactPoint.value`, with the key in a plaintext file beside the data. All three
target threats defeated it: the ontology data was 100% plaintext Turtle, the key was readable by the
same account, and 99% of the data was outside the encrypted scope.

The three hard premises of v2.1:

1. **Whole-graph encryption**: the ontology file is ciphertext end to end, leaking not even ids,
   relations, timestamps or the original scenario text.
2. **The key comes from the passphrase and is never written to disk in a usable form**: the file's
   trust domain and the passphrase's trust domain are separated.
3. **Zero plaintext on disk and zero long-lived credentials**: no plaintext data and no long-lived
   token that could be read off (see §5).

## 1. Threat model

**Covered** (in every case the adversary ends up with "the file"):

| # | Adversary | Notes |
|---|---|---|
| T1 | Malicious software on the device | Reads the ontology file directly. Mac first, an iPhone/iPad client later |
| T2 | Someone who gets the machine or the disk | Physical access, disk removal, a stolen device |
| T3 | Someone who gets the ontology file | Copied, synced elsewhere, sent to the wrong person |

**Not covered**: an adversary who fully controls the login session and can read process memory while
unlocked (requires debug rights or root); screen/clipboard/keyboard capture while unlocked;
passphrase phishing; historical plaintext lingering in uncovered blocks (see §8.3).

## 2. Architecture overview

```text
    Console / iOS app
        │  ① first time: set a login password   ② afterwards: enter it to log in (= unlock)
        ▼
   ┌──────────────────────────────────────────────┐
   │  Backend service (Mac)                        │
   │  Uninitialised: no container → guide the user to set a password (409) │
   │  Locked       : no key, no graph in memory → require login (401)      │
   │  Unlocked     : container decrypted into memory → in-memory session token │
   │  Write        : graph → Turtle → AES-256-GCM → atomic replace         │
   └───────────────────────┬──────────────────────┘
                           │
              ontology.po.json（always ciphertext）
                           │
              safe to sync / back up / copy away
```

**Logging in is unlocking**: the password serves both authentication and key derivation, so there is
no separate token file.

## 3. Container format specification (portable; iOS must be able to implement it)

A single JSON document: any platform can parse it, avoiding binary byte-order problems. A ~35 KB
ontology becomes ~47 KB encrypted.

### 3.1 Structure: one file, two independently encrypted sections

**The format is frozen**: `version: 1` is a cross-implementation contract; field names, AAD
concatenation and algorithm parameters must not change again. Any change requires a version bump.

```json
{
  "format": "personal-ontology-container",
  "version": 1,
  "revision": 42,
  "created_at": "2026-10-01T12:00:00Z",
  "updated_at": "2026-10-01T20:15:00Z",
  "sections": {
    "ontology": {
      "kdf": { "name": "pbkdf2-hmac-sha256", "salt": "<base64,16B>", "iterations": 2000000, "dklen": 32 },
      "cipher": { "name": "AES-256-GCM", "nonce": "<base64,12B>" },
      "ciphertext": "<base64, ciphertext || 16B tag>"
    },
    "model_service": {
      "kdf": { "name": "pbkdf2-hmac-sha256", "salt": "<base64,16B>", "iterations": 2000000, "dklen": 32 },
      "cipher": { "name": "AES-256-GCM", "nonce": "<base64,12B>" },
      "ciphertext": "<base64, ciphertext || 16B tag>"
    }
  }
}
```

**Why two sections rather than two files**: changing the passphrase must re-encrypt both the ontology
and the model credentials. Renaming two files is **not one atomic operation** — succeed with one and
fail with the other and you get "ontology under the new passphrase, credentials under the old one",
which the user experiences as a baffling "configuration cannot be read". A single file written to a
temporary file and replaced once with `os.replace` is atomic: all or nothing (see §4.5).

**Why each section has its own salt**: key separation. The two keys are derived from the same
passphrase but cannot be derived from one another, so one section leaking does not affect the other.

**Unchanged sections are copied verbatim**: when writing the file, if `model_service` did not change,
its existing bytes are reused as-is (same salt, same nonce, same ciphertext) and the **API key never
needs to be decrypted into memory**. Day-to-day ontology writes therefore neither touch credentials
nor risk nonce reuse.

**The model-service section is decrypted on demand**: unlocking decrypts only the `ontology` section;
`model_service` is decrypted when a model call is actually needed.

### 3.2 Algorithms (fixed, no choice offered)

| Purpose | Algorithm | Parameters |
|---|---|---|
| Passphrase derivation | **PBKDF2-HMAC-SHA256** (RFC 8018 / NIST SP 800-132) | 16 B random salt; **2,000,000 iterations**; 32 B output |
| Encryption | **AES-256-GCM** | 256-bit key; 96-bit random nonce; 128-bit tag |
| Plaintext payload | the existing Turtle serialisation (UTF-8) | rdflib / SHACL logic unchanged |

**Measured basis for the iteration count** (local Apple Silicon, PBKDF2-HMAC-SHA256):

| Iterations | Time |
|---|---|
| 100,000 | 12 ms |
| 600,000 (OWASP's suggested floor) | 71 ms |
| **2,000,000 (the value chosen here)** | **about 236 ms** |

CommonCrypto on iOS is typically 2–4× slower, i.e. about **0.5–1 s** — acceptable for a one-off
unlock. The iteration count is recorded in the container header, so it **can be raised later without
breaking old files** (an old file decrypts with its own header parameters).

**AAD (additional authenticated data)**: binds the header parameters so the header cannot be
tampered with. Constructed exactly, to be reproducible across languages (no "canonical JSON"):

```
aad = "po-container-v1|" + section + "|" + version + "|" + salt_b64 + "|" + iterations + "|" + nonce_b64
```

ASCII concatenation, integers in decimal with no leading zeros. The decrypting side must rebuild it
the same way, or it gets `InvalidTag`.

### 3.3 Cross-platform implementation paths: zero third-party dependencies on both sides

| Component | Python (Mac backend) | Swift (iOS/iPadOS) |
|---|---|---|
| AES-256-GCM | `cryptography`'s `AESGCM` (existing dependency) | **CryptoKit `AES.GCM` (built in)** |
| PBKDF2-HMAC-SHA256 | **`hashlib.pbkdf2_hmac` (standard library)** | **CommonCrypto `CCKeyDerivationPBKDF` (built in)** |

This is precisely why PBKDF2 was chosen: iOS needs no library at all. The cost is that PBKDF2
resists GPU/ASIC cracking less well than scrypt or Argon2id, so **the passphrase strength
requirement is raised accordingly** (§4.3) and the iteration count is set to an acceptable high
value.

### 3.4 Test vectors

A specification must ship fixed test vectors (passphrase, salt, iterations, nonce, expected
ciphertext and AAD) so that Swift and Python can verify each other against the same set.
**A format specification without test vectors is not frozen.**

### 3.5 Test vectors (frozen)

Every language's implementation must produce **exactly the same** ciphertext from the fixed inputs
below, or it is incompatible. The vectors use a small iteration count for fast verification;
production paths must use a random salt and a random nonce.

| Input | Value |
|---|---|
| section | `ontology` |
| version | `1` |
| password | `correct horse battery staple` |
| salt | hex `000102030405060708090a0b0c0d0e0f` (base64 `AAECAwQFBgcICQoLDA0ODw==`) |
| iterations | `1000` |
| nonce | hex `101112131415161718191a1b` (base64 `EBESExQVFhcYGRob`) |
| plaintext | `测试向量：personal-ontology container v1` (UTF-8; base64 `5rWL6K+V5ZCR6YeP77yacGVyc29uYWwtb250b2xvZ3kgY29udGFpbmVyIHYx`) |

> The plaintext is deliberately Chinese: these bytes are **frozen test data**, not UI text. They must
> never be translated, or every implementation would produce a different ciphertext. This is one of the
explicit exceptions in `docs/00-first-principle-bilingual.md`.

Intermediate and final results:

```
derived key (base64) = ppsXnjrdPB4KryJ6DrOqKqhkWrhv7PbKAMF1Eml8cZ4=
AAD (ASCII)          = po-container-v1|ontology|1|AAECAwQFBgcICQoLDA0ODw==|1000|EBESExQVFhcYGRob
ciphertext (base64)  = +lI6y8hTGDT7gLfyNSGpg9BY7nxOlr7a5UevsJaYhb+rKmZ6SfPhKrWYtCBXwZsr1nU0ncqlXTimCNOEnA==
```

On the Python side this is asserted as a fixed check by group 12 of `tests/test_vault.py`; an iOS
implementation should self-test against the same values.

## 4. Login, unlock and the locked state

### 4.1 The three states

| State | Condition | Behaviour |
|---|---|---|
| **Uninitialised** | no container file | everything except `/health` returns **409** `{"error":"ontology_uninitialized"}`; the frontend guides the user to set a password |
| **Locked** | container present, no valid session | everything except `/health` and `/v1/login` returns **401** `{"error":"login_required","message":"本体已锁定，请输入登录密码。"}` |
| **Unlocked** | valid session | normal |

Not-logged-in and locked are the same state, so both use 401 (unlike v2, which distinguished 423) and
the frontend only has to show one password screen.

### 4.2 Endpoints

| Endpoint | Notes |
|---|---|
| `GET /health` | no authentication; returns `{"locked":bool,"initialized":bool}` |
| `POST /v1/setup {password}` | only while uninitialised; sets the password and creates (or migrates, see §8) the container; on success the caller is logged in |
| `POST /v1/login {password}` | derive the key from the container header → decrypt → success means unlocked; returns the in-memory session token |
| `POST /v1/logout` | ends the current session |
| `POST /v1/lock` | discards the in-memory key and graph and invalidates **all** sessions |
| `PUT /v1/account/password {current,new}` | changes the login password (= re-encrypts the container), see §4.5 |
| other `/v1/*` | require a session token; 401 when not logged in |

**Login failure protection**: consecutive failures back off exponentially (1s/2s/4s… capped at 30s);
failure logs record only "failure number N", never the passphrase or its length. Note that **an
attacker holding the file can crack it offline**, so backoff is only a supplement — the real defence
is passphrase strength and the iteration count.

### 4.3 Passphrase policy (8-character floor plus three compensating rules)

**Decided: at least 8 characters.** Length alone is not an effective defence — PBKDF2 resists GPU
cracking poorly, and the same 8 characters differ by 8 orders of magnitude depending on their
composition. Measured offline-cracking estimates (PBKDF2 at 2,000,000 iterations, 236 ms per attempt
locally):

| Passphrase type | Single GPU | 8-GPU cluster |
|---|---|---|
| 8-character **common password** (100k dictionary) | 1.7 minutes | **12.5 seconds** |
| 8 random lowercase | 6.6 years | 10 months |
| 8 random upper+lower+digits | 6.9 thousand years | 865 years |
| 5 diceware words | 900 million years | 112 million years |

So accepting an 8-character floor **requires** these three:

1. **Reject common passwords**: a built-in list of frequent passphrases (`password1`, `12345678`,
   `qwerty`, dates, repeated characters, keyboard runs and so on) plus pattern detection, rejecting on
   a hit. This single rule removes the "12.5 seconds" row and is the most effective of the three.
2. **Require at least 3 character classes**: from lowercase / uppercase / digits / symbols, raising
   the attack space from `26^8` to `62^8` or more.
3. **Warn strongly without blocking on low strength**: below roughly 50 bits of entropy show an
   explicit warning ("this kind of passphrase can be cracked offline") and require an acknowledgement
   tick; the interface **recommends** (does not require) 5 diceware words.

State clearly that "forgetting the password means the data cannot be recovered" and require an
acknowledgement tick.

**Optional hardening (suggested)**: raise the iteration count from 2,000,000 to 3,000,000 — about
354 ms locally and 0.7–1.5 s on iOS, increasing the attacker's cost linearly by 50%. The iteration
count lives in the container header, so raising it does not affect reading old files.

### 4.4 Sessions

- After a successful login the backend generates a random session token that lives **only in backend
  memory** (with an expiry); the browser keeps it in `sessionStorage`.
- Restarting the backend invalidates every session, requiring a fresh login (which is also a fresh
  unlock).
- Idle auto-lock defaults to **30 minutes** (sliding expiry: each request renews it); when it fires,
  the key and graph are discarded and all sessions end. The duration is configurable through
  `session_timeout_minutes` in `data/settings.json` (0 = never auto-lock) and
  `PUT /v1/account/session-timeout`; the "Login & security" page offers the options.

### 4.5 Changing the login password (replacing "key rotation")

There is only one passphrase, so changing the password **re-encrypts both container sections**
(`ontology` and `model_service`, see §6).

**Transaction flow (aiming for all-or-nothing)**:

```text
1. verify the current password: decrypt the ontology section with it (failure = reject)
2. take a global write lock: pause other writers (so a concurrent write does not lose data)
3. derive two new keys from the new password with a fresh salt per section, re-encrypt both sections
4. write a temporary file in the same directory → fsync → replace the container with a single os.replace
       (one file, one replace = atomic: on a crash the old file is intact and the old password still works)
5. release the write lock; discard the old in-memory keys and swap in the new ones
6. invalidate all sessions, delete the unlock-period temporary credential (§5) → require a new login
```

**Failure-mode analysis**:

| Situation | Outcome |
|---|---|
| Step 3 fails (out of memory, etc.) | nothing was written; the container is unchanged and the old password still works |
| A crash or power loss mid-step-4 | the temporary file is left behind, the real container was not replaced → the old password still works; the temporary file is cleaned up on next start |
| Step 4 succeeded but the crash came before step 6 | the container already has the new password; after restart the new password is required (the old one no longer works, as expected) |
| Concurrent writes | blocked by the step-2 write lock, so no data is lost |

**Impact on normal data operations: none.** The data itself is unchanged, only re-encrypted under a
new key; after the change the store keeps reading and writing with the new key and nothing else
changes.

**Two user-visible consequences** (which the interface must state):

1. **All sessions are invalidated**, including other devices and MCP subprocesses — a new login is
   required;
2. **Existing encrypted backups remain protected by the old password.** Changing the password does
   not (and cannot) change backups already exported — they still open with the old password. The
   interface offers a prompt to "re-export a backup with the new password".

## 5. Credential model: no long-lived credential on disk

The current `data/api-token` is **long-lived and readable by any process under the same account** —
directly at odds with the threat model. It is replaced by:

| Credential | Where it lives | Lifetime |
|---|---|---|
| Login password / container key | **never on disk**. The password appears once, in the `POST /v1/login` request body | one request |
| Derived key | memory only; zeroed on a best-effort basis on lock/logout | the unlock period |
| Session token | backend memory | until logout, lock or restart |
| Password verifier | **not stored separately** — the container's own GCM tag is the verifier | — |
| Unlock-period temporary credential (for MCP subprocesses) | `data/session-token`, mode 0600 | **only while unlocked**; deleted on lock or logout |

**Authenticating the MCP subprocess**: a local MCP process is launched by the client and cannot type
a password interactively. So while unlocked the backend writes the current session token to
`data/session-token` (0600), and MCP **re-reads it before every call** (the current implementation
reads once at startup and must change to per-call reads). Once locked the file does not exist and MCP
receives the explicit message "the ontology is locked; ask the user to unlock it in the console."

The benefit: **no long-lived credential exists anywhere on disk**. Malware scanning the whole disk
finds no token it could use for access.

## 6. LLM credentials move into the container (decided)

> **Status: implemented.** The model configuration now lives in the container's `model_service` section (independent salt and nonce); on upgrade the old `model-service.json` and `model-service.key` are migrated into the container and deleted.

The API key in `model-service.json` is currently protected by a separate key (`model-service.key`)
and sits outside the container. It becomes:

- the **`model_service` section of the same container file** (§3.1), encrypted with a second key
  derived from **the same password with an independent salt**;
- decrypted on demand: the API key is only recovered when a model call is really needed, and daily
  ontology reads and writes never touch it;
- copied verbatim when unchanged, never re-encrypted and never reusing a nonce.

**Why the same file rather than a second one**: changing the password must rewrite both, and renaming
two files is not atomic, producing a broken half-new, half-old state (§4.5). A single-file replace
removes that window while an independent salt preserves key separation.

## 7. The zero-plaintext invariant and residue handling

### 7.1 The invariant

> At no time does plaintext ontology data, or a long-lived access credential, exist on disk.

The simplifications that follow:

- `_persist()`'s temporary file is itself ciphertext → leftover snapshots are no longer a
  confidentiality risk;
- a backup = copying the container file → **it is an encrypted backup by construction**, so "key
  separate from backup" holds automatically;
- **field-level encryption (Fernet on `contacts.value`) is no longer needed**: the container is
  already encrypted as a whole, and keeping it would only reintroduce key management and silent
  failures. **Delete that code path and `contact.key`.**

### 7.2 Logs and the frontend

- Service logs contain no ontology content; errors record only a record id and an error type.
- The frontend keeps no local persistence (no `localStorage` / IndexedDB); the session token lives in
  `sessionStorage`.

### 7.3 Historical plaintext (stated honestly)

On an SSD/APFS there is no guarantee that old data is physically overwritten: after deletion,
plaintext may remain in **APFS local snapshots**, Time Machine backups or unwritten blocks.
Therefore:

- **FileVault is still recommended** — it covers precisely that "historical plaintext";
- the migration steps include deleting plaintext files, leftover snapshots and plaintext exports, and
  list local snapshots so the user can decide whether to delete them (`tmutil listlocalsnapshots /`).

## 8. Migrating from plaintext to the container

```text
1. back up the existing ontology.ttl to a location the user chooses (prompt to delete it when done)
2. the user sets a login password (§4.3)
3. read the plaintext Turtle → SHACL validate → serialise → encrypt → atomically write ontology.po.json
4. re-read and decrypt the container → compare triple by triple with the pre-migration graph
5. delete ontology.ttl, leftover ontology-*.ttl, plaintext exports and data/api-token
6. report: container path, revision, residue check results
```

Step 4, "after decryption it matches the original graph", is the acceptance condition; if it does not
match, keep the plaintext and roll back.

Supporting change: `install.sh` **no longer generates `data/api-token`** (that step is removed); the
first password is set by the user in the console.

## 9. Cross-platform and the iPhone / iPad route

- Encryption is **a matter of the file format**, not of the service — this Python service does not run
  on the phone.
- **A native iOS app reading and writing the container directly is recommended** (SwiftUI +
  CryptoKit + CommonCrypto), accessed through the Files app or iCloud Drive; going through the Mac's
  API is not recommended (it only listens on 127.0.0.1).
- iOS notes: keep the container in the sandbox with `NSFileProtectionComplete`; the password may be
  stored in the Keychain (`kSecAttrAccessibleWhenUnlockedThisDeviceOnly`) with `LAContext` Face ID
  for convenient unlocking — **this is local convenience only and does not replace the password**.
- **Concurrent multi-device use**: the container carries a `revision`; compare before writing and
  refuse to overwrite when the on-disk revision is greater ("the file was updated by another
  device"). The convention is a single writer at a time, with no automatic merging.

## 10. Grading of audit and runtime values (retained, lower priority)

The container solves "the file was taken" but not "while unlocked" or "data handed to an agent":

1. **Minimisation before encryption**: the decision record's `input_params` by default keeps only the
   fields the constraints used, plus an HMAC-SHA256 digest of the rest.
2. **External display policy**: `principal_display_mode` (`neutral` by default / `full` / `id_only`),
   controlling whether principal names enter the context of the model an agent talks to.

## 11. Interface design

### 11.1 First open: set the login password (replacing "paste an API token")

```text
┌ Set login password ──────────────────────────────┐
│ This password logs you in and encrypts your ontology data. │
│ Password     [__________________]                │
│ Repeat       [__________________]                │
│ Strength     ▓▓▓▓░░  at least 8 characters, 3 classes │
│              (common passphrases are rejected; 5 unrelated words recommended) │
│ [ ] I understand the data cannot be recovered if I forget the password │
│                              [Create and encrypt] │
└──────────────────────────────────────────────────┘
```

If an existing plaintext `ontology.ttl` is detected, the same screen adds a line "will encrypt the
existing ontology data (N records)".

### 11.2 Every later open: logging in is unlocking

```text
┌ The ontology is locked ──────────────────────────┐
│ Enter the login password to unlock scenarios, rules and decision records. │
│ Password [__________________]      [Log in]      │
│ Forgetting the password means the data cannot be recovered. │
└──────────────────────────────────────────────────┘
```

- While not logged in, no ontology data is rendered or prefetched.
- A failure only says "incorrect password".

### 11.3 Configuration & monitoring → "Login & security"

As requested, password changes live under "Configuration & monitoring":

| Block | Content |
|---|---|
| Change login password | current password + new password (twice) + strength hint; running it re-encrypts the container and logs out every session |
| Lock | an "Lock now" button; the idle auto-lock duration setting |
| Status | container path, revision, last update time, KDF iteration count |
| Plaintext residue check | lists `ontology.ttl`, leftover snapshots, plaintext exports and an old `api-token`, confirming deletion item by item |

**No longer needed**: key fingerprints, downloading a key copy, a keychain switch, key rotation
(changing the password is the rotation).

## 12. Phased implementation

Status as of 2026-10-01: P0–P5 (Python/Mac side) are complete and tested; the iOS client has not
started.

| Phase | Content | Verification | Status |
|---|---|---|---|
| **P0** | Clean up plaintext residue (9 snapshots, plaintext exports); delete the field-level encryption path and `contact.key`; stop generating `api-token` | graph contents compared item by item | ✅ |
| **P1** | Container format (§3) + credential model (§5) + login/locked states (§4) + migration (§8) | test-vector round trip; triple-by-triple comparison after migration; 401 when not logged in, 409 when uninitialised | ✅ `tests/test_vault.py` 37/37, `tests/test_api_auth.py` 40/40, a real-data migration rehearsal 24/24 |
| **P2** | Interface (§11): set password, login screen, login & security page, idle auto-lock | walk the whole flow manually | ✅ idle locking is handled by the session TTL; the interface returns to the login screen on 401 |
| **P3** | LLM credentials into the container (§6); MCP reads the unlock-period credential per call | locked-state MCP reports a clear message; calls work once unlocked | ✅ `tests/test_mcp_e2e.py` 13/13 (real uvicorn + a real stdio subprocess) |
| **P4** | Minimised audit fields (§10.1) + principal display policy (§10.2) | decision records no longer contain names in plaintext | ✅ audit minimisation 11/11; the three display modes checked one by one |
| **P5** | Freeze the format specification + test vectors (§3.5) → a native iOS client | Swift and Python read and write the same container | 🔶 specification and vectors frozen; iOS client pending |

## 13. Open items

1. **The plaintext backups I made** (two `.ttl` files under
   `~/Documents/personal-ontology/backup/`): they should be deleted after a successful migration —
   they are plaintext copies and conflict with the "zero plaintext on disk" invariant.
2. ~~APFS local snapshots~~ **Implemented**: both the migration report and the "Login & security"
   page list `tmutil listlocalsnapshots` output with the delete command.
3. ~~Common-password list~~ **Implemented**: `assets/common-passwords.txt` ships 10,001 entries
   (SecLists 10k-most-common, MIT) plus pattern detection and three normalised comparisons.
4. **Should the iteration count rise to 3,000,000** (§4.3 optional hardening)? It is currently
   2,000,000 (about 240 ms locally).
5. ~~Configurable idle lock duration~~ **Implemented**: `data/settings.json` plus
   `PUT /v1/account/session-timeout` (0–1440 minutes).

**Implemented but worth reviewing**: audit minimisation keeps only the context fields a decision
actually read (§10.1), and the names of skipped fields are recorded in `context_not_retained` — if you
would rather not keep even the field names, that can be tightened further.

**Decided**: KDF = PBKDF2-HMAC-SHA256; LLM credentials inside the container (the `model_service`
section of the same file); login is password-based; the login and container passphrase are **merged
into one**; idle auto-lock at 30 minutes; an 8-character passphrase floor (with the three
compensating rules in §4.3).

**Known residual risks** (not mitigated, stated only): memory scraping while unlocked;
screen/clipboard capture; passphrase phishing; historical plaintext in unwritten blocks (covered by
FileVault); **the fragility of an 8-character passphrase without the compensating rules (mitigated by
§4.3)**.
