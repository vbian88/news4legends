import html
import json
import math
import os
import time
from datetime import datetime
from pathlib import Path

REPORTS = Path(os.environ.get("NEWS4LEGENDS_REPORT_DIR", "/security-reports"))
SNAPSHOT = REPORTS / "system-health.json"
WINDOW = 30 * 86400

def e(value):
    return html.escape(str(value), quote=True)

def fmt(value):
    return f"{value:,.2f}" if value is not None else "N/A"

def chart(name, current, samples):
    now = time.time()
    points = sorted(
        (float(t), float(v))
        for t, v in samples
        if isinstance(t, (int, float))
        and isinstance(v, (int, float))
        and math.isfinite(v)
        and now - WINDOW <= t <= now + 60
    )
    if not points:
        return f'<article class="metric"><h3>{e(name)}</h3><p>No historical samples</p></article>'

    values = [v for _, v in points]
    avg = sum(values) / len(values)
    low, high = min(values), max(values)
    pad = max((high - low) * .15, abs(avg) * .01, .01)
    bottom, top = low - pad, high + pad
    start, end = now - WINDOW, now

    def x(t):
        return 35 + 665 * (t - start) / (end - start)

    def y(v):
        return 170 - 135 * (v - bottom) / (top - bottom)

    coordinates = " ".join(
        f"{x(t):.1f},{y(v):.1f}" for t, v in points
    )
    average_y = y(avg)
    latest = float(current) if isinstance(current, (int, float)) else values[-1]
    coverage = (points[-1][0] - points[0][0]) / 86400
    binary = (
        name.startswith("container.")
        or name in ("docker.query_ok", "worker.available",
                    "backup.success_marker")
    )
    average_display = f"{avg * 100:.1f}% passing" if binary else fmt(avg)
    latest_display = "Healthy" if binary and latest == 1 else (
        "Failed" if binary else fmt(latest)
    )

    return f'''
    <article class="metric">
      <h3>{e(name)}</h3>
      <div class="stats">
        <span>Now <strong>{e(latest_display)}</strong></span>
        <span>30-day average <strong>{e(average_display)}</strong></span>
        <span>Min <strong>{fmt(low)}</strong></span>
        <span>Max <strong>{fmt(high)}</strong></span>
        <span>Samples <strong>{len(points)}</strong></span>
      </div>
      <svg viewBox="0 0 730 210" role="img"
           aria-label="Observed values and 30-day average for {e(name)}">
        <line x1="35" y1="170" x2="700" y2="170"
              stroke="#64748b" stroke-width="1"/>
        <line x1="35" y1="{average_y:.1f}" x2="700"
              y2="{average_y:.1f}" stroke="#d8ad62"
              stroke-width="2" stroke-dasharray="9 6"/>
        <polyline points="{coordinates}" fill="none"
                  stroke="#55c7b0" stroke-width="2.5"
                  stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="{x(points[-1][0]):.1f}"
                cy="{y(points[-1][1]):.1f}" r="4" fill="#55c7b0"/>
        <text x="35" y="193" fill="#aeb8c5" font-size="12">30 days ago</text>
        <text x="700" y="193" fill="#aeb8c5" font-size="12"
              text-anchor="end">Now</text>
      </svg>
      <p class="note">Rolling 30-day window · {coverage:.2f} days of observed history
      · partial baseline until 30 days collected</p>
    </article>'''


