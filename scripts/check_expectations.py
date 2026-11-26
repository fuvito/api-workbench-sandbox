"""Run ClearSignal against the fixtures and compare actual outcomes with expectations/*.yaml.

    uv run python scripts/check_expectations.py                                   # contract-fail
    uv run python scripts/check_expectations.py --expectations expectations/conform-fail.yaml
    uv run python scripts/check_expectations.py --only resp-003-missing-required-header
    uv run python scripts/check_expectations.py --table                           # markdown table

The server must be running (default http://localhost:8080). Exit code 0 only when every case
produced exactly its expected outcome: a case that unexpectedly passes, fails with another
finding, or changes exit code makes the run fail.

A response failure is recognized by the `checkId` ClearSignal puts on each finding in its JSON
report, plus a regex on the validator's message; a probe by its text in the report. Everything is
recorded in the expectations file. Written for clrsig v0.13.3 (v0.10.0 and later for the baseline cases).
"""

import argparse
import functools
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# clrsig prints characters such as the cross of a failed check; a Windows console would stop on them.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
CLOUD = False  # --cloud: skip every entry marked `local_only: true` (transport behavior not verified on Cloud Run)
# `PASS|FAIL <METHOD> <path> <dash> <description> (expect ...)`; the dash is matched loosely so a
# console encoding difference cannot break parsing.
PROBE_LINE = re.compile(r"^\s*(PASS|FAIL)\s+([A-Z]+)\s+(\S+)\s+\S+\s+(.*?)\s+\(expect ")


def clrsig(*args: str, unset: tuple[str, ...] = ()) -> tuple[int, str, str]:
    env = {k: v for k, v in os.environ.items() if k not in unset}
    done = subprocess.run(
        ["clrsig", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env
    )
    return done.returncode, done.stdout, done.stderr


def load_json(stdout: str, what: str):
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"cannot read clrsig's JSON for {what}: {exc}\n{stdout[:500]}") from exc


def conform_args(spec: dict, spec_file: Path, base_url: str) -> list[str]:
    # the spec keeps its `servers` block (standard), so the base is the family's, prefix included
    args = ["conform", str(spec_file), "-b", base_url + spec["prefix"]]
    if spec.get("env"):
        args += ["--env", str(ROOT / spec["env"])]
    return args


def norm(path: str) -> str:
    """ClearSignal writes a path parameter as {{id}}; the specs write {id}."""
    return path.replace("{{", "{").replace("}}", "}")


def case_path(spec: dict, case: dict) -> str:
    return spec["prefix"] + (case.get("path") or f"/cases/{case['case']}")


def skipped(entry: dict) -> bool:
    return CLOUD and bool(entry.get("local_only"))


def reset_family(spec: dict, base_url: str) -> None:
    """POST <prefix>/__admin/reset so counters and stores start from the seed state."""
    request = urllib.request.Request(f"{base_url}{spec['prefix']}/__admin/reset", method="POST")
    if os.environ.get("ADMIN_TOKEN"):
        request.add_header("Authorization", f"Bearer {os.environ['ADMIN_TOKEN']}")
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status != 204:
            raise SystemExit(f"reset answered {response.status}")


# ---- response cases: one operation at a time ----


