#!/usr/bin/env python3
"""Run everything — tests, validation, figures, deck, notebooks — in one command.

    uv run python scripts/run_all.py              # everything (~4 min)
    uv run python scripts/run_all.py --quick      # tests + validation only (~1 min)
    uv run python scripts/run_all.py --only validation figures

Each stage prints a single status line, so the whole run reads as a checklist. Output
lands in ``runs/<timestamp>/`` with ``runs/latest`` pointing at the newest run; ``runs/``
is gitignored, so nothing here touches version control.

The point of the ``runs/<timestamp>`` layout is that you can run this twice and compare.
``validation_report.json`` carries no timestamp and the model is seeded, so two runs must
be byte-identical — this script hashes it against the previous run and tells you MATCH or
DRIFT. That check is the reason to run it a couple of times rather than once.

Exit code is the number of failed stages, so it is non-zero if anything went wrong.

See ``docs/RUNBOOK.md`` for what to do with the output, and ``docs/VALIDATION.md`` for
what each study means.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
NOTEBOOKS = ["demo", "analysis", "clustering", "prediction"]


@dataclass
class Stage:
    key: str
    title: str
    detail: str
    quick: bool                       # included in --quick
    argv: list[str] | None = None     # a subprocess, or None for a python callable
    fn: object = None
    status: str = "pending"
    seconds: float = 0.0
    lines: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Stage bodies that are not plain subprocesses
# --------------------------------------------------------------------------- #
def run_notebooks(out: Path, log) -> bool:
    """Execute every notebook headless and keep the rendered HTML.

    ``--to html --execute`` runs each cell in a fresh kernel, so a notebook that only
    works because of stale in-memory state fails here. That is the point: it is the
    check that "Run All" would actually work in the meeting.
    """
    outdir = out / "notebooks"
    outdir.mkdir(parents=True, exist_ok=True)
    ok = True
    for name in NOTEBOOKS:
        src = ROOT / "notebooks" / f"{name}.ipynb"
        if not src.exists():
            log(f"    {name:11s} SKIP (not found)")
            continue
        t = time.time()
        r = subprocess.run(
            [sys.executable, "-m", "jupyter", "nbconvert", "--to", "html", "--execute",
             "--ExecutePreprocessor.timeout=1800", "--output-dir", str(outdir), str(src)],
            cwd=ROOT, capture_output=True, text=True,
        )
        if r.returncode == 0:
            log(f"    {name:11s} ok    {time.time() - t:5.1f}s")
        else:
            ok = False
            tail = (r.stderr.strip().splitlines() or ["(no stderr)"])[-3:]
            log(f"    {name:11s} FAILED {time.time() - t:5.1f}s")
            for line in tail:
                log(f"      {line[:160]}")
    return ok


def compare_with_previous(out: Path, log) -> bool:
    """Hash validation_report.json against the previous run — the determinism check."""
    report = out / "validation_report.json"
    if not report.exists():
        log("    no validation report in this run — nothing to compare")
        return True
    digest = hashlib.sha256(report.read_bytes()).hexdigest()
    log(f"    sha256 {digest[:16]}…")

    previous = sorted(
        (d for d in RUNS.iterdir()
         if d.is_dir() and not d.is_symlink() and d != out
         and (d / "validation_report.json").exists()),
        key=lambda d: d.name,
    )
    if not previous:
        log("    first run — nothing to compare against yet. Run this again to check "
            "determinism.")
        return True

    prev = previous[-1]
    prev_digest = hashlib.sha256((prev / "validation_report.json").read_bytes()).hexdigest()
    if prev_digest == digest:
        log(f"    MATCH — byte-identical to runs/{prev.name}. The pipeline is deterministic.")
        return True
    log(f"    DRIFT — differs from runs/{prev.name} (sha256 {prev_digest[:16]}…).")
    log(f"    diff runs/{prev.name}/validation_report.json {out.name}/validation_report.json")
    return False


# --------------------------------------------------------------------------- #
# Stage table
# --------------------------------------------------------------------------- #
def build_stages(out: Path) -> list[Stage]:
    py = [sys.executable]
    return [
        Stage("tests", "Unit & property tests", "pytest -m 'not slow'", quick=True,
              argv=py + ["-m", "pytest", "-q", "-m", "not slow"]),
        Stage("tests-slow", "Pinned validation bounds", "pytest -m slow", quick=False,
              argv=py + ["-m", "pytest", "-q", "-m", "slow"]),
        Stage("validation", "Validation report", "800 x 720 diagnostics, clustering, prediction",
              quick=True,
              argv=py + ["scripts/validation_report.py", "--out", str(out)]),
        Stage("figures", "Model figures", "19 charts, PNG + SVG", quick=False,
              argv=py + ["presentation/scripts/generate_figures.py"]),
        Stage("diagrams", "Diagrams", "5 Mermaid-sourced diagrams", quick=False,
              argv=py + ["presentation/scripts/make_diagrams.py"]),
        # Carries no data, so it does not need the model run the figures stage
        # does — but it writes into the same figures/ directory, so it belongs
        # here rather than beside the diagrams it is not one of.
        Stage("overview", "Overview figure", "f00_overview, PNG + PDF + SVG", quick=True,
              argv=py + ["presentation/scripts/make_overview_figure.py"]),
        Stage("deck", "Status deck", "presentation/status_deck.html", quick=False,
              argv=py + ["presentation/scripts/build_deck.py"]),
        Stage("results", "Results page", "runs/latest/results.html", quick=True,
              argv=py + ["scripts/build_results_page.py", "--out", str(out)]),
        # The three reference pages. `flows` reads only numbers.py, so it is cheap
        # and always in --quick. `savers-debt` needs the validation JSON. The
        # appendix runs its own 800x720 model to measure the tables it documents,
        # which is why it costs about as much as the validation stage and stays
        # out of --quick.
        Stage("flows", "Flows & papers", "runs/latest/flows_and_papers.html", quick=True,
              argv=py + ["scripts/build_flows_page.py", "--out", str(out)]),
        Stage("savers-debt", "Savers & debt", "runs/latest/savers_and_debt.html", quick=True,
              argv=py + ["scripts/build_savers_debt_page.py", "--out", str(out)]),
        Stage("data-appendix", "Dataset appendix",
              "runs/latest/data_appendix.html + features.csv", quick=False,
              argv=py + ["scripts/build_data_appendix.py", "--out", str(out)]),
        # The three paper replications, in one page. Much the most expensive stage:
        # it runs six 1,440-day simulations for the Butaru portfolios on top of the
        # pinned 720-day one, so it is firmly out of --quick.
        Stage("prediction-papers", "Paper replications",
              "runs/latest/prediction_and_papers.html", quick=False,
              argv=py + ["scripts/build_prediction_page.py", "--out", str(out)]),
        Stage("notebooks", "Notebooks", "execute all four headless", quick=False,
              fn=run_notebooks),
        Stage("determinism", "Determinism check", "compare with the previous run", quick=True,
              fn=compare_with_previous),
    ]


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true",
                    help="skip the slow tests, figures, deck and notebooks")
    ap.add_argument("--only", nargs="+", metavar="STAGE",
                    help="run only these stages (see --list)")
    ap.add_argument("--list", action="store_true", help="list the stage keys and exit")
    ap.add_argument("--keep", type=int, default=10,
                    help="how many timestamped runs to keep (default 10)")
    args = ap.parse_args()

    if args.list:
        for s in build_stages(Path("runs/latest")):
            print(f"  {s.key:12s} {s.title:26s} {'[quick]' if s.quick else ''}")
        return 0

    # Timestamped output dir. The name is the only non-deterministic thing produced,
    # and it deliberately lives outside validation_report.json so the hash comparison
    # above compares content and nothing else.
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = RUNS / stamp
    out.mkdir(parents=True, exist_ok=True)

    stages = build_stages(out)
    if args.only:
        keys = {s.key for s in stages}
        unknown = set(args.only) - keys
        if unknown:
            print(f"unknown stage(s): {', '.join(sorted(unknown))}\n"
                  f"known: {', '.join(sorted(keys))}", file=sys.stderr)
            return 1
        stages = [s for s in stages if s.key in set(args.only)]
    elif args.quick:
        stages = [s for s in stages if s.quick]

    log_path = out / "run_all.log"
    log_file = log_path.open("w", encoding="utf-8")

    def log(msg: str = "") -> None:
        print(msg, flush=True)
        log_file.write(msg + "\n")
        log_file.flush()

    log(f"synthitaly — run_all   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"output: {out.relative_to(ROOT)}   stages: {len(stages)}"
        + ("   (--quick)" if args.quick else ""))
    log("")

    t_all = time.time()
    for i, s in enumerate(stages, 1):
        log(f"[{i}/{len(stages)}] {s.title} — {s.detail}")
        t = time.time()
        if s.argv is not None:
            r = subprocess.run(s.argv, cwd=ROOT, capture_output=True, text=True)
            ok = r.returncode == 0
            body = (r.stdout + r.stderr).strip().splitlines()
            for line in body[-12:]:
                log(f"    {line[:170]}")
        else:
            ok = bool(s.fn(out, log))
        s.seconds = time.time() - t
        s.status = "ok" if ok else "FAILED"
        log(f"    -> {s.status}  {s.seconds:.1f}s")
        log("")

    # runs/latest -> this run
    latest = RUNS / "latest"
    if latest.is_symlink() or latest.exists():
        latest.unlink() if latest.is_symlink() else shutil.rmtree(latest)
    latest.symlink_to(out.name)

    # prune old runs, newest kept
    olds = sorted((d for d in RUNS.iterdir() if d.is_dir() and not d.is_symlink()),
                  key=lambda d: d.name)
    for d in olds[:-args.keep] if args.keep > 0 else []:
        shutil.rmtree(d, ignore_errors=True)

    failed = [s for s in stages if s.status != "ok"]
    log("=" * 68)
    for s in stages:
        mark = "ok  " if s.status == "ok" else "FAIL"
        log(f"  {mark}  {s.key:12s} {s.seconds:6.1f}s   {s.title}")
    log("=" * 68)
    log(f"{len(stages) - len(failed)}/{len(stages)} stages ok in {time.time() - t_all:.1f}s")
    log("")
    log("Look at:")
    log("  runs/latest/results.html            the browsable results page  <- start here")
    log("  runs/latest/flows_and_papers.html   money flows, paper map + gap audit")
    log("  runs/latest/savers_and_debt.html    the savers & debt studies")
    log("  runs/latest/data_appendix.html      dataset schemas + summary statistics")
    log("  runs/latest/validation_report.md    every number, as text")
    log("  runs/latest/notebooks/*.html        the executed notebooks")
    log("  presentation/status_deck.html       the full status deck")
    log("  runs/latest/run_all.log             this log")
    if failed:
        log("")
        log(f"FAILED: {', '.join(s.key for s in failed)} — see the output above.")
    log_file.close()
    return len(failed)


if __name__ == "__main__":
    raise SystemExit(main())
