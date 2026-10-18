import json
import shutil
import subprocess
from pathlib import Path

NODE_EXECUTABLE = shutil.which("node")
HARNESS_PATH = Path(__file__).resolve().parent / "document-panel-harness.js"
FRAME_EDITOR_HARNESS_PATH = Path(__file__).resolve().parent / "page-frame-editor-harness.js"
LAST_SCAN_HARNESS_PATH = Path(__file__).resolve().parent / "last-scan-harness.js"
HARNESS_TIMEOUT_SECONDS = 30


def run_harness_scenarios(harness_path: Path, scenario_names: tuple[str, ...]) -> dict:
    completed = subprocess.run(
        [NODE_EXECUTABLE, str(harness_path), *scenario_names],
        capture_output=True,
        text=True,
        timeout=HARNESS_TIMEOUT_SECONDS,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def run_panel_scenarios(scenario_names: tuple[str, ...]) -> dict:
    return run_harness_scenarios(HARNESS_PATH, scenario_names)


def run_frame_editor_scenarios(scenario_names: tuple[str, ...]) -> dict:
    return run_harness_scenarios(FRAME_EDITOR_HARNESS_PATH, scenario_names)


def run_last_scan_scenarios(scenario_names: tuple[str, ...]) -> dict:
    return run_harness_scenarios(LAST_SCAN_HARNESS_PATH, scenario_names)
