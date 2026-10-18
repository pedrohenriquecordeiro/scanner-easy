import json
import shutil
import subprocess
from pathlib import Path

NODE_EXECUTABLE = shutil.which("node")
POLICY_HARNESS_PATH = Path(__file__).resolve().parent / "document-page-policy-harness.js"
POLICY_HARNESS_TIMEOUT_SECONDS = 30


def evaluate_policy_expressions(expressions: list[str]) -> dict:
    completed = subprocess.run(
        [NODE_EXECUTABLE, str(POLICY_HARNESS_PATH)],
        input=json.dumps(expressions),
        capture_output=True,
        text=True,
        timeout=POLICY_HARNESS_TIMEOUT_SECONDS,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)
