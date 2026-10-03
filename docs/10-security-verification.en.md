# Security measures and how to verify them

This document lists the current version's security protections one by one, and gives **commands you
can run yourself** to verify each of them.

If you would rather not go through them one at a time, run this single command, which checks each
item and prints a summary:

```bash
bash ~/personal-ontology/scripts/verify-security.sh
```

Each entry below says three things: what the measure is, how to run the check, and what you should
see. The commands are meant to be run from `~/personal-ontology` and **none of them needs your login
passphrase**.

## 1. Data at rest: encrypted as a whole

| # | Measure | How to verify | Expected result |
|---|---|---|---|
| 1.1 | The ontology and the model configuration live in a single encrypted container | `ls ~/personal-ontology/data/` | only `ontology.po.json` plus logs and session files; **no** `.ttl` or plaintext JSON ontology |
| 1.2 | The container's contents are unreadable | `more ~/personal-ontology/data/ontology.po.json` | only base64 ciphertext and metadata — **no Chinese text, no field names and no API key** (space to page, `q` to quit) |
| 1.3 | Key derivation: PBKDF2-HMAC-SHA256, 2,000,000 iterations | `python3 -c "import json;d=json.load(open('data/ontology.po.json'));print([(n,b['kdf']['name'],b['kdf']['iterations']) for n,b in d['sections'].items()])"` | both sections show `pbkdf2-hmac-sha256` / `2000000` |
| 1.4 | Symmetric encryption: AES-256-GCM | same command, printing `b['cipher']['name']` | `AES-256-GCM` |
| 1.5 | Each section has its own salt and nonce (separate keys, no nonce reuse) | look at `salt` and `nonce` in the 1.3 output | the values for `ontology` and `model_service` **differ** |
| 1.6 | Ciphertext is bound to AAD, so moving or tampering with it fails to decrypt | `grep -n "def section_aad" -A 14 backend/vault.py` | the AAD concatenates section name, version, salt, iterations and nonce |
| 1.7 | Writes are atomic (temporary file plus replace) | `grep -n "os.replace" backend/vault.py` | `os.replace` is present (a same-directory rename is atomic) |
| 1.8 | Permissions: directory 0700, container 0600 | `ls -ld data; ls -l data/ontology.po.json` | `drwx------` and `-rw-------` |
| 1.9 | The decrypting key is never written to disk | `ls data/*.key` | `No such file or directory` |

## 2. The API key and the model configuration

| # | Measure | How to verify | Expected result |
|---|---|---|---|
| 2.1 | The model configuration lives in the container's `model_service` section | `python3 -c "import json;print(list(json.load(open('data/ontology.po.json'))['sections']))"` | `['ontology', 'model_service']` |
| 2.2 | **No plaintext API key exists on disk** | `grep -c "sk-" data/ontology.po.json` | `0` |
| 2.3 | No plaintext `api_key` field exists | `grep -c '"api_key"' data/ontology.po.json` | `0` |
| 2.4 | There is no separate configuration or key file | `ls data/model-service.key data/model-service.json` | neither exists |
| 2.5 | The key is encrypted once more inside that section | `grep -n "api_key_encrypted" backend/model_service.py` | written with `_cipher().encrypt(...)` and decrypted on read |
| 2.6 | Plaintext exists only in memory while unlocked | see §11 | it cannot be proven from disk; that is the design boundary |

## 3. Passphrase and sessions

| # | Measure | How to verify | Expected result |
|---|---|---|---|
| 3.1 | At least 8 characters and at least 3 character classes | `grep -n "len(password) < 8" backend/api.py` | the check exists |
| 3.2 | The passphrase is normalised before comparison (so `Password123!` is rejected) | `grep -n "strip(" backend/api.py` | you can see the lowercasing and the stripping of trailing digits and punctuation |
| 3.3 | A common-passphrase blocklist ships with the package | `wc -l assets/common-passwords.txt` | `10004` |
| 3.4 | No passphrase is on disk | `grep -rl password data/ \| grep -v '\.po\.json'` | no output |
| 3.5 | Session tokens exist only while unlocked | `ls data/session-token` → **lock** in the console → `ls` again | present while unlocked (0600, for the local MCP child process), gone after locking |
| 3.6 | Idle auto-lock | `cat data/settings.json` | `session_timeout_minutes` is not `0` (30 minutes by default) |
| 3.7 | Changing the passphrase re-encrypts the container | compare `stat -f %m data/ontology.po.json` and the `salt` from 1.3 before and after | both the timestamp and the salt change |

## 4. Network exposure

