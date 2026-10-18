import json
import shutil
import subprocess
from pathlib import Path

NODE_EXECUTABLE = shutil.which("node")
HARNESS_PATH = Path(__file__).resolve().parent / "document-panel-harness.js"
HARNESS_TIMEOUT_SECONDS = 30


def run_panel_scenarios(scenario_names: tuple[str, ...]) -> dict:
    completed = subprocess.run(
        [NODE_EXECUTABLE, str(HARNESS_PATH), *scenario_names],
        capture_output=True,
        text=True,
        timeout=HARNESS_TIMEOUT_SECONDS,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)
