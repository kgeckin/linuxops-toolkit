# Upgrade from LinuxOps Toolkit V1 to V2 on Ubuntu WSL

This upgrade retains your virtual environment and the existing SQLite history. Do not erase `~/.local/share/linuxops/telemetry.db`.

## 1. Stop the running application

In the Ubuntu terminal where `linuxops serve` runs, press **Ctrl+C**.

## 2. Download the new ZIP on Windows

Download `LinuxOps_Toolkit_V2_Live.zip` from the ChatGPT message to your Windows Downloads folder.

## 3. Extract it on top of the existing project

In Ubuntu WSL:

```bash
cd ~/projects
python3 -m zipfile -e /mnt/c/Users/kgeck/Downloads/LinuxOps_Toolkit_V2_Live.zip .
cd ~/projects/linuxops-toolkit
```

If your Windows user folder name or ZIP download location differs, adjust the `/mnt/c/Users/.../Downloads/` path. The archive includes the root `linuxops-toolkit/` folder, so it safely replaces corresponding source files while keeping your local `.venv` and database.

## 4. Activate and reinstall the editable project

```bash
source .venv/bin/activate
python -m pip install -e .
linuxops --version
linuxops serve
```

Expected version: `0.2.0`.

## 5. Check live measurements

Open http://localhost:8765 and perform a hard refresh using **Ctrl+Shift+R**.

* The top bar should say **LIVE · 2 SEC** when connected.
* The CPU/Memory/Disk values update as measurements arrive.
* The Overview network panel shows download and upload rates in bytes per second.
* Select **History** to see saved data. Select **Live** to return to the high-frequency chart.
* The pause button stops *browser updates* while the server keeps recording for history.

For a one-second live update interval (higher overhead), stop the app and restart with:

```bash
LINUXOPS_LIVE_INTERVAL=1 LINUXOPS_RECORD_INTERVAL=30 linuxops serve
```

## Important measurement scope

This tool reads the running Ubuntu WSL Linux environment, not Windows Task Manager utilization or production storage arrays. Docker readings may reflect container limits. The data is real for the Linux environment where the collector runs.
