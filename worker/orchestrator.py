#!/usr/bin/env python3

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path("/app")
DATA_DIR = Path("/data")
PROFILE_DB = "/config/home-ai-news.db"
COLLECTOR_CONFIG = "/config/collector.yaml"


def enabled_profiles():
    db = sqlite3.connect(PROFILE_DB)
    try:
        rows = db.execute(
            """
            SELECT slug
            FROM profiles
            WHERE enabled = 1
            ORDER BY id
            """
        ).fetchall()
    finally:
        db.close()

    return [row[0] for row in rows]


def run(command, timeout):
    return subprocess.run(
        command,
        cwd=PROJECT_DIR,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def main():
    parser = argparse.ArgumentParser(
        description="News 4 Legends enabled-profile orchestrator"
    )
    parser.add_argument(
        "--profile",
        help="Optional single-profile override for diagnostics",
    )
    args = parser.parse_args()

    profiles = (
        [args.profile.strip()]
        if args.profile
        else enabled_profiles()
    )

    if not profiles:
        print("No enabled News 4 Legends profiles.")
        return

    telegram_digests = []
    email_digests = []

    for profile in profiles:
        if not profile or not all(
            char.isalnum() or char in "_-"
            for char in profile
        ):
            raise SystemExit(f"Invalid profile slug: {profile!r}")

        print(f"PROCESSING: {profile}", file=sys.stderr, flush=True)

        articles_path = DATA_DIR / f"{profile}_articles.json"

        collector = run(
            [
                "python",
                "collector.py",
                "--profile",
                profile,
                "--config",
                COLLECTOR_CONFIG,
                "--output",
                str(articles_path),
            ],
            timeout=300,
        )

        sys.stderr.write(collector.stdout)
        sys.stderr.write(collector.stderr)

        if collector.returncode != 0:
            raise SystemExit(collector.returncode)

        if not articles_path.exists():
            raise SystemExit(
                f"Collector output missing: {articles_path}"
            )

        try:
            articles = json.loads(
                articles_path.read_text(encoding="utf-8")
            )
        except Exception as exc:
            raise SystemExit(
                f"Invalid collector output for {profile}: {exc}"
            )

        print(
            f"{profile}: collected {len(articles)} article(s)",
            file=sys.stderr,
            flush=True,
        )

        pipeline = run(
            [
                "python",
                "news_pipeline.py",
                str(articles_path),
                "--profile",
                profile,
                "--profile-db",
                PROFILE_DB,
                "--llm",
                "--delivery-bundle",
            ],
            timeout=600,
        )

        sys.stderr.write(pipeline.stderr)

        if pipeline.returncode != 0:
            raise SystemExit(pipeline.returncode)

        try:
            bundle = json.loads(pipeline.stdout)
        except json.JSONDecodeError as exc:
            raise SystemExit(
                f"Invalid delivery bundle for {profile}: {exc}"
            )

        telegram_digest = str(
            bundle.get("telegram", "")
        ).strip()
        email_digest = str(
            bundle.get("email", "")
        ).strip()

        if telegram_digest:
            telegram_digests.append(telegram_digest)

        if email_digest:
            email_digests.append(email_digest)

    # Telegram allows 4096 characters. Keep deliberate
    # headroom for downstream formatting/escaping.
    max_digest_chars = 4000
    separator = "\n\n"
    telegram_output = ""

    if telegram_digests:
        separator_chars = (
            len(separator)
            * (len(telegram_digests) - 1)
        )
        content_budget = (
            max_digest_chars - separator_chars
        )

        allocations = [0] * len(telegram_digests)
        remaining = set(
            range(len(telegram_digests))
        )
        remaining_budget = content_budget

        while remaining and remaining_budget > 0:
            share = max(
                1,
                remaining_budget // len(remaining),
            )
            completed = []

            for index in remaining:
                needed = len(
                    telegram_digests[index]
                )

                if needed <= share:
                    allocations[index] = needed
                    remaining_budget -= needed
                    completed.append(index)

            if not completed:
                for index in remaining:
                    allocations[index] = share

                remaining_budget -= (
                    share * len(remaining)
                )

                for index in sorted(remaining):
                    if remaining_budget <= 0:
                        break
                    allocations[index] += 1
                    remaining_budget -= 1

                break

            for index in completed:
                remaining.remove(index)

        rendered = []

        for digest, allocation in zip(
            telegram_digests,
            allocations,
        ):
            if len(digest) <= allocation:
                rendered.append(digest)
                continue

            marker = "\n…"
            keep = max(
                0,
                allocation - len(marker),
            )
            rendered.append(
                digest[:keep].rstrip() + marker
            )

        telegram_output = separator.join(
            rendered
        )

        if len(telegram_output) > max_digest_chars:
            raise RuntimeError(
                "Internal Telegram digest budget exceeded: "
                f"{len(telegram_output)} > "
                f"{max_digest_chars}"
            )

    email_output = separator.join(email_digests)

    # stdout is machine-readable for worker_api/n8n.
    print(json.dumps({
        "telegram": telegram_output,
        "email": email_output,
        "profiles_processed": len(profiles),
    }))


if __name__ == "__main__":
    main()
