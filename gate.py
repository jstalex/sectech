import json, sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())
levels = json.loads(Path(__file__).with_name("severity.json").read_text())
summary = report["summary"]
if summary.get("parsing_errors", 0) or not summary.get("resource_count", 0):
    raise SystemExit("ERROR: incomplete scan")
blocked = []
for item in report["results"]["failed_checks"]:
    level = levels.get(item["check_id"], "UNKNOWN")
    if level in ("HIGH", "CRITICAL", "UNKNOWN"):
        blocked.append((item["check_id"], item["resource"], level))
for item in blocked:
    print(*item)
print(f"Quality Gate: {'BLOCK' if blocked else 'PASS'}; blocking={len(blocked)}")
sys.exit(1 if blocked else 0)
