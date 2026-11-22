"""Run ClearSignal against the fixtures and compare actual outcomes with expectations/*.yaml.

    uv run python scripts/check_expectations.py                                   # contract-fail
    uv run python scripts/check_expectations.py --expectations expectations/conform-fail.yaml
    uv run python scripts/check_expectations.py --only resp-003-missing-required-header
    uv run python scripts/check_expectations.py --table                           # markdown table

The server must be running (default http://localhost:8080). Exit code 0 only when every case
produced exactly its expected outcome: a case that unexpectedly passes, fails with another
finding, or changes exit code makes the run fail.

ClearSignal prints no check IDs (F-012), so a response failure is recognized by its JSON finding
`kind`, its `where` and a regex on the validator's message; a probe by its text in the report
(F-014: probes are not in JSON). All of it is recorded in the expectations file.

The runner checks a generated spec copy because of ClearSignal finding F-010; see
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
# `PASS|FAIL <METHOD> <path> <dash> <description> (expect ...)`; the dash is matched loosely so a
# console encoding difference cannot break parsing.
PROBE_LINE = re.compile(r"^\s*(PASS|FAIL)\s+([A-Z]+)\s+(\S+)\s+\S+\s+(.*?)\s+\(expect ")


def clrsig(*args: str) -> tuple[int, str, str]:
    done = subprocess.run(
        ["clrsig", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return done.returncode, done.stdout, done.stderr


def load_json(stdout: str, what: str):
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"cannot read clrsig's JSON for {what}: {exc}\n{stdout[:500]}") from exc


def conform_args(spec: dict, copy: Path, base_url: str) -> list[str]:
    args = ["conform", str(copy), "-b", base_url]
    if spec.get("env"):
        args += ["--env", str(ROOT / spec["env"])]
    return args


def case_path(spec: dict, case: dict) -> str:
    return spec["prefix"] + (case.get("path") or f"/cases/{case['case']}")


# ---- response cases: one operation at a time ----


def check_case(case: dict, spec: dict, copy: Path, base_url: str) -> list[str]:
    """Return a list of problems (empty means the case behaved as expected)."""
    path = case_path(spec, case)
    # --paths is a prefix filter and ClearSignal writes path parameters as {{id}}, so filter on the
    # part before the first parameter and compare the normalized path.
    code, out, _ = clrsig(*conform_args(spec, copy, base_url), "--paths", path.split("{")[0], "--format", "json")
    report = load_json(out, case["case"])
    ran = [op for op in report["operations"] if not op.get("skipped")]
    if len(ran) != 1 or ran[0]["path"].replace("{{", "{").replace("}}", "}") != path:
        return [f"expected exactly one operation to run at {path}, got {[o['path'] for o in ran]}"]
    op = ran[0]
    findings = op.get("findings") or []
    problems: list[str] = []

    # Response problems are in `violations`, problems with the request ClearSignal built in
    # `requestViolations`.
    messages = (op.get("violations") or []) + (op.get("requestViolations") or [])

    if case["expect"] == "pass":
        if code != 0:
            problems.append(f"exit code {code}, expected 0")
        if not op["passed"] or findings or messages:
            problems.append(f"expected a pass, got findings: {[f['kind'] for f in findings] or messages}")
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
    text = " || ".join(messages)
    if not re.search(case["message"], text):
        problems.append(f"message does not match /{case['message']}/: {text[:160]}")
    return problems


def run_response_cases(spec: dict, copy: Path, base_url: str, only: set[str] | None) -> int:
    cases = spec.get("cases") or []
    failures = 0
    print(f"\nconform, one case at a time ({len(cases)} cases)")
    for case in cases:
        if only and case["case"] not in only:
            continue
        problems = check_case(case, spec, copy, base_url)
        label = case.get("check") or ("pass" + (f" ({case['reference']})" if case.get("reference") else ""))
        print(f"  {'ok  ' if not problems else 'FAIL'}  {case['case']:<36} {label}")
        for problem in problems:
            print(f"        - {problem}")
        failures += bool(problems)
    return failures


def run_whole_spec(spec: dict, copy: Path, base_url: str) -> int:
    """Acceptance: the plain conform run exits 1 exactly when some case should fail, and the
    failing operations are exactly the expected ones."""
    cases = spec.get("cases") or []
    expected_failing = {case_path(spec, c) for c in cases if c["expect"] == "fail"}
    code, out, _ = clrsig(*conform_args(spec, copy, base_url), "--format", "json")
    report = load_json(out, "whole spec")
    failing = {
        o["path"].replace("{{", "{").replace("}}", "}")
        for o in report["operations"]
        if not o.get("passed") and not o.get("skipped")
    }
    problems = []
    if code != (1 if expected_failing else 0):
        problems.append(f"exit code {code}, expected {1 if expected_failing else 0}")
    if failing != expected_failing:
        problems.append(
            f"failing set differs: unexpectedly failing {sorted(failing - expected_failing)}, "
            f"unexpectedly passing {sorted(expected_failing - failing)}"
        )
    print(f"\nconform, whole spec (acceptance)\n  {'ok  ' if not problems else 'FAIL'}  {len(failing)} of {len(report['operations'])} operations fail")
    for problem in problems:
        print(f"        - {problem}")
    return bool(problems)


# ---- scenario: checker A (step spec check) and checker B (schema assertion) ----


def check_scenario(entry: dict, copy: Path) -> list[tuple[str, list[str], str]]:
    args = ["run", str(ROOT / entry["file"]), "--env", str(ROOT / entry["env"]), "--spec", str(copy), "--format", "json"]
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
        schema_assertions = [a for a in assertions if a.get("name") != "spec conformance" and a["type"] == "schema"]
        problems = []
        got_a = "violation" if a_failed else "ok"
        if got_a != want["spec_check"]:
            problems.append(f"spec check (A) was '{got_a}', expected '{want['spec_check']}'")
        got_b = "-" if not schema_assertions else ("ok" if all(a["passed"] for a in schema_assertions) else "fail")
        if want["schema_assertion"] != "none" and got_b != want["schema_assertion"]:
            problems.append(f"schema assertion (B) was '{got_b}', expected '{want['schema_assertion']}'")
        results.append((name, problems, f"A={got_a} B={got_b}"))
    return results


def run_scenarios(spec: dict, copy: Path) -> int:
    failures = 0
    for entry in spec.get("scenarios") or []:
        print(f"\nscenario {entry['file']}")
        for name, problems, shown in check_scenario(entry, copy):
            print(f"  {'ok  ' if not problems else 'FAIL'}  {name:<36} {shown}")
            for problem in problems:
                print(f"        - {problem}")
            failures += bool(problems)
    return failures


# ---- what `clrsig generate` builds from the spec (request generation gaps) ----


def run_generation(spec: dict, copy: Path) -> int:
    """Pin CS-GAP-006 (form and multipart bodies are generated without a body) and CS-GAP-010
    (callbacks are not generated) by looking at the request files ClearSignal writes."""
    gen = spec.get("generation")
    if not gen:
        return 0
    with tempfile.TemporaryDirectory() as out:
        code, _, err = clrsig("generate", str(copy), "-o", out, "-b", "http://localhost")
        files = {f.stem: yaml.safe_load(f.read_text(encoding="utf-8")) for f in Path(out).glob("*.yaml")}
    problems = []
    if code != 0:
        problems.append(f"clrsig generate exited {code}: {err[:200]}")
    if "operations" in gen and len(files) != gen["operations"]:
        problems.append(f"{len(files)} requests generated, expected {gen['operations']}")
    for item in gen.get("bodiless") or []:
        request = files.get(item["operation"])
        if request is None:
            problems.append(f"no generated request for {item['operation']}")
        elif request.get("body"):
            problems.append(f"{item['operation']} ({item['media']}) was generated WITH a body; CS-GAP-006 may be fixed")
    for opid in gen.get("with_body") or []:
        request = files.get(opid)
        if request is None or not request.get("body"):
            problems.append(f"{opid} was expected to be generated with a body")
    for opid in gen.get("not_generated") or []:
        if opid in files:
            problems.append(f"{opid} was generated; CS-GAP-010 may be fixed")
    print(f"\nrequest generation ({len(files)} requests)\n  {'ok  ' if not problems else 'FAIL'}  bodiless {len(gen.get('bodiless') or [])}, with body {len(gen.get('with_body') or [])}, not generated {len(gen.get('not_generated') or [])}")
    for problem in problems:
        print(f"        - {problem}")
    return bool(problems)


# ---- negative probes ----


def probe_check(description: str, kinds: dict[str, str]) -> str | None:
    for text, check in kinds.items():
        if description.startswith(text):
            return check
    return None


def run_probes(spec: dict, copy: Path, base_url: str) -> int:
    """One `--negative` run for the whole spec (probes ignore --paths, F-013), attributed to each
    operation from the text report (probes are not in the JSON, F-014)."""
    entries = spec.get("probes") or []
    kinds = spec.get("probe_kinds") or {}
    code, out, _ = clrsig(*conform_args(spec, copy, base_url), "--negative")
    seen: dict[str, list[tuple[str, str]]] = {}
    for line in out.splitlines():
        match = PROBE_LINE.match(line)
        if match:
            seen.setdefault(match.group(3), []).append((match.group(1), match.group(4)))

    failures = 0
    print(f"\nnegative probes ({sum(len(v) for v in seen.values())} probes over {len(seen)} operations)")
    expected_failing_total = 0
    for entry in entries:
        path = spec["prefix"] + entry["op"]
        probes = seen.get(path, [])
        failed = [d for status, d in probes if status == "FAIL"]
        expected = entry.get("fail") or []
        expected_failing_total += len(expected)
        problems = []
        if len(probes) != entry["probes"]:
            problems.append(f"ClearSignal ran {len(probes)} probes, expected {entry['probes']} (did probing change?)")
        want_failed = sorted(e["probe"] for e in expected)
        if sorted(failed) != want_failed:
            problems.append(f"failing probes {sorted(failed)}, expected {want_failed}")
        for e in expected:
            got = probe_check(e["probe"], kinds)
            if got != e["check"]:
                problems.append(f"probe '{e['probe']}' maps to {got}, expected {e['check']}")
        label = ", ".join(e["check"] for e in expected) or ("pass" + (f" ({entry['reference']})" if entry.get("reference") else ""))
        print(f"  {'ok  ' if not problems else 'FAIL'}  {entry['op']:<34} {len(probes)} probes  {label}")
        for problem in problems:
            print(f"        - {problem}")
        failures += bool(problems)

    unexpected = sorted(set(seen) - {spec["prefix"] + e["op"] for e in entries})
    if unexpected:
        print(f"  FAIL  probes ran for operations not in the expectations: {unexpected}")
        failures += 1
    want_code = 1 if expected_failing_total else 0
    if code != want_code:
        print(f"  FAIL  --negative exit code {code}, expected {want_code}")
        failures += 1
    return failures


# ---- housekeeping ----


def covered_paths(spec: dict) -> set[str]:
    paths = {case.get("path") or f"/cases/{case['case']}" for case in spec.get("cases") or []}
    paths |= {entry["op"] for entry in spec.get("probes") or []}
    paths |= set(spec.get("ignore") or [])
    return paths


def print_table(spec: dict) -> int:
    """Markdown table of every response case, kept in docs so it cannot drift."""
    print("| Case | Path (under `" + spec["prefix"] + "`) | Expected | Check | Exit code | ClearSignal reports (or why it passes) |")
    print("|---|---|---|---|---|---|")
    for case in spec["cases"]:
        path = case.get("path") or f"/cases/{case['case']}"
        if case["expect"] == "fail":
            expected, check, exit_code = "fails", case["check"], 1
            note = case["message"].strip("^").replace("|", "/")
        else:
            expected, exit_code = "passes", 0
            check = case.get("reference") or "none"
            note = case.get("why", "").replace("|", "/")
        print(f"| `{case['case']}` | `{path}` | {expected} | {check} | {exit_code} | {note} |")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--expectations", default="expectations/contract-fail.yaml")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--only", help="comma-separated case names to run (response cases only)")
    parser.add_argument("--table", action="store_true", help="print the response-case table as markdown and exit")
    args = parser.parse_args()

    spec = yaml.safe_load((ROOT / args.expectations).read_text(encoding="utf-8"))
    if args.table:
        return print_table(spec)
    only = set(args.only.split(",")) if args.only else None
    print(f"{clrsig('--version')[1].strip()}  |  {args.expectations}  |  {args.base_url}")

    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "spec.yaml"
        make_copy(str(ROOT / spec["spec"]), spec["prefix"], str(copy))
        failures = 0

        in_spec = set(yaml.safe_load((ROOT / spec["spec"]).read_text(encoding="utf-8"))["paths"])
        covered = covered_paths(spec)
        if in_spec != covered:
            print(f"FAIL  spec and expectations disagree: only in spec {sorted(in_spec - covered)}, only in expectations {sorted(covered - in_spec)}")
            failures += 1

        failures += run_response_cases(spec, copy, args.base_url, only) if spec.get("cases") else 0
        if not only:
            failures += run_whole_spec(spec, copy, args.base_url)
            failures += run_scenarios(spec, copy)
            failures += run_generation(spec, copy)
            if spec.get("probes"):
                failures += run_probes(spec, copy, args.base_url)

    print(f"\n{'ALL AS EXPECTED' if not failures else str(failures) + ' MISMATCH(ES)'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
