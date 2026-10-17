import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "maintenance"))
sys.path.insert(0, str(ROOT / "ui"))

from vulnerability_report import build, remediation_prompt, update_history
import health_charts


class Receiver(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.__class__.received.append(json.loads(body))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *_args):
        pass


class SecurityMonitoringTests(unittest.TestCase):
    def test_inventory_history_and_remediation(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "trivy.json"
            source.write_text(json.dumps({"Results": [{
                "Target": "debian",
                "Vulnerabilities": [
                    {"Severity": "CRITICAL", "PkgName": "openssl",
                     "VulnerabilityID": "CVE-TEST-1", "InstalledVersion": "1",
                     "FixedVersion": "2", "PrimaryURL": "https://example.invalid/1"},
                    {"Severity": "LOW", "PkgName": "libexample",
                     "VulnerabilityID": "CVE-TEST-2", "InstalledVersion": "3"},
                ],
            }]}))
            inventory = build([source], "debian")
            self.assertEqual(1, inventory["counts"]["CRITICAL"])
            self.assertEqual(1, inventory["counts"]["LOW"])
            history = directory / "history.json"
            update_history(history, inventory)
            update_history(history, inventory)
            self.assertEqual(2, len(json.loads(history.read_text())["items"]))
            prompt = remediation_prompt({}, inventory)
            self.assertIn("openssl | CVE-TEST-1 | installed=1 | fixed=2", prompt)
            self.assertIn("Do not upgrade automatically", prompt)

    def test_system_health_renders_when_ctem_data_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            snapshot = directory / "system-health.json"
            snapshot.write_text(json.dumps({
                "schema_version": 1,
                "generated_at": __import__("time").time(),
                "metrics": {"cpu.used_pct": 10.0},
                "history": {"cpu.used_pct": [[__import__("time").time(), 10.0]]},
                "active_incidents": {},
            }))
            original_reports, original_snapshot = health_charts.REPORTS, health_charts.SNAPSHOT
            health_charts.REPORTS, health_charts.SNAPSHOT = directory, snapshot
            try:
                page = health_charts.render()
            finally:
                health_charts.REPORTS, health_charts.SNAPSHOT = original_reports, original_snapshot
            self.assertIn("Vulnerability Trends (CTEM)", page)
            self.assertIn("No historical snapshots available", page)

    def test_security_webhook_deduplicates_identical_event(self):
        Receiver.received = []
        server = HTTPServer(("127.0.0.1", 0), Receiver)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                env = os.environ.copy()
                env["NEWS4LEGENDS_MAINTENANCE_ROOT"] = directory
                env["N4L_SECURITY_WEBHOOK_URL"] = (
                    f"http://127.0.0.1:{server.server_port}/security"
                )
                payload = json.dumps({"items": [{
                    "identity": "openssl:CVE-TEST-1",
                    "message": "CRITICAL test finding",
                }]})
                command = [sys.executable, str(ROOT / "maintenance" / "send_security_event.py"), "test"]
                for _ in range(2):
                    subprocess.run(
                        command, input=payload, text=True, env=env,
                        check=True, capture_output=True,
                    )
            self.assertEqual(1, len(Receiver.received))
            self.assertEqual("CRITICAL test finding", Receiver.received[0]["message"])
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
