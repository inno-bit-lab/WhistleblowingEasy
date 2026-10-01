"""Retry an audit only when Chrome failed to record its navigation trace."""
import json
from pathlib import Path
import subprocess
import sys


def audit(arguments, run=subprocess.run):
    prefix = next(arg.split("=", 1)[1] for arg in arguments if arg.startswith("--output-path="))
    report = Path(prefix + ".report.json")
    for attempt in range(1, 4):
        # Do not mistake a report from a previous attempt for the current result.
        report.unlink(missing_ok=True)
        result = run(["npx", "lighthouse", *arguments])
        if result.returncode == 0:
            return 0
        try:
            error = json.loads(report.read_text()).get("runtimeError", {}).get("code")
        except (OSError, ValueError, AttributeError):
            error = None
        if error != "NO_NAVSTART" or attempt == 3:
            return result.returncode
        print(f"Chrome navigation trace missing; retrying Lighthouse ({attempt}/2).", flush=True)
        for extension in ("json", "html"):
            artifact = Path(prefix + ".report." + extension)
            if artifact.exists():
                artifact.rename(Path(prefix + f".attempt-{attempt}.report." + extension))
    return 1


if __name__ == "__main__":
    sys.exit(audit(sys.argv[1:]))