def check_case(case: dict, spec: dict, spec_file: Path, base_url: str) -> list[str]:
    """Return a list of problems (empty means the case behaved as expected)."""
    path = case_path(spec, case)
    # --paths is a prefix filter on the spec's own paths (no family prefix) and ClearSignal writes
    # path parameters as {{id}}, so filter on the part before the first parameter.
    code, out, _ = clrsig(
        *conform_args(spec, spec_file, base_url), "--paths", path.removeprefix(spec["prefix"]).split("{")[0], "--format", "json",
        *[str(a) for a in case.get("args") or []],
    )
    report = load_json(out, case["case"])
    ran_all = [op for op in report["operations"] if not op.get("skipped")]
    # --paths is a PREFIX filter, so /unavailable also runs /unavailable-then-ok. Pick the
    # operation(s) by exact path and judge the outcome from them, not from the whole command's exit
    # code. The extra calls are harmless: every stateful case resets its family first.
    ran = [o for o in ran_all if spec["prefix"] + norm(o["path"]) == path]
    want_ops = case.get("operations", 1)  # a path can carry several methods (GET and PUT)
    if len(ran) != want_ops:
        return [f"expected {want_ops} operation(s) at {path}, got {[o['method'] + ' ' + o['path'] for o in ran_all]}"]
    derived = 0 if all(o["passed"] for o in ran) else 1
    if len(ran_all) == len(ran) and code != derived:
        return [f"exit code {code} does not match the operation outcome ({derived})"]
    if want_ops > 1:
        if case["expect"] != "pass":
            return ["a multi-operation case can only expect a pass"]
        bad = [o["method"] for o in ran if not o["passed"] or o.get("findings")]
        return [f"operations that did not pass: {bad}"] if bad else []
    op = ran[0]
    findings = op.get("findings") or []
    problems: list[str] = []
    code = derived

    # Response problems are in `violations`, problems with the request ClearSignal built in
    # `requestViolations`, and a request that got no answer in `error` / `blocked`.
    messages = (
        (op.get("violations") or []) + (op.get("requestViolations") or [])
        + [m for m in (op.get("error"), op.get("blocked")) if m]
    )

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
        # `reported` is the checkId ClearSignal puts in the report when it differs from the catalog's
        # (null: the finding carries none, F-022); `check` is the catalog ID the case is about.
        if finding.get("checkId") != case.get("reported", case["check"]):
            problems.append(f"check {finding.get('checkId')}, expected {case.get('reported', case['check'])}")
        if "kind" in case and finding["kind"] != case["kind"]:
            problems.append(f"finding kind '{finding['kind']}', expected '{case['kind']}'")
    text = " || ".join(messages)
    if not re.search(case["message"], text):
        problems.append(f"message does not match /{case['message']}/: {text[:160]}")
    return problems


def run_response_cases(spec: dict, spec_file: Path, base_url: str, only: set[str] | None) -> int:
    cases = spec.get("cases") or []
    failures = 0
    print(f"\nconform, one case at a time ({len(cases)} cases)")
    for case in cases:
        if only and case["case"] not in only:
            continue
        if skipped(case):
            print(f"  skip  {case['case']:<36} (local only)")
            continue
        problems = check_case(case, spec, spec_file, base_url)
        if case["expect"] == "fail":
            label = case["check"] or f"no check ID ({case.get('reference')})"
        else:
            label = "pass" + (f" ({case['reference']})" if case.get("reference") else "")
        print(f"  {'ok  ' if not problems else 'FAIL'}  {case['case']:<36} {label}")
        for problem in problems:
            print(f"        - {problem}")
        failures += bool(problems)
    return failures


