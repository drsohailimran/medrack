# MedRack one-click launcher

Turns the 3-step manual startup (start model -> SSH in and type `medrack` ->
open browser) into a single desktop double-click that anyone can use.

## Files

| File | What it is |
|------|-----------|
| `RUN-SETUP-FIRST.cmd` | **Step 1 of setup.** Task + SSH key + shortcuts. |
| `AUTHORIZE-SERVER.cmd` | **Step 2 of setup.** Authorizes the key (password once). |
| `setup-medrack-launcher.ps1` | Step-1 logic (called by the .cmd). |
| `authorize-server.ps1` | Step-2 logic (called by the .cmd). |
| `medrack-launcher.ps1` | Daily start. Behind the "Start MedRack" shortcut. |
| `medrack-stop.ps1` | Behind the "Stop MedRack" shortcut. |
| `medrack-config.ps1` | Settings (host, ports, paths). Edit if the network changes. |

## First-time setup (do this ONCE, two double-clicks)

**Step 1 - `RUN-SETUP-FIRST.cmd`**
1. Double-click it.
2. Click **Yes** on the Windows security (UAC) prompt.

This registers the elevated **Scheduled Task** for the Qwopus model (so daily
startup needs **no** admin popup), creates a **passwordless SSH key**, and puts
**Start MedRack** / **Stop MedRack** shortcuts on the Desktop.

**Step 2 - `AUTHORIZE-SERVER.cmd`**
1. Double-click it.
2. Type **sohail's password** for `192.168.29.82` when asked (typing is
   invisible - just type and press Enter). This is the **only** time you type it.

The window shows `[SUCCESS]` when done and waits for you to press Enter. Both
steps are safe to re-run any time (e.g. if you rebuild the server).

## Daily use

**Double-click "Start MedRack" on the Desktop.** A small splash appears while it:

1. starts the Qwopus model on this PC (silently) and waits for port `8080`;
2. starts MedRack on `192.168.29.82` over SSH (no password);
3. waits until the web UI on port `3010` is actually reachable;
4. opens the browser to `http://192.168.29.82:3010`.

If something is already running, it skips that step and goes straight to the
browser. Safe to double-click more than once.

**"Stop MedRack"** stops the model on this PC (frees RAM/GPU) and best-effort
stops MedRack on the server.

## Overnight stability (the AI model)

The model runs under an **auto-restart watchdog** so it can run all night
unattended. If `llama-server` ever dies, it restarts within ~5s. Two logs live
next to the model in `C:\ai models\`:

- `qwopus-watchdog.log` - one line per start/exit/restart (the crash history).
- `qwopus-server.log` - `llama-server`'s own output for the **last** run; look
  here to see *why* it last stopped.

It is tuned NOT to run out of VRAM: this is an 8 GB card and the model is 40
layers / 256 experts, so **all** expert weights run on the CPU
(`--n-cpu-moe 40`), leaving ~4.5 GB VRAM free to absorb spikes from the Windows
desktop / browser / Overwolf. `GGML_CUDA_ENABLE_UNIFIED_MEMORY=1` is a safety
net that spills to system RAM instead of crashing if VRAM ever does fill.

Because of the watchdog, **"Stop MedRack" writes a `qwopus.stop` flag** (so the
watchdog exits instead of relaunching) *before* killing the model - don't kill
`llama-server` by hand, it will just come back; use the shortcut.

## How the pieces map to the old manual steps

| Old manual step | Automated by |
|-----------------|--------------|
| Right-click `run-qwopus-medrack.bat` -> Run as admin | Scheduled Task, triggered silently |
| `ssh sohail@192.168.29.82` + password + type `medrack` | Passwordless SSH key + `RemoteStart` command |
| Open `192.168.29.82:3010` in browser | Auto-opened once the UI is ready |

## Troubleshooting

- **"passwordless login may not be set up"** -> re-run `RUN-SETUP-FIRST.cmd`.
- **Model window shows an error** -> the `MedRack Qwopus Server` window (or
  Task Scheduler task of the same name) failed; check it manually.
- **Change the server IP / ports / model command** -> edit `medrack-config.ps1`.
- **Stop on the server doesn't work** -> the `RemoteStop` value in
  `medrack-config.ps1` must be a command that exists on the box (default
  `stop_medrack.sh`). Leaving MedRack running is harmless.

## Permanent Ubuntu ↔ Windows link

One-time: double-click **INSTALL-PERMANENT-LINK.cmd** (UAC) for firewall + elevated tasks,
or rely on user logon tasks already set by the agent:

| Task | Purpose |
|------|---------|
| MedRack OCR Agent | Always-on OCR API :8090 (restart on fail) |
| MedRack OCR Tunnel | Reverse SSH backup Ubuntu:18090 → Windows:8090 |
| MedRack Link Watchdog | Every 5 min — restart agent/tunnel if dead |
| MedRack Qwopus Server | Model (started by Start MedRack) |

**Stop MedRack** frees GPU (stops model) but **keeps** OCR agent + tunnel up so hybrid ingest still works next time.

Ubuntu uses **direct LAN** `http://192.168.29.89:8090` first, then tunnel fallback.

Verify from Ubuntu:
  curl http://192.168.29.89:8090/v1/health
  curl http://127.0.0.1:18090/v1/health
  curl http://192.168.29.89:8080/health
