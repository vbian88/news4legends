#!/usr/bin/env python3
import json, os, re, subprocess
from pathlib import Path
from collections import defaultdict

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("NEWS4LEGENDS_MAINTENANCE_ROOT", SCRIPT_DIR))
REPORTS = Path(os.environ.get(
    "NEWS4LEGENDS_MAINTENANCE_REPORTS_DIR", ROOT / "reports"
))
STATE = Path(os.environ.get(
    "NEWS4LEGENDS_MAINTENANCE_STATE_DIR", ROOT / "state"
))
CONFIG_PATH = Path(os.environ.get(
    "NEWS4LEGENDS_MAINTENANCE_CONFIG", ROOT / "config.json"
))
if not CONFIG_PATH.exists():
    CONFIG_PATH = SCRIPT_DIR / "config.example.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
DATA = json.loads((STATE / "advisories.json").read_text(encoding="utf-8"))

def docker_version(container, command, pattern=r"(\d+(?:\.\d+){1,3})"):
    result = subprocess.run(
        ["docker", "exec", container, *command],
        text=True,
        capture_output=True,
        timeout=15,
    )
    text = (result.stdout + "\\n" + result.stderr).strip()
    if result.returncode != 0:
        raise RuntimeError(
            f"Cannot determine installed version for {container}: {text}"
        )
    match = re.search(pattern, text)
    if not match:
        raise RuntimeError(
            f"Cannot parse installed version for {container}: {text}"
        )
    return match.group(1)

INSTALLED = {}
DISCOVERY_ERRORS = []
for service, cfg in CONFIG.get("services", {}).items():
    if not cfg.get("enabled", True):
        continue
    try:
        INSTALLED[service] = docker_version(
            cfg["container"], cfg["version_command"]
        )
    except Exception as exc:
        DISCOVERY_ERRORS.append(f"{service}: {exc}")

def ver(s):
    s = str(s).strip().lower().lstrip("v")
    m = re.match(r"(\d+(?:\.\d+){0,3})", s)
    return tuple(map(int, m.group(1).split("."))) if m else None

def vc(a,b):
    a,b=ver(a),ver(b)
    if a is None or b is None: return None
    n=max(len(a),len(b))
    a+=((0,)*(n-len(a))); b+=((0,)*(n-len(b)))
    return (a>b)-(a<b)

def simple_range(version, expr):
    e=(expr or "").strip().lower().replace("&&",",")
    if e=="*": return None

    m=re.fullmatch(r"\s*v?([\d.]+)\s*-\s*v?([\d.]+)\s*",e)
    if m:
        return vc(version,m.group(1))>=0 and vc(version,m.group(2))<=0

    results=[]
    for part in [x.strip() for x in e.split(",") if x.strip()]:
        m=re.fullmatch(r"(>=|<=|>|<|=)?\s*v?([\d.]+)",part)
        if not m: return None
        op,target=m.group(1) or "=",m.group(2)
        c=vc(version,target)
        if c is None: return None
        results.append({">=":c>=0,"<=":c<=0,">":c>0,"<":c<0,"=":c==0}[op])
    return all(results) if results else None

def patched_on_branch(installed, patched):
    """
    GitHub advisories may publish parallel maintained branches, e.g.
    1.123.61 / 2.27.4 / 2.28.1.  If installed is on the same major/minor
    branch and >= that branch's patched release, it is patched.
    """
    iv=ver(installed)
    if not iv or len(iv)<2: return False
    for token in re.findall(r"(?:>=\s*)?v?(\d+(?:\.\d+){1,3})", patched or ""):
        pv=ver(token)
        if pv and len(pv)>=2 and iv[:2]==pv[:2] and vc(installed,token)>=0:
            return True
    return False

findings=[]
uncertain=[]

