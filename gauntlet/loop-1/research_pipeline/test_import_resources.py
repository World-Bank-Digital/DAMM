"""Worker entry-point imports must release file and temporary resources."""

import os
from pathlib import Path
import subprocess
import sys
import unittest


class ImportResourceTest(unittest.TestCase):
    def test_stage_imports_and_legacy_fixtures_close_their_resources(self):
        script = """
import sys
def deny_network(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo', 'socket.sendto'):
        raise RuntimeError('offline resource check forbids network')
sys.addaudithook(deny_network)
import vendors, gates, diagnostic, research_orchestrator, scans, generate_dar
import test_gates, test_generate_dar
"""
        result = subprocess.run(
            [sys.executable, "-Walways::ResourceWarning", "-c", script],
            cwd=Path(__file__).parent,
            env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True, text=True, timeout=45,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertNotIn("ResourceWarning", result.stderr)
