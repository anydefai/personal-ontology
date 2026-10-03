# Cross-machine use: letting an agent on another machine reach the local ontology

Status: implemented (option A: SSH tunnel + MCP service running on the remote side)
Applies to: scenarios where the agent runs on **another machine** while the ontology data stays on
your local Mac

## 1. Why this needs special handling

In the current architecture **MCP uses the stdio transport**: the agent client starts
`python -m backend.mcp_server` as **its own subprocess**, and the two exchange JSON-RPC over
stdin/stdout. That produces a hard limitation:

> A client on a remote machine **cannot start** a process on your Mac. So stdio MCP is inherently
> same-machine only.

Meanwhile both local HTTP services listen on `127.0.0.1` only and are unreachable from the LAN —
**deliberately**:

- the interfaces' only credential is a local session token, with **no TLS, no per-agent revocable
  credential and no protection aimed at remote origins**;
- and `/v1/*` can **read the entire ontology** (principals, scenarios, preferences, rules,
  decision records).

So **do not** set `PERSONAL_ONTOLOGY_HOST=0.0.0.0` to enable remote access: that exposes the
ontology to anyone on the same network. The manager's origin allowlist only guards against browser
CSRF; it does **not** stop `curl` or scripts.

This approach instead adds **no new network exposure on the local machine**: the remote side reaches
it through an SSH tunnel, and the MCP service runs on the remote machine.

## 2. Topology

```
        ┌──────────── remote machine (where the agent runs) ────────────┐
        │  WorkBuddy / Muse Code                                        │
        │      │ stdio (local subprocess)                               │
        │      ▼                                                        │
        │  scripts/mcp-remote.sh ──► backend.mcp_server                 │
        │                                │ HTTP                         │
        │                                ▼                              │
        │                        127.0.0.1:8765 (tunnel entry)          │
        └────────────────────────────────┼──────────────────────────────┘
                                         │ SSH encrypted tunnel
        ┌────────────────────────────────┼──────────────────────────────┐
        │  Mac (where the ontology lives) ▼                             │
        │  manager 8765 ──proxies /v1/*──► governance backend 8766      │
        │  both listen on 127.0.0.1 only                                │
        └───────────────────────────────────────────────────────────────┘
```

The remote side forwards **8765** (the manager) only. Backend 8766 does not need to be exposed, and
should not be.

## 3. Steps

### 3.1 On the Mac (once)

1. Enable SSH: System Settings → General → Sharing → **Remote Login**.
   Prefer key-only login, and keep the tunnel on loopback (the `-L` default).
2. Confirm the services are running: `~/personal-ontology/start.sh`
3. Unlock the ontology in the console (**every unlock generates a new token**): open
   http://127.0.0.1:8765 and enter the login password.

### 3.2 On the remote machine (once)

The MCP service depends only on the standard library and **needs no pip installs**, but it requires
**Python 3.11 or newer** (it uses 3.10+ type syntax). Copy three files:

```bash
mkdir -p ~/personal-ontology-mcp/backend
scp <your-mac>:~/personal-ontology/backend/{__init__.py,config.py,mcp_server.py} \
    ~/personal-ontology-mcp/backend/
scp <your-mac>:~/personal-ontology/scripts/mcp-remote.sh ~/personal-ontology-mcp/
chmod +x ~/personal-ontology-mcp/mcp-remote.sh
```

### 3.3 Establish the tunnel (keep it running)

```bash
ssh -N -L 8765:127.0.0.1:8765 <your-mac>
```

This connects the **remote** `127.0.0.1:8765` to the Mac's manager over the encrypted SSH tunnel.
`-N` means forward only, without opening a shell. Once the tunnel drops, the remote agent becomes
unavailable (and receives a clear error).

### 3.4 Configure the agent client

Point the MCP configuration's `command` at the wrapper script (**not** directly at python — that way
you would get no token):

```json
{
  "mcpServers": {
    "personal-ontology": {
      "command": "/Users/<you>/personal-ontology-mcp/mcp-remote.sh",
      "env": { "PO_REMOTE": "user@example-host.local" }
    }
  }
}
```

The wrapper script: ① checks the Python version; ② checks that the tunnel is ready; ③ fetches the
unlock-period token over SSH; ④ starts the MCP service over stdio.

Available environment variables: `PO_REMOTE` (required), `PO_REMOTE_HOME` (default
`personal-ontology`), `PO_LOCAL_PORT` (default `8765`), `PO_MCP_HOME` (default
`~/personal-ontology-mcp`), `PO_PYTHON` (default `python3`, needs 3.11+) and `PO_SSH_OPTS`.

## 4. Behaviour and limitations

| Situation | Behaviour |
|---|---|
| Ontology locked | The wrapper clearly says "unlock it in the console on that Mac and retry" and does not start MCP |
| Tunnel not established | It shows the `ssh -N -L ...` command you need to run first |
| Python version too old | It says 3.11+ is required and that `PO_PYTHON` can point at another interpreter |
| **The ontology was unlocked again** | The old token is invalid and the tools return "the session token has expired … restart this MCP connection" — **restarting the client is enough** |
| Idle lock expires | Same as above; unlock again and restart the MCP connection |

**This is not an unattended setup**: the key is derived from the login password and only lives in
memory while unlocked. A remote agent can be used provided you keep the ontology unlocked on the
Mac. Long unattended use would need a separate design (for example storing the credential in the
system keychain), which changes the threat model — see the trade-offs in `05`.

## 5. Security notes

- On the Mac, **do not** change `PERSONAL_ONTOLOGY_HOST`; keep `127.0.0.1`.
- The tunnel forwards **8765 only**; do not forward 8766.
- Use SSH key login with a passphrase, and turn password login off.
- `data/session-token` is a **local** credential file (0600) that exists only while unlocked; the
  remote side fetches it over SSH. **Do not** copy it to the remote machine for long-term storage —
  it changes on every unlock and is equivalent to an access credential.
- The remote machine should be at least as well secured as the Mac: it holds a session token
  (in memory) that can read the ontology.
