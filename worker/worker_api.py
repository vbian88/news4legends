import json
import subprocess

from preflight import preflight
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)


HOST = "0.0.0.0"
PORT = 8080

PROJECT_DIR = "/app"



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
                        "home-ai-news-worker"
                    ),
                },
            )
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
            command = [
                "python",
                "orchestrator.py",
            ]

            try:
                result = self.run_command(command, 3600)
            except subprocess.TimeoutExpired:
                self.send_json(
                    504,
                    {
                        "error": "orchestrator timed out",
                        "mode": "enabled_profiles",
                    },
                )
                return

            if result.returncode != 0:
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
                self.send_json(
                    500,
                    {
                        "error": "invalid orchestrator output",
                        "detail": str(exc),
                        "stderr": result.stderr,
                    },
                )
                return

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
        "home-ai-news-worker "
        f"listening on {HOST}:{PORT}"
    )

    server.serve_forever()


if __name__ == "__main__":
    main()
