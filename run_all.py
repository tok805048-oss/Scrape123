import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path

SCRIPTS = [
    "MerkurV1.py",
    "ObiV1.py",
    "KalcerV1.py",
    "SlovenijalesV1.py",
    "TehnolesV1.py",
    "ZagozenV1.py",
    "PilihBetonV1.py",
]

def write_progress(output_dir: str, summary: dict):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    with open(Path(output_dir) / "run_progress.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

def main() -> int:
    output_dir = os.environ.get("OUTPUT_DIR", "artifacts")
    os.environ["OUTPUT_DIR"] = output_dir

    # koliko minut max na posamezno skripto
    script_timeout_min = int(os.environ.get("SCRIPT_TIMEOUT_MIN", "45"))

    started = datetime.now()
    results = []

    summary = {
        "started": started.isoformat(),
        "script_timeout_min": script_timeout_min,
        "output_dir": output_dir,
        "results": results,
    }

    # naredi progress file že takoj
    write_progress(output_dir, summary)

    for script in SCRIPTS:
        t0 = datetime.now()
        print(f"\n=== Running: {script} (timeout {script_timeout_min} min) ===", flush=True)

        try:
            p = subprocess.run(
                [sys.executable, script],
                capture_output=True,
                text=True,
                timeout=script_timeout_min * 60,
            )
            status = "ok" if p.returncode == 0 else "error"
            result = {
                "script": script,
                "status": status,
                "returncode": p.returncode,
                "started": t0.isoformat(),
                "finished": datetime.now().isoformat(),
                "duration_sec": (datetime.now() - t0).total_seconds(),
                "stdout_tail": p.stdout[-4000:],
                "stderr_tail": p.stderr[-4000:],
            }

        except subprocess.TimeoutExpired as e:
            result = {
                "script": script,
                "status": "timeout",
                "returncode": None,
                "started": t0.isoformat(),
                "finished": datetime.now().isoformat(),
                "duration_sec": (datetime.now() - t0).total_seconds(),
                "stdout_tail": (e.stdout or "")[-4000:] if hasattr(e, "stdout") else "",
                "stderr_tail": (e.stderr or "")[-4000:] if hasattr(e, "stderr") else "",
            }
            print(f"!!! TIMEOUT: {script}", flush=True)

        results.append(result)
        summary["results"] = results
        write_progress(output_dir, summary)

    finished = datetime.now()
    final = {
        "started": started.isoformat(),
        "finished": finished.isoformat(),
        "duration_sec": (finished - started).total_seconds(),
        "script_timeout_min": script_timeout_min,
        "output_dir": output_dir,
        "results": results,
    }

    with open(Path(output_dir) / "run_summary.json", "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    any_bad = any(r["status"] in ("error", "timeout") for r in results)
    return 1 if any_bad else 0

if __name__ == "__main__":
    raise SystemExit(main())
