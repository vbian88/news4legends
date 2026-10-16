#!/usr/bin/env python3
import json, math, os, shutil, sqlite3, statistics, subprocess, time
from pathlib import Path

ROOT = Path(os.environ.get("N4L_HEALTH_ROOT", "/var/lib/news4legends/health"))
ROOT.mkdir(parents=True, exist_ok=True)
DB = ROOT / "metrics.sqlite3"
NOW = int(time.time())
WINDOW = 30 * 86400
INTERVAL = 900
MIN_BASELINE = 96
METRICS = {}

def run(*args, timeout=12):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.stdout.strip() if p.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None

def metric(name, value):
    if value is not None and math.isfinite(float(value)):
        METRICS[name] = round(float(value), 4)

def proc_mem():
    data = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        data[key] = int(value.strip().split()[0])
    metric("memory.used_pct", 100 * (1 - data["MemAvailable"] / data["MemTotal"]))
    metric("memory.available_mb", data["MemAvailable"] / 1024)
    if data["SwapTotal"]:
        metric("swap.used_pct", 100 * (1 - data["SwapFree"] / data["SwapTotal"]))

def collect():
    proc_mem()
    disk = shutil.disk_usage("/")
    metric("disk.root.used_pct", 100 * disk.used / disk.total)
    metric("disk.root.free_gb", disk.free / 1024**3)
    stat = os.statvfs("/")
    metric("disk.root.inodes_used_pct", 100 * (1 - stat.f_favail / stat.f_files))
    metric("cpu.load_1m", os.getloadavg()[0])
    metric("cpu.load_5m", os.getloadavg()[1])
    metric("cpu.load_15m", os.getloadavg()[2])
    metric("host.uptime_hours", float(Path("/proc/uptime").read_text().split()[0]) / 3600)

    output = run("docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}")
    if output is None:
        metric("docker.query_ok", 0)
    else:
        metric("docker.query_ok", 1)
        containers = dict(line.split("|", 1) for line in output.splitlines() if "|" in line)
        required = tuple(filter(None, os.environ.get(
            "N4L_MONITORED_CONTAINERS", "news4legends-ui,news4legends-worker,n8n"
        ).split(",")))
        for name in required:
            status = containers.get(name, "")
            metric("container." + name + ".healthy",
                   int(status.startswith("Up") and "(unhealthy)" not in status))

    start = time.monotonic()
    worker_url = os.environ.get("NEWS4LEGENDS_WORKER_URL", "http://news4legends-worker:8080")
    response = run("wget", "-qO-", "-T", "5", worker_url.rstrip("/") + "/health")
    elapsed = (time.monotonic() - start) * 1000
    try:
        healthy = response is not None and json.loads(response).get("status") == "ok"
    except (ValueError, AttributeError):
        healthy = False
    metric("worker.available", int(healthy))
    if healthy:
        metric("worker.latency_ms", elapsed)

    log = Path(os.environ.get("N4L_BACKUP_LOG", "/var/lib/news4legends/backup/latest.log"))
    if log.exists():
        metric("backup.log_age_hours", (time.time() - log.stat().st_mtime) / 3600)
        metric("backup.success_marker", int("BACKUP SUCCESSFUL" in
               log.read_text(errors="replace")[-4000:]))
    else:
        metric("backup.log_present", 0)

def baseline(values):
    med = statistics.median(values)
    mad = statistics.median(abs(v - med) for v in values)
    return med, mad

