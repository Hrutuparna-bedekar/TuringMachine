# Turing Machine Simulator

Design a machine, run it, and step through the tape and state diagram. The simulator accepts step limits from 0 to 1,000. The ML predictor estimates halting at 50, 200, and 1,000 steps. Use **Compare with exact simulation** to check a prediction.

## Launch on Windows

Install Python 3.13 and Node.js with npm. Open PowerShell in the repository root and run:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt -r backend/requirements-ml.txt
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). On later runs, double-click `run.bat` or rerun the last command. Press Ctrl+C in the launcher to stop the server.

For a quick test, load **Examples → Scan to Blank** and run the default input `101`. It halts at step 4.

## Run the tests

From the repository root, using the same virtual environment:

```powershell
.\.venv\Scripts\python.exe -m backend.experiments.generate_pilot
.\.venv\Scripts\python.exe -m backend.experiments.generate_pilot_v2
.\.venv\Scripts\python.exe -m pytest
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
```

The first two commands prepare the audit fixtures. The trained models ship in `models/final/`. See the [evaluation report](report/final/report.md) for accuracy and limitations.
