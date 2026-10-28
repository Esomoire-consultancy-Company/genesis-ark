"""Run synthetic CI gates locally; no external dependencies or API calls."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
checks = [
    [sys.executable, str(root/'synthetic-baseline'/'verify.py')],
    [sys.executable, '-m', 'unittest', 'discover', '-s', str(root/'synthetic-baseline'), '-p', 'test_*.py', '-q'],
]
for command in checks:
    result = subprocess.run(command, cwd=root, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)
print('PASS: immutable synthetic fixture, localhost workbench contracts and no live operations')
