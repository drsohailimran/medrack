# Deployment & Operations

How to run MedRack as a persistent service, update it, and troubleshoot.

---

## Turn it on / off

```bash
cd medrack
bash run.sh      # starts API (:8010) + frontend (:3010), detached
bash stop.sh     # stops them
```

`run.sh` launches both processes with `setsid` (fully detached), writes PIDs to
`.run/*.pid`, and logs to `.run/api.log` and `.run/frontend.log`. It refuses to
double-start (checks the PID files). If a local LLM server is on another
machine, make sure that machine is up first.

**Quick "turn it back on" recipe** (after a reboot):
```bash
cd ~/medrack
bash run.sh
# open http://localhost:3010
```

---

## Start automatically on boot (systemd)

Optional — makes MedRack come back after a reboot. Create
`/etc/systemd/system/medrack.service`:

```ini
[Unit]
Description=MedRack
After=network-online.target
Wants=network-online.target

[Service]
Type=forking
User=YOUR_USER
WorkingDirectory=/home/YOUR_USER/medrack
ExecStart=/home/YOUR_USER/medrack/run.sh
ExecStop=/home/YOUR_USER/medrack/stop.sh
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now medrack
sudo systemctl status medrack
```

---

## Ports & network

| Service | Default port | Notes |
|---------|--------------|-------|
| Frontend (UI) | 3010 | change via `FRONTEND_PORT` |
| API | 8010 | change via `API_PORT`; docs at `/docs` |
| Local LLM (llama.cpp) | 8080 | on the GPU host; `MEDRACK_LLM_BASE_URL` |

To reach the UI from other LAN devices, open the ports in your firewall and
rebuild the frontend with the LAN `MEDRACK_API_BASE` (see
[SETUP.md](SETUP.md#accessing-the-ui-from-another-device)). MedRack has **no
authentication** — only expose it on a trusted network, never the public
internet.

> Default ports are `8010`/`3010` (not `8000`/`3000`) specifically so MedRack
> can coexist with another service already using the common ports.

---

## Updating to a new version

```bash
cd medrack
git pull
bash stop.sh

# if backend deps changed:
./.venv/bin/pip install ./backend

# rebuild the frontend (always safe):
( cd frontend && NITRO_PRESET=node-server \
    VITE_MEDRACK_API_BASE="${MEDRACK_API_BASE:-http://localhost:8010/api/v1}" \
    npm run build )

bash run.sh
```

Data in `MEDRACK_HOME` is preserved across updates. If a pipeline change bumps a
cache version, previously cached answers are treated as stale and regenerate on
the next solve.

---

## Logs

```bash
tail -f .run/api.log       # backend
tail -f .run/frontend.log  # frontend
```
Application logs (ingestion, generation) also appear in the **Logs** tab and
under `$MEDRACK_HOME/logs/`.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `run.sh`: "backend not installed" / "frontend not built" | Run `bash install.sh` first. |
| UI loads but every call fails | API not running, or the frontend was built with the wrong `MEDRACK_API_BASE`. Check `.run/api.log`; rebuild the frontend with the correct base URL. |
| Port already in use | Another service (or a previous MedRack) holds `8010`/`3010`. Change `API_PORT`/`FRONTEND_PORT` in `.env`, or stop the other service. |
| Answers never complete / time out | The LLM is unreachable or slow. Verify `MEDRACK_LLM_BASE_URL`, that the llama.cpp/Ollama server is up, and raise `MEDRACK_LLM_TIMEOUT`. |
| Gemini stops after ~20 answers | You're on `gemini-2.5-flash` (low free daily cap). Switch to `gemini-2.0-flash`. |
| Flowcharts don't render (blank/omitted) | `graphviz` isn't installed — `sudo apt-get install graphviz` (the `dot` command must be on PATH). |
| Scanned PDF ingests as empty | Tesseract OCR missing — `sudo apt-get install tesseract-ocr`. |
| Answers too short/long | Adjust the length boxes in the Workspace, or `THEORY_*_TARGET_WORDS` in `config.py`. |

---

## Backups

Everything worth keeping is under `MEDRACK_HOME` (default `~/medrack-data`):
the vector index, question banks, and cached answers. Back up that directory.
The repo itself is reproducible from git + `install.sh`.