def security_monitoring():
    from datetime import datetime, timezone
    reports = REPORTS
    now = datetime.now(timezone.utc)

    def age(value):
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return max(0, int((now - timestamp).total_seconds() / 3600))
        except (ValueError, TypeError, AttributeError):
            return None

    av = reports / "clamav-current.json"
    if av.exists():
        try:
            result = json.loads(av.read_text())
            hours = age(result.get("timestamp"))
            av_text = (
                f"Status: {result.get('status', 'unknown')} | "
                f"Detections: {len(result.get('detections', []))} | "
                f"Last scan: {result.get('timestamp', 'unknown')} | "
                f"Age: {hours if hours is not None else '?'} hours"
            )
        except (ValueError, OSError, TypeError):
            av_text = "Report unreadable"
    else:
        av_text = "No scan report available"

    images = list((reports / "container-images").glob("*.json"))
    skipped = reports / "container-scan-skipped-images.txt"
    missing = (
        [line.strip() for line in skipped.read_text().splitlines()
         if line.strip()]
        if skipped.exists() else []
    )

    high = critical = 0
    latest = None
    for report in images:
        try:
            data = json.loads(report.read_text())
            timestamp = report.stat().st_mtime
            latest = max(latest or timestamp, timestamp)
            for result in data.get("Results", []):
                for vuln in result.get("Vulnerabilities") or []:
                    if vuln.get("Severity") == "HIGH":
                        high += 1
                    elif vuln.get("Severity") == "CRITICAL":
                        critical += 1
        except (OSError, ValueError, TypeError):
            continue

    coverage = "PARTIAL" if missing else (
        "COMPLETE" if images else "UNKNOWN"
    )
    scan_time = (
        datetime.fromtimestamp(latest, timezone.utc).isoformat()
        if latest else "Unavailable"
    )
    trivy_text = (
        f"Coverage: {coverage} | Scanned reports: {len(images)} | "
        f"Skipped images: {len(missing)} | HIGH: {high} | "
        f"CRITICAL: {critical} | Latest report: {scan_time}"
    )

    return (
        '<section><h2>Security monitoring</h2><div class="grid">'
        '<article class="metric"><h3>ClamAV</h3><p>'
        + e(av_text) +
        '</p></article><article class="metric"><h3>Trivy</h3><p>'
        + e(trivy_text) +
        '</p><p class="note">Partial coverage does not suppress '
        'security notifications. Findings are processed through '
        'the existing n8n Telegram integration.</p>'
        '</article></div></section>'
    )

def render():
    data = json.loads(SNAPSHOT.read_text())
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported snapshot version")

    metrics = data["metrics"]
    history = data["history"]
    age = max(0, int(time.time() - data["generated_at"]))
    incidents = data.get("active_incidents", {})
    stale = age > 1200

    status = (
        "DATA STALE" if stale else
        "ATTENTION REQUIRED" if incidents else
        "ALL SYSTEMS OPERATIONAL"
    )

    groups = {
        "CPU and memory": [
            "cpu.", "memory.", "swap."
        ],
        "Disk and host": [
            "disk.", "host."
        ],
        "Containers and Docker": [
            "container.", "docker."
        ],
        "Worker and backups": [
            "worker.", "backup."
        ],
    }

    sections = []
    for heading, prefixes in groups.items():
        charts = "".join(
            chart(name, metrics[name], history.get(name, []))
            for name in sorted(metrics)
            if any(name.startswith(prefix) for prefix in prefixes)
        )
        sections.append(f"<section><h2>{e(heading)}</h2><div class='grid'>{charts}</div></section>")

    return f'''<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>News 4 Legends · System Health</title>
<style>
body{{margin:0;background:#10151d;color:#f1e9d8;font:15px system-ui,sans-serif}}
main{{max-width:1500px;margin:auto;padding:28px 20px}}
h1,h2{{color:#d8ad62}}
a{{color:#d8ad62}}
header{{margin-bottom:24px}}
.banner,.metric{{background:#1b2430;border:1px solid #394354;border-radius:12px;padding:18px}}
.banner{{margin:18px 0 30px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,480px),1fr));gap:16px}}
.metric h3{{font-size:15px;color:#f1e9d8;overflow-wrap:anywhere}}
.stats{{display:flex;flex-wrap:wrap;gap:12px;font-size:12px;color:#aeb8c5}}
.stats strong{{color:#f1e9d8}}
svg{{display:block;width:100%;height:auto;margin-top:12px}}
.note{{font-size:12px;color:#aeb8c5}}
section{{margin-bottom:32px}}
</style></head><body><main>
<header><a href="/">← Profiles</a>
<h1>News 4 Legends · System Health</h1>
<p>22 monitored metrics · updated every 15 minutes · page refreshes every 5 minutes</p>
</header>
<div class="banner"><strong>{e(status)}</strong>
<p>Snapshot age: {age} seconds · Active incidents: {len(incidents)}</p>
<p><span style="color:#55c7b0">━━</span> Observed
&nbsp;&nbsp; <span style="color:#d8ad62">┄┄</span> Rolling 30-day average</p>
</div>
{''.join(sections)}
{security_monitoring()}
</main></body></html>'''