def run_whole_spec(spec: dict, spec_file: Path, base_url: str) -> int:
    """Acceptance: the plain conform run exits 1 exactly when some case should fail, and the
    failing operations are exactly the expected ones."""
    cases = spec.get("cases") or []
    options = spec.get("whole_spec") or {}
    if CLOUD:
        return 0  # the whole-spec outcome includes local-only cases; it is verified locally
    # With request timeouts or counters in play the whole-spec outcome differs from the per-case
    # outcomes, so `whole_spec.failing` can list the failing paths explicitly.
    if "failing" in options:
        expected_failing = {spec["prefix"] + p for p in options["failing"]}
    else:
        expected_failing = {case_path(spec, c) for c in cases if c["expect"] == "fail"}
    if options.get("reset"):
        reset_family(spec, base_url)
    extra = ["--request-timeout", str(options["request_timeout"])] if options.get("request_timeout") else []
    code, out, _ = clrsig(*conform_args(spec, spec_file, base_url), "--format", "json", *extra)
    report = load_json(out, "whole spec")
    failing = {
        spec["prefix"] + norm(o["path"])
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


@functools.cache
def schema_assertions_are_strict() -> bool:
    """From clrsig 0.13.4 a `schema` assertion fails when it has nothing to compare the body with
    (F-038). A development build ("dev", clrsig's main) behaves like the newest release."""
    _, out, _ = clrsig("--version")
    found = re.search(r"v(\d+)\.(\d+)\.(\d+)", out)
    return found is None or tuple(int(n) for n in found.groups()) >= (0, 13, 4)


def check_scenario(entry: dict, spec_file: Path) -> list[tuple[str, list[str], str]]:
    args = ["run", str(ROOT / entry["file"]), "--env", str(ROOT / entry["env"]), "--spec", str(spec_file), "--format", "json"]
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
        if "spec_check" in want and got_a != want["spec_check"]:
            problems.append(f"spec check (A) was '{got_a}', expected '{want['spec_check']}'")
        got_b = "-" if not schema_assertions else ("ok" if all(a["passed"] for a in schema_assertions) else "fail")
        expected_b = want.get("schema_assertion", "none")
        # a result that changed with 0.13.4 is written down for both sides, never "either"
        if "schema_assertion_from_0_13_4" in want and schema_assertions_are_strict():
            expected_b = want["schema_assertion_from_0_13_4"]
        if expected_b != "none" and got_b != expected_b:
            problems.append(f"schema assertion (B) was '{got_b}', expected '{expected_b}'")
        # Plain step outcome, for scenarios whose steps assert the CORRECT behavior and so fail
        # exactly where the server is wrong.
        if "passed" in want and step["passed"] != want["passed"]:
            problems.append(f"step passed={step['passed']}, expected {want['passed']}")
        if "extracted" in want and (step.get("extracted") or {}) != want["extracted"]:
            problems.append(f"extracted {step.get('extracted')}, expected {want['extracted']}")
        if "error" in want and not re.search(want["error"], step.get("error") or ""):
            problems.append(f"step error does not match /{want['error']}/: {(step.get('error') or '')[:120]}")
        shown = f"A={got_a} B={got_b}" if "spec_check" in want else f"passed={step['passed']}"
        results.append((name, problems, shown))
    return results


def run_scenarios(spec: dict, spec_file: Path) -> int:
    failures = 0
    for entry in spec.get("scenarios") or []:
        print(f"\nscenario {entry['file']}")
        for name, problems, shown in check_scenario(entry, spec_file):
            print(f"  {'ok  ' if not problems else 'FAIL'}  {name:<36} {shown}")
            for problem in problems:
                print(f"        - {problem}")
            failures += bool(problems)
    return failures


# ---- whole commands: wrong environments, scenarios that cannot run, unreadable specs, ... ----


_BIG_SPEC: Path | None = None


def big_spec_file() -> Path:
    """The 500-operation document of the scale cases, built once per run (scripts/make_specs.py)."""
    global _BIG_SPEC
    if _BIG_SPEC is None:
        sys.path.insert(0, str(Path(__file__).parent))
        from make_specs import big_spec, dump

        _BIG_SPEC = Path(tempfile.mkdtemp(prefix="clrsig-big-")) / "big-500.json"
        _BIG_SPEC.write_text(dump(big_spec(500)), encoding="utf-8")
    return _BIG_SPEC


def check_run(entry: dict, spec_file: Path, base_url: str, prefix: str = "") -> list[str]:
    """Run one ClearSignal command and compare exit code, finding and output text.

    `args` may use {spec} (the family's spec), {base} (the server's base URL), {fbase} (the base URL
    with the family prefix), {root} (the repo) and {bigspec} (a generated 500-operation document).
    `max_seconds` fails the entry when the command takes longer.
    `unset` lists process variables removed from the command's environment. `finding` applies to
    the one operation that ran (kind, and a regex over its messages); `output` is a regex over
    everything the command printed and `not_output` one that must NOT match it.
    """
    bigspec = str(big_spec_file()) if any("{bigspec}" in a for a in entry["args"]) else ""
    args = [a.format(spec=str(spec_file), base=base_url, fbase=base_url + prefix, root=str(ROOT), bigspec=bigspec) for a in entry["args"]]
    started = time.monotonic()
    code, out, err = clrsig(*args, unset=tuple(entry.get("unset") or ()))
    elapsed = time.monotonic() - started
    problems = []
    if "max_seconds" in entry and elapsed > entry["max_seconds"]:
        problems.append(f"took {elapsed:.1f} s, more than {entry['max_seconds']} s")
    if code != entry["exit"]:
        problems.append(f"exit code {code}, expected {entry['exit']}")
    text = out + "\n" + err
    if "output" in entry and not re.search(entry["output"], text):
        problems.append(f"output does not match /{entry['output']}/: {' '.join(text.split())[:180]}")
    if "not_output" in entry and re.search(entry["not_output"], text):
        problems.append(f"output matches /{entry['not_output']}/ but must not")
    if "finding" in entry or "passed" in entry:
        try:
            ran = [o for o in json.loads(out)["operations"] if not o.get("skipped")]
        except (json.JSONDecodeError, KeyError):
            return problems + ["expected a JSON report with operations"]
        if entry.get("op"):
            # --paths is a prefix filter: pick the operation by its exact path, and judge the exit
            # code from that operation alone (the others it dragged in are not under test).
            ran = [o for o in ran if norm(o["path"]) == entry["op"]]
            problems = [p for p in problems if not p.startswith("exit code")]
            derived = 0 if all(o["passed"] for o in ran) else 1
            if ran and derived != entry["exit"]:
                problems.append(f"operation outcome exit {derived}, expected {entry['exit']}")
        if len(ran) != 1:
            return problems + [f"expected exactly one operation to run, got {len(ran)}"]
        op = ran[0]
        if "passed" in entry and op["passed"] != entry["passed"]:
            problems.append(f"operation passed={op['passed']}, expected {entry['passed']}")
        if "finding" in entry:
            want = entry["finding"]
            findings = op.get("findings") or []
            if len(findings) != 1:
                problems.append(f"expected exactly one finding, got {[f['kind'] for f in findings]}")
            elif findings[0]["kind"] != want["kind"]:
                problems.append(f"finding kind '{findings[0]['kind']}', expected '{want['kind']}'")
            elif "check" in want and findings[0].get("checkId") != want["check"]:
                problems.append(f"check {findings[0].get('checkId')}, expected {want['check']}")
            messages = " || ".join(
                (op.get("violations") or []) + (op.get("requestViolations") or []) + [op.get("blocked") or "", op.get("error") or ""]
            )
            if not re.search(want["message"], messages):
                problems.append(f"message does not match /{want['message']}/: {messages[:200]}")
    return problems


def run_runs(spec: dict, spec_file: Path, base_url: str) -> int:  # noqa: C901
    runs = spec.get("runs") or []
    if not runs:
        return 0
    failures = 0
    print(f"\ncommands ({len(runs)}): wrong environments, scenarios that cannot run, unreadable specs")
    for entry in runs:
        if skipped(entry):
            print(f"  skip  {entry['name']:<40} (local only)")
            continue
        problems = check_run(entry, spec_file, base_url, spec["prefix"])
        label = entry.get("check") or ("pass" + (f" ({entry['reference']})" if entry.get("reference") else ""))
        print(f"  {'ok  ' if not problems else 'FAIL'}  {entry['name']:<40} exit {entry['exit']}  {label}")
        for problem in problems:
            print(f"        - {problem}")
        failures += bool(problems)
    return failures


# ---- call sequences: state-dependent behavior (a counter, a degrading delay) ----


def run_sequences(spec: dict, spec_file: Path, base_url: str) -> int:
    """Reset the family, call one operation several times, and compare each outcome in order.

    `outcomes` is a list of pass / fail per call. `fail` pins the finding every failed call must
    have. `repeat: 2` runs the whole sequence again after another reset and demands the same
    outcomes (determinism). `args` are extra clrsig arguments (for example a request timeout).
    """
    sequences = spec.get("sequences") or []
    if not sequences:
        return 0
    failures = 0
    print(f"\nsequences ({len(sequences)}): state after a reset, call by call")
    for seq in sequences:
        if skipped(seq):
            print(f"  skip  {seq['name']:<40} (local only)")
            continue
        path = seq["path"]
        problems: list[str] = []
        runs = seq.get("repeat", 1)
        shown = ""
        for attempt in range(runs):
            reset_family(spec, base_url)
            got = []
            for call in range(1, len(seq["outcomes"]) + 1):
                code, out, _ = clrsig(
                    *conform_args(spec, spec_file, base_url), "--paths", path, "--format", "json",
                    *[str(a) for a in seq.get("args") or []],
                )
                ran = [o for o in load_json(out, seq["name"])["operations"] if not o.get("skipped")]
                if len(ran) != 1:
                    problems.append(f"call {call}: expected one operation, got {len(ran)}")
                    got.append("?")
                    continue
                op = ran[0]
                got.append("pass" if op["passed"] else "fail")
                if not op["passed"] and seq.get("fail"):
                    want = seq["fail"]
                    findings = op.get("findings") or []
                    text = " || ".join((op.get("violations") or []) + [op.get("error") or "", op.get("blocked") or ""])
                    if len(findings) != 1 or findings[0]["kind"] != want["kind"]:
                        problems.append(f"call {call}: finding {[f['kind'] for f in findings]}, expected {want['kind']}")
                    elif "check" in want and findings[0].get("checkId") != want["check"]:
                        problems.append(f"call {call}: check {findings[0].get('checkId')}, expected {want['check']}")
                    if not re.search(want["message"], text):
                        problems.append(f"call {call}: message does not match /{want['message']}/: {text[:120]}")
            if got != seq["outcomes"]:
                problems.append(f"run {attempt + 1}: outcomes {got}, expected {seq['outcomes']}")
            shown = " ".join("P" if g == "pass" else "F" for g in got)
        label = seq.get("check") or "pass"
        print(f"  {'ok  ' if not problems else 'FAIL'}  {seq['name']:<40} {shown}  {label}{'  x' + str(runs) if runs > 1 else ''}")
        for problem in problems:
            print(f"        - {problem}")
        failures += bool(problems)
    return failures


# ---- what `clrsig generate` builds from the spec (request generation gaps) ----


def run_generation(spec: dict, spec_file: Path) -> int:
    """Pin CS-GAP-006 (form and multipart bodies are generated without a body) and CS-GAP-010
    (callbacks are not generated) by looking at the request files ClearSignal writes."""
    gen = spec.get("generation")
    if not gen:
        return 0
    with tempfile.TemporaryDirectory() as out:
        code, _, err = clrsig("generate", str(spec_file), "-o", out, "-b", "http://localhost")
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


def run_probes(spec: dict, spec_file: Path, base_url: str) -> int:
    """One `--negative` run for the whole spec, attributed to each operation from the text report
    (the JSON report has the probes too, but the text carries the description the expectations quote)."""
    entries = spec.get("probes") or []
    kinds = spec.get("probe_kinds") or {}
    code, out, _ = clrsig(*conform_args(spec, spec_file, base_url), "--negative")
    seen: dict[str, list[tuple[str, str]]] = {}
    for line in out.splitlines():
        match = PROBE_LINE.match(line)
        if match:
            seen.setdefault(match.group(3), []).append((match.group(1), match.group(4)))

    failures = 0
    print(f"\nnegative probes ({sum(len(v) for v in seen.values())} probes over {len(seen)} operations)")
    expected_failing_total = 0
    for entry in entries:
        probes = seen.get(entry["op"], [])
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

    unexpected = sorted(set(seen) - {e["op"] for e in entries})
    if unexpected:
        print(f"  FAIL  probes ran for operations not in the expectations: {unexpected}")
        failures += 1
    # The --negative run also repeats the plain conform pass, so operations that fail there fail it too.
    want_code = 1 if expected_failing_total or (spec.get("whole_spec") or {}).get("failing") else 0
    if code != want_code:
        print(f"  FAIL  --negative exit code {code}, expected {want_code}")
        failures += 1
    return failures


# ---- spec against spec: clrsig diff and clrsig impact (no server involved) ----


def run_diffs(spec: dict) -> int:
    """Each pair: the exact set of changes (id and level) and the exit code at every --fail-on level."""
    failures = 0
    print(f"\nclrsig diff ({len(spec['diffs'])} pairs; v1 against v2, no server)")
    for case in spec["diffs"]:
        base = ROOT / "specs" / "diff" / case["case"]
        problems = []
        _, out, _ = clrsig("diff", str(base / "v1.yaml"), str(base / "v2.yaml"), "--format", "json")
        report = load_json(out, case["case"])
        got = sorted((c["level"], c["id"]) for c in report.get("changes") or [])
        want = sorted((c["level"], c["id"]) for c in case["changes"])
        if got != want:
            problems.append(f"changes {got}, expected {want}")
        for level, expected in case["exit"].items():
            code, _, _ = clrsig("diff", str(base / "v1.yaml"), str(base / "v2.yaml"), "--fail-on", level)
            if code != expected:
                problems.append(f"--fail-on {level}: exit {code}, expected {expected}")
        top = ("ERR" if any(c[0] == "ERR" for c in got) else "WARN" if any(c[0] == "WARN" for c in got)
               else "INFO" if got else "none")
        e = case["exit"]
        print(f"  {'ok  ' if not problems else 'FAIL'}  {case['case']:<30} {top:<5} exit {e['breaking']}/{e['warning']}/{e['info']}  {case.get('check') or 'no change'}")
        for problem in problems:
            print(f"        - {problem}")
        failures += bool(problems)
    return failures


def run_impacts(spec: dict) -> int:
    failures = 0
    print(f"\nclrsig impact ({len(spec['impacts'])} cases)")
    for case in spec["impacts"]:
        base = ROOT / "specs" / "diff" / case["pair"]
        scenarios = [str(ROOT / s) for s in case["scenarios"]]
        code, out, _ = clrsig("impact", str(base / "v1.yaml"), str(base / "v2.yaml"), *scenarios, "--format", "json")
        problems = []
        if code != case["exit"]:
            problems.append(f"exit code {code}, expected {case['exit']}")
        report = load_json(out, case["name"])
        hit = sorted(
            f"{Path(s['path']).name}: {step['label']}"
            for s in (report.get("scenarios") or []) for step in s.get("steps") or []
        )
        if hit != sorted(case.get("hits") or []):
            problems.append(f"steps hit {hit}, expected {sorted(case.get('hits') or [])}")
        print(f"  {'ok  ' if not problems else 'FAIL'}  {case['name']:<44} exit {case['exit']}  {case.get('check') or 'no hit'}")
        for problem in problems:
            print(f"        - {problem}")
        failures += bool(problems)
    return failures


# ---- coverage signals ----


def run_coverage(spec: dict, base_url: str) -> int:
    """Run the gap-leaving scenario into a fresh workspace and read the four quality signals as JSON."""
    cov = spec.get("coverage")
    if not cov:
        return 0
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        spec_file = ROOT / cov["spec"]
        workspace = Path(tmp) / "workspace"
        workspace.mkdir()
        run_args = ["run", str(ROOT / cov["scenario"]), "--env", str(ROOT / cov["env"]), "--spec", str(spec_file), "-w", str(workspace)]
        code, _, _ = clrsig(*run_args)
        if code != 0:
            problems.append(f"the scenario run exited {code}, expected 0")
        code, out, _ = clrsig("coverage", "quality", str(spec_file), "-w", str(workspace), "--format", "json")
        if code != cov["exit"]:
            problems.append(f"coverage quality exit code {code}, expected {cov['exit']}")
        report = load_json(out, "coverage quality")
        for key, got, want in (
            ("never_exercised", report.get("neverExercised") or [], cov["never_exercised"]),
            ("happy_path_only", report.get("happyPathOnly") or [], cov["happy_path_only"]),
            ("secured_never_authed", report.get("securedNeverAuthed") or [], cov["secured_never_authed"]),
            ("errors_never_triggered", [f"{e['operation']} -> {e['missing']}" for e in report.get("errorsNeverTriggered") or []],
             [f"{e['op']} -> {e['missing']}" for e in cov["errors_never_triggered"]]),
        ):
            if sorted(got) != sorted(want):
                problems.append(f"{key}: {sorted(got)}, expected {sorted(want)}")
        totals = report.get("totals") or {}
        for key, want in cov["totals"].items():
            if totals.get(key) != want:
                problems.append(f"totals.{key} = {totals.get(key)}, expected {want}")

    print(f"\ncoverage signals (fresh workspace, {cov['scenario']})")
    print(f"  {'ok  ' if not problems else 'FAIL'}  CS-COV-001 {len(cov['never_exercised'])}, CS-COV-002 {len(cov['happy_path_only'])}, CS-COV-003 {len(cov['errors_never_triggered'])}, CS-COV-004 {len(cov['secured_never_authed'])}")
    for problem in problems:
        print(f"        - {problem}")
    return bool(problems)


# ---- drift and the baseline ratchet (real servers at different drift levels) ----


def _free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(drift: int) -> tuple[subprocess.Popen, str]:
    port = _free_port()
    env = {**os.environ, "PORT": str(port), "HOST": "127.0.0.1"}
    env.pop("DRIFT", None)
    proc = subprocess.Popen(
        [sys.executable, "-m", "app", f"--drift={drift}"], cwd=ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            with urllib.request.urlopen(f"{url}/conform-fail/health", timeout=1):
                return proc, url
        except OSError:
            if proc.poll() is not None:
                break
            import time

            time.sleep(0.1)
    proc.kill()
    raise SystemExit(f"the drift-{drift} server did not start")


def run_drift(spec: dict, spec_file: Path) -> int:
    """Record baselines at one drift level and run at another: the ratchet (CS-RUN-006)."""
    drift = spec.get("drift")
    if not drift:
        return 0
    servers: dict[int, tuple[subprocess.Popen, str]] = {}
    problems_total = 0
    print(f"\ndrift and the baseline ratchet (a server per drift level, --paths {','.join(drift['paths'])})")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            baselines: dict[str, Path] = {}
            for step in drift["steps"]:
                level = step["drift"]
                if level not in servers:
                    servers[level] = _start_server(level)
                url = servers[level][1]
                args = conform_args(spec, spec_file, url)
                if step["mode"] != "write":  # a baseline is recorded from a full run (clrsig 0.10.0)
                    args += ["--paths", ",".join(drift["paths"])]
                file = baselines.setdefault(step["file"], Path(tmp) / f"{step['file']}.yaml")
                if step["mode"] == "write":
                    args += ["--write-baseline", str(file)]
                elif step["mode"] == "use":
                    args += ["--baseline", str(file)]
                elif step["mode"] == "use-missing":
                    args += ["--baseline", str(Path(tmp) / "does-not-exist.yaml")]
                code, out, err = clrsig(*args)
                text = out + "\n" + err
                problems = []
                if code != step["exit"]:
                    problems.append(f"exit code {code}, expected {step['exit']}")
                if "output" in step and not re.search(step["output"], text):
                    last = [line for line in text.splitlines() if line.strip()][-1:] or [""]
                    problems.append(f"output does not match /{step['output']}/ (last line: {last[0][:120]})")
                for kind in ("NEW", "FIXED"):
                    got = sorted(re.findall(rf"^\s*{kind}\s+(\S+ \S+)", text, re.M))
                    expected = sorted(step.get(kind.lower()) or [])
                    if got != expected:
                        problems.append(f"{kind} {got}, expected {expected}")
                label = step.get("check") or "baseline"
                print(f"  {'ok  ' if not problems else 'FAIL'}  {step['name']:<44} drift {level}  exit {step['exit']}  {label}")
                for problem in problems:
                    print(f"        - {problem}")
                problems_total += bool(problems)
    finally:
        for proc, _ in servers.values():
            proc.terminate()
        for proc, _ in servers.values():
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
    return problems_total


# ---- housekeeping ----


def covered_paths(spec: dict) -> set[str]:
    paths = {case.get("path") or f"/cases/{case['case']}" for case in spec.get("cases") or []}
    paths |= {entry["op"] for entry in spec.get("probes") or []}
    paths |= {seq["path"] for seq in spec.get("sequences") or []}
    paths |= {run["covers"] for run in spec.get("runs") or [] if run.get("covers")}
    paths |= {step["covers"] for sc in spec.get("scenarios") or [] for step in sc["steps"].values() if step.get("covers")}
    paths |= set(spec.get("ignore") or [])
    if (spec.get("whole_spec") or {}).get("covers_all"):  # a whole-spec run judges every operation
        paths |= set(yaml.safe_load((ROOT / spec["spec"]).read_text(encoding="utf-8"))["paths"])
    return paths


def print_table(spec: dict) -> int:
    """Markdown table of every response case, kept in docs so it cannot drift."""
    print("| Case | Path (under `" + spec["prefix"] + "`) | Expected | Check | Exit code | ClearSignal reports (or why it passes) |")
    print("|---|---|---|---|---|---|")
    for case in spec["cases"]:
        path = case.get("path") or f"/cases/{case['case']}"
        if case["expect"] == "fail":
            expected, check, exit_code = "fails", case["check"] or f"none ({case.get('reference')})", 1
            note = case["message"].strip("^").replace("|", "/")
        else:
            expected, exit_code = "passes", 0
            check = case.get("reference") or "none"
            note = case.get("why", "").replace("|", "/")
        if case.get("args"):
            note += f" (with {' '.join(str(a) for a in case['args'])})"
        if case.get("local_only"):
            note += " (local only)"
        print(f"| `{case['case']}` | `{path}` | {expected} | {check} | {exit_code} | {note} |")
    if spec.get("sequences"):
        print("\n### Sequences (reset first, then call by call)\n")
        print("| Sequence | Path | Outcomes (P = pass, F = fail) | Check on failure | Notes |")
        print("|---|---|---|---|---|")
        for seq in spec["sequences"]:
            outcomes = " ".join("P" if o == "pass" else "F" for o in seq["outcomes"])
            extra = f"with {' '.join(str(a) for a in seq['args'])}" if seq.get("args") else ""
            if seq.get("repeat", 1) > 1:
                extra += f"; repeated {seq['repeat']} times after a reset, identical"
            print(f"| `{seq['name']}` | `{seq['path']}` | {outcomes} | {seq.get('check', 'none')} | {extra.strip('; ')} |")
    if spec.get("runs"):
        print("\n### Commands (wrong environments, scenarios that cannot run, unreadable specs)\n")
        print("| Run | Check | Exit code | ClearSignal reports |")
        print("|---|---|---|---|")
        for run in spec["runs"]:
            note = (run.get("finding") or {}).get("message") or run.get("output") or ""
            if run.get("note"):
                note += f" ({run['note']})"
            print(f"| `{run['name']}` | {run.get('check', 'none')} | {run['exit']} | {note.replace('|', '/')} |")
    return 0


def print_diff_table(spec: dict) -> int:
    print("| Pair (`specs/diff/<case>/v1.yaml`, `v2.yaml`) | Highest level | Check | Exit code at --fail-on breaking / warning / info | Changes reported |")
    print("|---|---|---|---|---|")
    for case in spec["diffs"]:
        levels = [c["level"] for c in case["changes"]]
        top = "ERR" if "ERR" in levels else "WARN" if "WARN" in levels else "INFO" if levels else "none"
        ids = sorted({c["id"] for c in case["changes"]})
        e = case["exit"]
        print(f"| `{case['case']}` | {top} | {case.get('check') or 'none'} | {e['breaking']} / {e['warning']} / {e['info']} | {', '.join(ids) or 'nothing'} |")
    print("\n### clrsig impact\n")
    print("| Case | Pair | Check | Exit code | Steps that call a breaking change |")
    print("|---|---|---|---|---|")
    for case in spec["impacts"]:
        hits = '; '.join(case.get('hits') or []) or 'none'
        print(f"| `{case['name']}` | `{case['pair']}` | {case.get('check') or 'none'} | {case['exit']} | {hits} |")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--expectations", default="expectations/contract-fail.yaml")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--only", help="comma-separated case names to run (response cases only)")
    parser.add_argument("--table", action="store_true", help="print the response-case table as markdown and exit")
    parser.add_argument("--cloud", action="store_true", help="skip entries marked local_only (transport behavior not verified on Cloud Run)")
    parser.add_argument(
        "--section",
        help="comma-separated parts to run: cases, whole, scenarios, generation, runs, sequences, coverage, drift, probes (default: all)",
    )
    args = parser.parse_args()
    global CLOUD
    CLOUD = args.cloud

    spec = yaml.safe_load((ROOT / args.expectations).read_text(encoding="utf-8"))
    if spec.get("family") == "diff":  # spec against spec: no server, no spec to prepare
        if args.table:
            return print_diff_table(spec)
        print(f"{clrsig('--version')[1].strip()}  |  {args.expectations}  |  no server needed")
        failures = run_diffs(spec) + run_impacts(spec)
        print(f"\n{'ALL AS EXPECTED' if not failures else str(failures) + ' MISMATCH(ES)'}")
        return 1 if failures else 0
    if args.table:
        return print_table(spec)
    only = set(args.only.split(",")) if args.only else None
    print(f"{clrsig('--version')[1].strip()}  |  {args.expectations}  |  {args.base_url}")

    with tempfile.TemporaryDirectory() as tmp:
        spec_file = ROOT / spec["spec"]
        failures = 0

        in_spec = set(yaml.safe_load((ROOT / spec["spec"]).read_text(encoding="utf-8"))["paths"])
        covered = covered_paths(spec)
        if in_spec != covered:
            print(f"FAIL  spec and expectations disagree: only in spec {sorted(in_spec - covered)}, only in expectations {sorted(covered - in_spec)}")
            failures += 1

        chosen = set(args.section.split(",")) if args.section else None

        def wanted(name: str) -> bool:
            return chosen is None or name in chosen

        if wanted("cases") and spec.get("cases"):
            failures += run_response_cases(spec, spec_file, args.base_url, only)
        if not only:
            if wanted("whole"):
                failures += run_whole_spec(spec, spec_file, args.base_url)
            if wanted("scenarios"):
                failures += run_scenarios(spec, spec_file)
            if wanted("generation"):
                failures += run_generation(spec, spec_file)
            if wanted("runs"):
                failures += run_runs(spec, spec_file, args.base_url)
            if wanted("sequences"):
                failures += run_sequences(spec, spec_file, args.base_url)
            if wanted("coverage"):
                failures += run_coverage(spec, args.base_url)
            if wanted("drift"):
                failures += run_drift(spec, spec_file)
            if wanted("probes") and spec.get("probes"):
                failures += run_probes(spec, spec_file, args.base_url)

    print(f"\n{'ALL AS EXPECTED' if not failures else str(failures) + ' MISMATCH(ES)'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
