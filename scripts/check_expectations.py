"""Run ClearSignal against the fixtures and compare actual outcomes with expectations/*.yaml.

    uv run python scripts/check_expectations.py                    # contract-fail, server on :8080
    uv run python scripts/check_expectations.py --only resp-003-missing-required-header
    uv run python scripts/check_expectations.py --base-url http://localhost:9000

Exit code 0 only when every case produced exactly its expected outcome. A case that unexpectedly
passes, fails with another finding, or changes exit code makes the run fail.

ClearSignal prints no check IDs, so a failure is recognized by its JSON finding `kind`, its
`where`, and a regex on the validator's message (all recorded in the expectations file).

The runner uses a generated spec copy because of ClearSignal finding F-010; see
scripts/clrsig_spec_copy.py. This is a facility of the test harness only: the specs stay as written.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from clrsig_spec_copy import make_copy  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def clrsig(*args: str) -> tuple[int, str, str]:
    done = subprocess.run(["clrsig", *args], capture_output=True, text=True, encoding="utf-8")
    return done.returncode, done.stdout, done.stderr


def load_json(stdout: str, what: str):
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"cannot read clrsig's JSON for {what}: {exc}\n{stdout[:500]}") from exc


# ---- conform: one case at a time ----


def check_case(case: dict, spec_copy: Path, base_url: str, prefix: str) -> list[str]:
    """Return a list of problems (empty means the case behaved as expected)."""
    path = f"{prefix}/cases/{case['case']}"
    code, out, err = clrsig("conform", str(spec_copy), "-b", base_url, "--paths", path, "--format", "json")
    report = load_json(out, case["case"])
    ran = [op for op in report["operations"] if not op.get("skipped")]
    if len(ran) != 1 or ran[0]["path"] != path:
        return [f"expected exactly one operation to run at {path}, got {[o['path'] for o in ran]}"]
    op = ran[0]
    findings = op.get("findings") or []
    problems: list[str] = []

    if case["expect"] == "pass":
        if code != 0:
            problems.append(f"exit code {code}, expected 0")
        if not op["passed"] or findings or op.get("violations"):
            problems.append(f"expected a pass, got findings: {[f['kind'] for f in findings] or op.get('violations')}")
        return problems

    if code != 1:
        problems.append(f"exit code {code}, expected 1")
    if op["passed"]:
        return problems + ["expected a failure, but the operation passed"]
    if len(findings) != 1:
        problems.append(f"expected exactly one finding, got {len(findings)}: {[f['kind'] for f in findings]}")
    if findings:
        finding = findings[0]
        if finding["kind"] != case["kind"]:
            problems.append(f"finding kind '{finding['kind']}', expected '{case['kind']}'")
        if "where" in case and finding.get("where") != case["where"]:
            problems.append(f"finding location '{finding.get('where')}', expected '{case['where']}'")
    text = " || ".join(op.get("violations") or [])
    if not re.search(case["message"], text):
        problems.append(f"message does not match /{case['message']}/: {text[:160]}")
    return problems


# ---- scenario: checker A (step spec check) and checker B (schema assertion) ----


def check_scenario(entry: dict, spec_copy: Path) -> list[tuple[str, list[str], str]]:
    args = ["run", str(ROOT / entry["file"]), "--env", str(ROOT / entry["env"]), "--spec", str(spec_copy), "--format", "json"]
    _, out, _ = clrsig(*args)
    steps = {s["name"]: s for s in load_json(out, entry["file"])["steps"]}
    results = []
    for name, want in entry["steps"].items():
        step = steps.get(name)
        if step is None:
            results.append((name, ["step missing from the report"], ""))
            continue
        assertions = step.get("assertions") or []
        a_failed = [a for a in assertions if a.get("name") == "spec conformance" and not a["passed"]]
        explicit = [a for a in assertions if a.get("name") != "spec conformance"]
        schema_assertions = [a for a in explicit if a["type"] == "schema"]
        problems = []
        got_a = "violation" if a_failed else "ok"
        if got_a != want["spec_check"]:
            problems.append(f"spec check (A) was '{got_a}', expected '{want['spec_check']}'")
        if want["schema_assertion"] != "none":
            got_b = "ok" if schema_assertions and all(a["passed"] for a in schema_assertions) else "fail"
            if got_b != want["schema_assertion"]:
                problems.append(f"schema assertion (B) was '{got_b}', expected '{want['schema_assertion']}'")
        results.append((name, problems, f"A={got_a} B={'-' if not schema_assertions else ('ok' if all(a['passed'] for a in schema_assertions) else 'fail')}"))
    return results


def print_table(spec: dict) -> int:
    """Markdown table of every case: kept in docs so it cannot drift from the expectations."""
    print("| Case (`GET " + spec["prefix"] + "/cases/<case>`) | Expected | Check | Exit code | ClearSignal reports (or why it passes) |")
    print("|---|---|---|---|---|")
    for case in spec["cases"]:
        if case["expect"] == "fail":
            expected, check, exit_code = "fails", case["check"], 1
            note = case["message"].strip("^").replace("|", "/")
        else:
            expected, exit_code = "passes", 0
            check = case.get("reference") or "none"
            note = case.get("why", "").replace("|", "/")
        print(f"| `{case['case']}` | {expected} | {check} | {exit_code} | {note} |")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--expectations", default="expectations/contract-fail.yaml")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--only", help="comma-separated case names to run")
    parser.add_argument("--table", action="store_true", help="print the expected-results table as markdown and exit")
    args = parser.parse_args()

    if args.table:
        return print_table(yaml.safe_load((ROOT / args.expectations).read_text(encoding="utf-8")))

    spec = yaml.safe_load((ROOT / args.expectations).read_text(encoding="utf-8"))
    prefix = spec["prefix"]
    only = set(args.only.split(",")) if args.only else None
    version = clrsig("--version")[1].strip()
    print(f"{version}  |  {args.expectations}  |  {args.base_url}")

    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "spec.yaml"
        make_copy(str(ROOT / spec["spec"]), prefix, str(copy))
        failures = 0

        # Every case in the expectations must exist in the spec, and the other way round.
        spec_cases = {
            p.removeprefix("/cases/")
            for p in yaml.safe_load((ROOT / spec["spec"]).read_text(encoding="utf-8"))["paths"]
            if p.startswith("/cases/")
        }
        listed = {c["case"] for c in spec["cases"]}
        if spec_cases != listed:
            print(f"FAIL  spec and expectations disagree: only in spec {sorted(spec_cases - listed)}, only in expectations {sorted(listed - spec_cases)}")
            failures += 1

        print(f"\nconform, one case at a time ({len(spec['cases'])} cases)")
        for case in spec["cases"]:
            if only and case["case"] not in only:
                continue
            problems = check_case(case, copy, args.base_url, prefix)
            label = case.get("check") or ("pass" + (f" ({case['reference']})" if case.get("reference") else ""))
            print(f"  {'ok  ' if not problems else 'FAIL'}  {case['case']:<36} {label}")
            for problem in problems:
                print(f"        - {problem}")
            failures += bool(problems)

        if not only:
            print("\nconform, whole spec (acceptance: exits 1, and exactly the expected cases fail)")
            code, out, _ = clrsig("conform", str(copy), "-b", args.base_url, "--format", "json")
            failing = {o["path"].rsplit("/", 1)[-1] for o in load_json(out, "whole spec")["operations"] if not o.get("passed") and not o.get("skipped")}
            expected_failing = {c["case"] for c in spec["cases"] if c["expect"] == "fail"}
            problems = []
            if code != 1:
                problems.append(f"exit code {code}, expected 1")
            if failing != expected_failing:
                problems.append(f"failing set differs: unexpectedly failing {sorted(failing - expected_failing)}, unexpectedly passing {sorted(expected_failing - failing)}")
            print(f"  {'ok  ' if not problems else 'FAIL'}  {len(failing)} of {len(spec['cases'])} cases fail")
            for problem in problems:
                print(f"        - {problem}")
            failures += bool(problems)

            for entry in spec.get("scenarios", []):
                print(f"\nscenario {entry['file']}")
                for name, problems, shown in check_scenario(entry, copy):
                    print(f"  {'ok  ' if not problems else 'FAIL'}  {name:<36} {shown}")
                    for problem in problems:
                        print(f"        - {problem}")
                    failures += bool(problems)

    print(f"\n{'ALL AS EXPECTED' if not failures else str(failures) + ' MISMATCH(ES)'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
