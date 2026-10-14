import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which('node') is None, reason='Node is needed for browser-script unit regressions')
def test_auth_browser_regressions():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(['node', '--test', str(root / 'tests/browser/auth-regression.cjs')],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
