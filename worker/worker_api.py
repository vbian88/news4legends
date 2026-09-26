import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from preflight import preflight
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)


HOST = "0.0.0.0"
PORT = 8080

PROJECT_DIR = "/app"
LOG_DIR = Path(os.environ.get("LOG_DIR", "/data/logs"))
LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "7"))


def prune_run_logs():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now(timezone.utc) - timedelta(
        days=LOG_RETENTION_DAYS
    )
    for path in LOG_DIR.glob("run-*.txt"):
        modified = datetime.fromtimestamp(
            path.stat().st_mtime,
            tz=timezone.utc,
        )
        if modified < cutoff:
            path.unlink()


def new_run_log():
    prune_run_logs()
    stamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S.%fZ"
    )
    return LOG_DIR / f"run-{stamp}.txt"


def write_run_log(path, message):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message.rstrip()}\n")


def latest_run_log():
    prune_run_logs()
    logs = sorted(
        LOG_DIR.glob("run-*.txt"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return logs[0] if logs else None



class RequestHandler(
    BaseHTTPRequestHandler
):
    def send_json(
        self,
        status_code,
        payload,
    ):
        body = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        self.send_response(
            status_code
        )

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )

        self.send_header(
            "Content-Length",
            str(len(body)),
        )

        self.end_headers()

        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.send_json(
                200,
                {
                    "status": "ok",
                    "service": (
                        "news4legends-worker"
                    ),
                },
            )
            return

        if self.path == "/logs":
            path = latest_run_log()
            if path is None:
                self.send_json(404, {"error": "no run logs available"})
                return

            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{path.name}"',
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_json(
            404,
            {
                "error": "not found"
            },
        )

    def run_command(
        self,
        command,
        timeout,
    ):
        return subprocess.run(
            command,
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def do_POST(self):
        if self.path == "/preflight":
            try:
                content_length = int(
                    self.headers.get(
                        "Content-Length",
                        "0",
                    )
                )
                body = self.rfile.read(
                    content_length
                )
                request = json.loads(
                    body.decode("utf-8")
                )
                listing_url = request.get(
                    "listing_url",
                    ""
                ).strip()
            except (
                ValueError,
                UnicodeDecodeError,
                json.JSONDecodeError,
            ):
                self.send_json(
                    400,
                    {"error": "invalid JSON request"},
                )
                return

            if not listing_url.startswith(
                ("http://", "https://")
            ):
                self.send_json(
                    400,
                    {
                        "error": (
                            "listing_url must be "
                            "http:// or https://"
                        )
                    },
                )
                return

            result = preflight(
                listing_url
            )

            self.send_json(
                200,
                result,
            )
            return

        if self.path == "/run":
            log_path = new_run_log()
            write_run_log(
                log_path,
                "News 4 Legends run started; mode=enabled_profiles",
            )
            command = [
                "python",
                "orchestrator.py",
            ]

            try:
                result = self.run_command(command, 3600)
            except subprocess.TimeoutExpired:
                write_run_log(log_path, "Run timed out after 3600 seconds")
                self.send_json(
                    504,
                    {
                        "error": "orchestrator timed out",
                        "mode": "enabled_profiles",
                    },
                )
                return

            if result.returncode != 0:
                write_run_log(
                    log_path,
                    f"Run failed; return_code={result.returncode}",
                )
                if result.stderr.strip():
                    write_run_log(log_path, result.stderr)
                self.send_json(
                    500,
                    {
                        "mode": "enabled_profiles",
                        "return_code": result.returncode,
                        "stderr": result.stderr,
                    },
                )
                return

            try:
                delivery = json.loads(
                    result.stdout
                )
            except json.JSONDecodeError as exc:
                write_run_log(
                    log_path,
                    f"Invalid orchestrator output: {exc}",
                )
                if result.stderr.strip():
                    write_run_log(log_path, result.stderr)
                self.send_json(
                    500,
                    {
                        "error": "invalid orchestrator output",
                        "detail": str(exc),
                        "stderr": result.stderr,
                    },
                )
                return

            if result.stderr.strip():
                write_run_log(log_path, result.stderr)
            write_run_log(
                log_path,
                "Run completed successfully; return_code=0; "
                f"profiles_processed={delivery.get('profiles_processed', 0)}",
            )

            self.send_json(
                200,
                {
                    "mode": "enabled_profiles",
                    "return_code": 0,
                    "profiles_processed": delivery.get(
                        "profiles_processed",
                        0,
                    ),
                    "telegram": delivery.get(
                        "telegram",
                        "",
                    ),
                    "email": delivery.get(
                        "email",
                        "",
                    ),
                    "stderr": result.stderr,
                },
            )
            return

        self.send_json(
            404,
            {
                "error": "not found"
            },
        )

    def log_message(
        self,
        format,
        *args,
    ):
        print(
            "%s - %s"
            % (
                self.address_string(),
                format % args,
            )
        )


def main():
    server = ThreadingHTTPServer(
        (HOST, PORT),
        RequestHandler,
    )

    print(
        "news4legends-worker "
        f"listening on {HOST}:{PORT}"
    )

    server.serve_forever()


if __name__ == "__main__":
    main()
