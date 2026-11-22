"""Property-style test of clrsig on random valid OpenAPI documents. No server is needed.

    uv run python scripts/fuzz_specs.py                    # seeds 1..30
    uv run python scripts/fuzz_specs.py --count 200 --start 1000

For each seed, `scripts/make_specs.py` builds a random valid OpenAPI 3.0.3 document, and clrsig must:
  1. load it and build one request per operation (`generate --dry-run`: exit 0, the right count);
  2. build every request and probe without crashing or hanging (`conform --negative` against a closed
     port: the connection errors are expected, a panic or a timeout is not);
  3. find no change when it is compared with itself (`diff`: exit 0, "No changes").
Any other outcome is printed with its seed, which reproduces it exactly (`--start SEED --count 1`),
and the script exits 1. A failing seed is a clrsig finding, not something to code around.
"""

import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_specs import dump, random_spec  # noqa: E402

CRASH = ("panic:", "goroutine ", "runtime error")
SLOW_SECONDS = 30


def clrsig(*args: str) -> tuple[int, str, float]:
    started = time.monotonic()
    done = subprocess.run(["clrsig", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return done.returncode, done.stdout + done.stderr, time.monotonic() - started


def check_seed(seed: int, folder: Path) -> list[str]:
    doc = random_spec(seed)
    path = folder / f"random-{seed}.json"
    path.write_text(dump(doc), encoding="utf-8")
    operations = sum(1 for item in doc["paths"].values() for key in item if key != "parameters")
    problems = []

    code, out, _ = clrsig("generate", str(path), "--dry-run")
    if code != 0 or f"{operations} request(s) generated" not in out:
        problems.append(f"generate: exit {code}, expected {operations} requests: {out.strip().splitlines()[-1][:160] if out.strip() else ''}")

    code, out, seconds = clrsig("conform", str(path), "-b", "http://localhost:1", "--request-timeout", "200", "--negative")
    if any(marker in out for marker in CRASH):
        problems.append("conform --negative crashed: " + next(line for line in out.splitlines() if any(m in line for m in CRASH))[:160])
    if code not in (0, 1):
        problems.append(f"conform --negative: exit {code}: {out.strip().splitlines()[-1][:160] if out.strip() else ''}")
    if seconds > SLOW_SECONDS:
        problems.append(f"conform --negative took {seconds:.0f} s")

    code, out, _ = clrsig("diff", str(path), str(path))
    if code != 0 or "No changes" not in out:
        problems.append(f"diff with itself: exit {code}: {out.strip().splitlines()[-1][:160] if out.strip() else ''}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--count", type=int, default=30)
    args = parser.parse_args()
    version = subprocess.run(["clrsig", "--version"], capture_output=True, text=True).stdout.strip()
    print(f"{version}  |  random specs, seeds {args.start}..{args.start + args.count - 1}")
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        for seed in range(args.start, args.start + args.count):
            problems = check_seed(seed, Path(tmp))
            failures += bool(problems)
            print(f"  {'ok  ' if not problems else 'FAIL'}  seed {seed}")
            for problem in problems:
                print(f"        - {problem}")
    print("\nALL AS EXPECTED" if not failures else f"\n{failures} SEED(S) FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
