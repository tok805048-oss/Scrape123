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
    # kasneje dodaš še: "ZagozenV1.py", ...
]

def main() -> int:
    output_dir = os.environ.get("OUTPUT_DIR", "artifacts")
    os.environ["OUTPUT_DIR"] = output_dir  # prenese se tudi v subprocess

    started = datetime.now()
    results = []

    for script in SCRIPTS:
        print(f"\n=== Running: {script} ===")
        p = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
        )
        results.append({
            "script": script,
            "returncode": p.returncode,
            "stdout_tail": p.stdout[-4000:],
            "stderr_tail": p.stderr[-4000:],
        })
        if p.returncode != 0:
            print(f"!!! FAILED: {script} (rc={p.returncode})")
            print(p.stderr[-2000:])

    finished = datetime.now()

    summary = {
        "started": started.isoformat(),
        "finished": finished.isoformat(),
        "duration_sec": (finished - started).total_seconds(),
        "output_dir": output_dir,
        "results": results,
    }

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    with open(Path(output_dir) / "run_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Fail CI, če je katera skripta padla (ampak artefakte bomo vseeno uploadali z if: always()).
    any_failed = any(r["returncode"] != 0 for r in results)
    return 1 if any_failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
