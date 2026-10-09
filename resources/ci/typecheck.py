"""Pyright error gate: fails only when a (file, rule) error count exceeds the committed baseline."""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASELINE = os.path.join(ROOT, "resources", "ci", "pyright_baseline.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--pyright", default=os.environ.get("PYRIGHT") or "pyright")
    args = ap.parse_args()

    proc = subprocess.run([args.pyright, "--outputjson"], cwd=ROOT, capture_output=True, text=True)
    try:
        report = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        sys.stderr.write(proc.stderr)
        print("pyright: stdout is not JSON", file=sys.stderr)
        return 2

    diags = {}
    counts = {}
    for d in report.get("generalDiagnostics", []):
        if d.get("severity") != "error":
            continue
        rel = os.path.relpath(d["file"], ROOT).replace(os.sep, "/")
        rule = d.get("rule") or "none"
        diags.setdefault((rel, rule), []).append(d)
        counts.setdefault(rel, {})
        counts[rel][rule] = counts[rel].get(rule, 0) + 1

    if args.update:
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump({k: dict(sorted(v.items())) for k, v in sorted(counts.items())}, f, indent=2)
            f.write("\n")
        print(f"pyright: baseline written ({sum(sum(v.values()) for v in counts.values())} errors)")
        return 0

    if not os.path.exists(BASELINE):
        print("pyright: no baseline at resources/ci/pyright_baseline.json; run with --update", file=sys.stderr)
        return 2

    with open(BASELINE, encoding="utf-8") as f:
        base = json.load(f)

    regressed = []
    for rel, rules in sorted(counts.items()):
        for rule, n in sorted(rules.items()):
            if n > base.get(rel, {}).get(rule, 0):
                regressed.append((rel, rule))

    for rel, rule in regressed:
        for d in diags[(rel, rule)]:
            line = d["range"]["start"]["line"] + 1
            col = d["range"]["start"]["character"] + 1
            msg = d["message"].split("\n", 1)[0]
            print(f"{rel}:{line}:{col}: {rule} {msg}")

    total = sum(sum(v.values()) for v in counts.values())
    base_total = sum(sum(v.values()) for v in base.values())
    print(f"pyright: {total} errors (baseline {base_total}); regressions in {len(regressed)} file/rule pairs")
    return 1 if regressed else 0


if __name__ == "__main__":
    sys.exit(main())
