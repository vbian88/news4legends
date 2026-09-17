import json
import sys
import time

import requests

from collector import (
    discover_links,
    extract_article,
    fetch,
)


MAX_CANDIDATES = 40
SAMPLE_FETCHES = 3
REQUEST_TIMEOUT = 15

USER_AGENT = "HomeAI-News/0.1 (+personal research collector)"


def preflight(listing_url):
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,"
            "application/xhtml+xml,"
            "application/xml;q=0.9,"
            "*/*;q=0.8"
        ),
    })

    started = time.monotonic()

    try:
        listing_started = time.monotonic()
        listing_html = fetch(
            session,
            listing_url,
            REQUEST_TIMEOUT,
        )
        listing_seconds = (
            time.monotonic() - listing_started
        )
    except requests.RequestException as exc:
        return {
            "status": "FAIL",
            "reason": "listing request failed",
            "error": str(exc),
        }

    candidates = discover_links(
        listing_html,
        listing_url,
        MAX_CANDIDATES,
    )

    if not candidates:
        return {
            "status": "FAIL",
            "reason": "no candidate article links discovered",
            "listing_seconds": round(listing_seconds, 3),
            "candidates": 0,
        }

    sample = candidates[:SAMPLE_FETCHES]

    fetched = 0
    extracted = 0
    failures = []

    for candidate in sample:
        url = candidate["url"]

        try:
            article_html = fetch(
                session,
                url,
                REQUEST_TIMEOUT,
            )
            fetched += 1
        except requests.RequestException as exc:
            failures.append({
                "url": url,
                "reason": f"request failed: {exc}",
            })
            continue

        article = extract_article(
            article_html,
            url,
        )

        if article is None:
            failures.append({
                "url": url,
                "reason": "extraction failed",
            })
            continue

        extracted += 1

    total_seconds = time.monotonic() - started

    if extracted == 0:
        status = "FAIL"
        reason = "sample article extraction failed"
    elif extracted < len(sample):
        status = "WARNING"
        reason = "partial sample extraction success"
    elif len(candidates) >= MAX_CANDIDATES:
        status = "WARNING"
        reason = "candidate discovery reached pre-flight limit"
    else:
        status = "PASS"
        reason = "source passed bounded pre-flight"

    return {
        "status": status,
        "reason": reason,
        "listing_seconds": round(listing_seconds, 3),
        "total_seconds": round(total_seconds, 3),
        "candidates": len(candidates),
        "candidate_limit_reached": (
            len(candidates) >= MAX_CANDIDATES
        ),
        "sample_requested": len(sample),
        "sample_fetched": fetched,
        "sample_extracted": extracted,
        "failures": failures,
        "limits": {
            "max_candidates": MAX_CANDIDATES,
            "sample_fetches": SAMPLE_FETCHES,
            "request_timeout_seconds": REQUEST_TIMEOUT,
        },
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: preflight.py LISTING_URL"
        )

    print(
        json.dumps(
            preflight(sys.argv[1]),
            ensure_ascii=False,
            indent=2,
        )
    )