for service,installed in INSTALLED.items():
    iv=ver(installed)
    installed_branch=iv[:2] if iv and len(iv)>=2 else None

    for a in DATA.get(service,[]):
        vulnerabilities=a.get("vulnerabilities") or []

        # Collect explicitly published patched release branches.
        patch_branches=set()
        same_branch_patch=False

        for v in vulnerabilities:
            patched=v.get("patched_versions") or ""
            for token in re.findall(
                r"(?:>=\s*)?v?(\d+(?:\.\d+){1,3})",
                patched
            ):
                pv=ver(token)
                if pv and len(pv)>=2:
                    patch_branches.add(pv[:2])
                    if installed_branch == pv[:2]:
                        if vc(installed,token) >= 0:
                            same_branch_patch=True

        # An explicit fixed release on our branch is authoritative.
        if same_branch_patch:
            continue

        applicable=[]
        ambiguous=[]

        # Multiple maintained branches, but no published fix metadata for
        # our installed branch: don't project another branch's "< X" range
        # backwards onto ours. Require manual review.
        parallel_branches = len(patch_branches) > 1
        missing_our_branch = (
            parallel_branches
            and installed_branch not in patch_branches
        )

        for v in vulnerabilities:
            rng=v.get("vulnerable_version_range") or ""
            patched=v.get("patched_versions") or ""

            if missing_our_branch:
                ambiguous.append(
                    f"{rng or 'unstructured range'} "
                    f"(published patch: {patched or 'none'})"
                )
                continue

            result=simple_range(installed,rng)

            if result is True:
                applicable.append({
                    "range":rng,
                    "patched":patched or "not published"
                })
            elif result is None:
                ambiguous.append(rng or "unstructured range")

        if applicable:
            findings.append({
                "service":service,
                "installed":installed,
                "severity":(a.get("severity") or "unknown").upper(),
                "id":a.get("cve_id") or a.get("ghsa_id"),
                "summary":a.get("summary") or "",
                "url":a.get("html_url") or "",
                "matches":applicable,
            })
        elif ambiguous:
            uncertain.append(
                f"UNCERTAIN: {service} {installed}: "
                f"{a.get('cve_id') or a.get('ghsa_id')} "
                f"requires manual applicability review: "
                + "; ".join(ambiguous)
            )

rank={"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3,"UNKNOWN":4}
findings.sort(key=lambda x:(rank.get(x["severity"],4),x["service"],x["id"] or ""))

out=["NEWS 4 LEGENDS - VERIFIED VERSION FINDINGS",""]

for f in findings:
    out += [
        f'{f["severity"]}: {f["service"]} {f["installed"]}',
        f'Advisory: {f["id"]}',
        f'Summary: {f["summary"]}',
    ]
    for m in f["matches"]:
        out.append(f'Affected: {m["range"]} | Patched: {m["patched"]}')
    out += [f'Official advisory: {f["url"]}',""]

if not findings:
    out += ["No confirmed installed-version matches.",""]

if uncertain:
    out += ["=== MANUAL REVIEW ===",*uncertain,""]

if DISCOVERY_ERRORS:
    out += ["=== VERSION DISCOVERY ERRORS ===", *DISCOVERY_ERRORS, ""]

REPORTS.mkdir(parents=True, exist_ok=True)
p=REPORTS/"actionable.txt"
p.write_text("\n".join(out))
print(p.read_text())

counts=defaultdict(int)
for f in findings:
    counts[f["severity"]]+=1

from datetime import datetime, timezone
now=datetime.now(timezone.utc)
snapshot={
    "generated_at": now.isoformat(),
    "installed": INSTALLED,
    "counts": {
        "total": len(findings),
        "critical": counts["CRITICAL"],
        "high": counts["HIGH"],
        "medium": counts["MEDIUM"],
        "low": counts["LOW"],
        "uncertain": len(uncertain),
    },
    "findings": findings,
    "manual_review": uncertain,
    "version_discovery_errors": DISCOVERY_ERRORS,
}

history_dir=REPORTS/"history"
history_dir.mkdir(parents=True,exist_ok=True)

current=REPORTS/"current.json"
current.write_text(json.dumps(snapshot,indent=2)+"\n")

history=history_dir/f'{now.strftime("%Y%m%dT%H%M%SZ")}.json'
history.write_text(json.dumps(snapshot,indent=2)+"\n")

# Keep 90 most recent snapshots.
snapshots=sorted(history_dir.glob("*.json"),reverse=True)
for old_snapshot in snapshots[90:]:
    old_snapshot.unlink()

print("\n=== RESULT ===")
print("TOTAL_CONFIRMED="+str(len(findings)))
for severity in ("CRITICAL","HIGH","MEDIUM","LOW"):
    print(f"{severity}={counts[severity]}")
print("UNCERTAIN="+str(len(uncertain)))