| # | Measure | How to verify | Expected result |
|---|---|---|---|
| 4.1 | Listens on loopback only | `lsof -nP -iTCP -sTCP:LISTEN \| grep -E "8765\|8766"` | `127.0.0.1:8765` and `127.0.0.1:8766` |
| 4.2 | Nothing listens externally | same command | no `0.0.0.0` and no LAN address appears |
| 4.3 | Cross-origin requests are refused | `curl -s -o /dev/null -w '%{http_code}' -H 'Origin: https://evil.example' http://127.0.0.1:8765/v1/principals` | `403` |
| 4.4 | Requests without credentials are refused | `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8765/v1/principals` | `401` |
| 4.5 | Agent access uses a Unix domain socket, not a network port | `ls -l data/agent.sock` | an `srw-------` socket file |

## 5. Agent identity and authorization

| # | Measure | How to verify | Expected result |
|---|---|---|---|
| 5.1 | Identity comes from peer process credentials | `grep -nE "^def (peer_pid\|peer_uid\|executable_path\|command_line)" backend/peercred.py` | all four functions exist |
| 5.2 | There is no token file that could be copied and replayed | `ls data/ \| grep -i token` | only the while-unlocked `session-token` (see 3.5) |
| 5.3 | Authorization is per capability, with a pending state | the console's "Agent authorization" page | three sections: waiting for your approval / authorized / denied |
| 5.4 | A program that has never asked is never silently allowed | `grep -n "尚未请求过访问" backend/agent_access.py` | that branch exists |

## 6. The decision engine

| # | Measure | How to verify | Expected result |
|---|---|---|---|
| 6.1 | Deny by default | `~/personal-ontology/.venv/bin/python tests/test_policy_actions.py` | `7/7 checks pass` |
| 6.2 | Unknown operators and unregistered constraints never allow | `grep -n "return False" backend/store.py \| head` | the unknown-type branch returns `False` |
| 6.3 | `draft` / `suspended` rules never take part in allowing | `grep -n "policy_status" backend/store.py \| head` | anything but `active` does not allow |
| 6.4 | Regex-based matchers are disabled by default | `grep -n "regex" backend/store.py` | those branches are disabled |
| 6.5 | An authorization check executes nothing | the console's "Quick decision" | it returns a decision and an audit record only, and calls no external service |

## 7. Auditing and traceability

| # | Measure | How to verify | Expected result |
|---|---|---|---|
| 7.1 | Every decision is recorded | the console's "Decisions" page | records exist, with time and outcome |
| 7.2 | A record keeps the rule reference and snapshot used at the time | expand any decision record | it traces back to the rule version and execution id |
| 7.3 | Scenario-instance updates keep the user's own words and before/after values | the console's "Scenario instances" → revision history | it contains the user's words, before/after field values, time and instance revision |

## 8. Availability and recovery

| # | Measure | How to verify | Expected result |
|---|---|---|---|
| 8.1 | The console and the governance backend are two processes | `lsof -nP -iTCP -sTCP:LISTEN \| grep -E "8765\|8766"` | each port has its own process |
| 8.2 | The backend can be restarted from the console | the console's "Service monitor" → stop / start | after the backend stops, the console still works |
| 8.3 | A backup is a single file | `ls -l data/ontology.po.json` | that one file is all the data |

## 9. Automated tests (matching the tables above)

```bash
cd ~/personal-ontology
for t in test_vault test_api_auth test_policy_actions test_agent_access test_origin_policy; do
  .venv/bin/python "tests/$t.py" | tail -1
done
```

| Test | Security area covered |
|---|---|
| `test_vault.py` (37 checks) | container encryption, passphrase derivation, AAD binding, atomic writes, wrong-passphrase rejection |
| `test_api_auth.py` (42 checks) | authentication, sessions, passphrase policy, first-run setup |
| `test_policy_actions.py` (7 checks) | deny by default, per-action scoping |
| `test_agent_access.py` (24 checks) | agent capabilities and the approval flow |
| `test_origin_policy.py` (12 checks) | origin checking |

## 10. What these commands **cannot** prove (please read alongside)

- **While unlocked, plaintext is in memory.** Malware able to read the backend process's memory is
  outside this model; the "encryption" here protects **data at rest** only.
- **It is not a sandbox.** The decision engine adjudicates authorization; it does not intercept what
  an agent actually does. The agent must call it and honour the result.
- **There is no TLS.** The design assumes local loopback; do not expose it across a network.
- **A weak passphrase remains the biggest risk.** 2,000,000 iterations raise the cost of offline
  cracking but do not make it impossible — keep the passphrase in a password manager.
- **Container metadata is plaintext** (section names, algorithm, iteration count, salt, nonce). That is
  by design: decryption needs a key derived from your passphrase.
- **`data/session-token` exists while unlocked** (0600, read by the local MCP child process) and is
  deleted on locking.
- **`data/settings.json` is plaintext**, holding interface preferences only (language, cross-machine
  switch, idle-lock timeout).
- **Legacy fallback files are not removed automatically.** If `data/model-service.json` or
  `model-service.key` exists, the fallback path is in use and you may delete them by hand.