def evaluate(db):
    events = []
    active = {}
    baseline_eligible = {}
    hard = {
        "disk.root.used_pct": (90, "above"),
        "memory.used_pct": (95, "above"),
        "docker.query_ok": (0.5, "below"),
        "worker.available": (0.5, "below"),
        "backup.log_age_hours": (216, "above"),
        "backup.success_marker": (0.5, "below"),
    }
    for key in METRICS:
        if key.startswith("container.") and key.endswith(".healthy"):
            hard[key] = (0.5, "below")

    for key, value in METRICS.items():
        rows = db.execute(
            """SELECT value FROM samples
               WHERE metric=? AND ts<? AND ts>=?
                 AND COALESCE(baseline_ok, 1)=1
               ORDER BY ts""",
            (key, NOW, NOW - WINDOW)
        ).fetchall()
        values = [r[0] for r in rows]
        med = mad = None
        if len(values) >= MIN_BASELINE:
            med, mad = baseline(values)

        rule = hard.get(key)
        failed = bool(rule and (
            value >= rule[0] if rule[1] == "above" else value < rule[0]
        ))
        adaptive = False
        if med is not None and key in (
            "memory.used_pct", "swap.used_pct",
            "disk.root.used_pct", "disk.root.free_gb",
            "cpu.load_1m", "cpu.load_5m", "cpu.load_15m",
            "worker.latency_ms"
        ):
            threshold = max(4 * 1.4826 * mad, abs(med) * 0.20, 0.5)
            adaptive = abs(value - med) > threshold

        abnormal = failed or adaptive
        baseline_eligible[key] = int(not abnormal)
        prior = db.execute(
            "SELECT streak,active FROM incidents WHERE metric=?", (key,)
        ).fetchone()
        previous = db.execute(
            "SELECT updated FROM incidents WHERE metric=?", (key,)
        ).fetchone()
        elapsed = NOW - previous[0] if previous else None
        consecutive = elapsed is not None and INTERVAL * 0.75 <= elapsed <= INTERVAL * 1.5
        was_active = bool(prior and prior[1])
        streak = (prior[0] + 1 if consecutive and prior else 1) if abnormal else (
            min(prior[0] - 1, -1) if consecutive and prior and prior[0] <= 0 else -1
        )
        is_active = failed or (adaptive and streak >= 4) or (
            was_active and (abnormal or streak > -2)
        )
        if is_active and not was_active:
            events.append({"type": "OPEN", "metric": key, "value": value})
        if was_active and not is_active and not abnormal:
            events.append({"type": "RECOVERED", "metric": key, "value": value})
        if is_active:
            active[key] = {"value": value, "baseline": med,
                           "mad": mad, "streak": streak,
                           "reason": "hard_limit" if failed else "persistent_drift"}
        for event in events:
            if event.get("metric") == key:
                db.execute(
                    """INSERT INTO incident_events
                       (ts,metric,event,value,baseline,mad,reason)
                       VALUES(?,?,?,?,?,?,?)""",
                    (NOW, key, event["type"], value, med, mad,
                     "hard_limit" if failed else "persistent_drift")
                )
        db.execute(
            """INSERT INTO incidents(metric,streak,active,updated)
               VALUES(?,?,?,?)
               ON CONFLICT(metric) DO UPDATE SET
               streak=excluded.streak,active=excluded.active,updated=excluded.updated""",
            (key, streak, int(is_active), NOW)
        )

    for key, value in METRICS.items():
        baseline_ok = baseline_eligible[key]
        db.execute(
            "INSERT INTO samples(ts,metric,value,baseline_ok) VALUES(?,?,?,?)",
            (NOW, key, value, baseline_ok)
        )
    db.execute("DELETE FROM samples WHERE ts<?", (NOW - WINDOW,))
    return active, events

def publish_snapshot(report):
    import tempfile
    directory = Path(os.environ.get("N4L_REPORT_DIR", str(ROOT / "public")))
    directory.mkdir(mode=0o755, parents=True, exist_ok=True)

    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as db:
        history = {}
        for name, ts, value in db.execute(
            "SELECT metric,ts,value FROM samples ORDER BY metric,ts"
        ):
            history.setdefault(name, []).append([ts, value])

        events = [
            dict(zip(
                ("timestamp", "metric", "event", "value", "baseline", "reason"),
                row
            ))
            for row in db.execute(
                """SELECT ts,metric,event,value,baseline,reason
                   FROM incident_events ORDER BY ts DESC LIMIT 200"""
            )
        ]

    payload = {
        "schema_version": 1,
        "generated_at": report["timestamp"],
        "metrics": report["metrics"],
        "active_incidents": report["active_incidents"],
        "incident_events": events,
        "history": history,
    }

    fd, temporary = tempfile.mkstemp(prefix=".snapshot-", dir=directory)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(payload, output, separators=(",", ":"))
            output.write(chr(10))
        os.chmod(temporary, 0o644)
        os.replace(temporary, directory / "system-health.json")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    ROOT.mkdir(mode=0o700, exist_ok=True)
    collect()
    with sqlite3.connect(DB, timeout=10) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("""CREATE TABLE IF NOT EXISTS samples(
                   ts INTEGER, metric TEXT, value REAL,
                   PRIMARY KEY(ts,metric))""")
        columns = {
            row[1] for row in db.execute("PRAGMA table_info(samples)")
        }
        if "baseline_ok" not in columns:
            db.execute(
                "ALTER TABLE samples ADD COLUMN baseline_ok INTEGER DEFAULT 1"
            )
        db.execute("""CREATE INDEX IF NOT EXISTS samples_lookup
                   ON samples(metric,ts)""")
        db.execute("""CREATE TABLE IF NOT EXISTS incident_events(
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   ts INTEGER NOT NULL,
                   metric TEXT NOT NULL,
                   event TEXT NOT NULL,
                   value REAL,
                   baseline REAL,
                   mad REAL,
                   reason TEXT)""")
        db.execute("""CREATE TABLE IF NOT EXISTS incidents(
                   metric TEXT PRIMARY KEY, streak INTEGER,
                   active INTEGER, updated INTEGER)""")
        active, events = evaluate(db)
        db.commit()
    report = {
        "timestamp": NOW, "baseline_samples_required": MIN_BASELINE,
        "metrics": METRICS, "active_incidents": active,
        "events": events, "notifications_sent": False
    }
    tmp = ROOT / "current.json.tmp"
    tmp.write_text(json.dumps(report, indent=2) + "\n")
    tmp.replace(ROOT / "current.json")
    publish_snapshot(report)
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
