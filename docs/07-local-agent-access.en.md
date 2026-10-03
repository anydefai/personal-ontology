# Local agent access control

Status: implemented (T1 + T2 + T3 + T4)
Applies to: scenarios where the ontology and the agent run on **the same device**

## 1. What this solves

Other programs on the same machine must not read anything from the ontology over MCP without your
knowledge and consent.

## 2. The hard limit, stated first

Any program running as your user can read the files you can read, connect to `127.0.0.1` and run
your Python. So a **pure-software scheme with an on-disk credential cannot, in principle,
distinguish "the agent you approved" from "malicious code running as you"**. The only true
boundary is a hardware key plus user presence (Touch ID / Secure Enclave), which this layer does
not include.

## 3. The four things this layer does

| | Measure | Effect |
|---|---|---|
| **T1** | Agents move to a **Unix domain socket** (`data/agent.sock`, 0600); the kernel supplies the peer's **uid / executable / full command line** | **No stealable credential on disk** — there is no token file to copy, and every client is identified by name |
| **T2** | **Deny by default**: a new program's first connection is only registered as "pending", and you allow or deny it in the console's "Agent authorization" page; grants can be listed and revoked | **Silent reads are impossible**; who is reading and how much is visible at a glance |
| **T3** | Every grant carries **scopes**: `catalog` / `rules` / `decisions` / `principals` / `check` / `preview` / `feedback`, excluding `principals` by default | Limits blast radius: a program approved to "check authorization" does not get the whole ontology |
| **T4** | When the backend is unreachable, recovery mode allows **only** `health` / `start` / `restart` | Logs, status and settings changes still require credentials |

Implementation notes: the gateway runs **inside the backend process** and signs identity assertions
with a key that exists only in memory; the API side verifies the signature, so a forged assertion
(connecting straight to the loopback port) is always invalid. Management interfaces (grant list,
privilege escalation, settings changes) are **not exposed to agents**.

## 4. An honest caveat: this is not a hard boundary

Malicious code under the same uid can `exec` our interpreter with the same arguments and therefore
"look identical". What this layer removes is the **cheapest and most covert** path (copying a token
file, silently reading everything), and it turns **every new client into something visible that
needs approval**. Blocking same-uid malicious code requires T5 (Secure Enclave + user presence),
which is a separate design.

## 5. Cross-machine access is off by default

`data/session-token` is **no longer written by default**. Once it exists, any process on the same
machine can read it and call the API directly, bypassing agent authorization. When cross-machine
access (over an SSH tunnel) is genuinely needed, enable it explicitly in
"Agent authorization → Cross-machine access".

## 6. Self-check

`tests/test_agent_access.py` 24/24: unapproved clients are always denied, approved clients are
allowed within their scopes, ungranted scopes are denied, management endpoints and self-escalation
are rejected, forged assertions return 401, revocation takes effect immediately, and re-approval
restores access.

---

## 7. T5 (planned, not implemented)

The user decided to pursue this as later work. It is the only mechanism that can block "malicious
code running as you" — the first four layers only raise the bar and eliminate the silent path;
they **cannot** distinguish "the agent you approved" from same-uid malicious code.

### 7.1 Goal

Turn "may this read the ontology" from a **software decision** into a **hardware plus user-presence
decision**:

- the container key is no longer derived from the passphrase alone but protected by a key in the
  **Secure Enclave**;
- every **unlock** requires **Touch ID / Apple Watch / the system password**
  (`.userPresence` in `SecAccessControl`);
- **approving a new agent grant** also requires user presence — so a silent first access becomes
  impossible at the hardware level too.

### 7.2 Design sketch

1. No plaintext KEK inside the container: instead `container_key` is wrapped by a **SE-generated
   P-256 public key** (ECDH derivation + AES-GCM wrapping); the SE private key never leaves the
   enclave and is set to `.userPresence`.
2. Unlock flow: the user clicks "Unlock" → the system prompts for a fingerprint → the SE completes
   ECDH → `container_key` is recovered → the container is decrypted as today. The passphrase can
   still be used for recovery (as a second wrapping path); otherwise the constraint that a
   forgotten passphrase means lost data is unchanged.
3. Grant approval: `POST /v1/agents/{key}/approve` gains a "user presence required" precondition
   (performed by a local helper calling LocalAuthentication).
4. Optional hardening: sensitive scopes such as `feedback` (writes) require presence on **every
   call** — the strongest security, but clearly worse UX; decide whether to adopt it first.

### 7.3 Trade-offs and decisions needed up front

| Topic | Notes |
|---|---|
| Unlock experience | Changes from "type the passphrase" to "fingerprint, with the system password as fallback"; usually better on macOS, but the **passphrase recovery path must be kept** |
| Migration | The existing `ontology.po.json` must be re-wrapped once (read with the passphrase → generate the SE key → rewrite the container) |
| Compatibility | Machines without Touch ID / a usable SE (or non-macOS) fall back to the current passphrase derivation |
| Residual risk | Within one unlock window, same-uid malicious code can still **ride along** on the unlocked session. Eliminating that requires presence for every sensitive call — this round must decide the trade-off explicitly |
| Where to implement | Swift / `Security.framework` (`LocalAuthentication` + `SecKeyCreateWithData`), or Security.framework via ctypes; the MCP and API sides only need "a presence-backed unlock credential" |

### 7.4 Decide before starting

1. The granularity of presence: **every unlock** (recommended) / every unlock plus every grant
   approval / every sensitive call.
2. Whether to keep "the passphrase alone can decrypt" as a recovery path (recommended, with its
   place in the threat model stated explicitly).
3. Whether the iOS/iPad client proceeds in parallel (the SE is likewise the only hard boundary on
   mobile).
