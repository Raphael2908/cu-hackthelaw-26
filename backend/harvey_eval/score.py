"""Invoke Harvey Labs' LLM-judge scorer for a run, injecting the Anthropic key and
pandoc into the child process environment in-memory (never written to disk).

The judge + deliverable matcher need harvey-labs' own venv (pandas, pdfplumber,
markitdown, anthropic) and pandoc on PATH to read .docx deliverables, so we shell
out via `uv run --project harvey-labs`. Run with plain python (no backend deps):

    python -m harvey_eval.score --run-id <id> --task <task>
"""

from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HARVEY_ROOT = REPO_ROOT / "harvey-labs"


def _parse_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.split("#", 1)[0].strip().strip('"').strip("'")
    return env


def _find_pandoc_dir(explicit: str | None) -> str | None:
    if explicit and (Path(explicit) / "pandoc.exe").exists():
        return explicit
    scratch = os.environ.get("TEMP", "")
    hits = glob.glob(os.path.join(scratch, "**", "pandoc*", "pandoc.exe"), recursive=True)
    return str(Path(hits[0]).parent) if hits else None


def score_run(run_id: str, task: str, judge_model: str = "claude-sonnet-4-6",
              pandoc_dir: str | None = None) -> int:
    """Score one produced run with Harvey's judge. Key + pandoc are injected into the
    child env in-memory; nothing is written to disk."""
    env = dict(os.environ)
    key = _parse_env(REPO_ROOT / ".env").get("ANTHROPIC_API_KEY", "")
    if not key:
        print("No ANTHROPIC_API_KEY in repo-root .env", file=sys.stderr)
        return 2
    env["ANTHROPIC_API_KEY"] = key

    found = _find_pandoc_dir(pandoc_dir)
    if found:
        env["PATH"] = found + os.pathsep + env.get("PATH", "")
    else:
        print("Warning: pandoc.exe not found; .docx deliverables may not be read.", file=sys.stderr)

    cmd = [
        "uv", "run", "--project", str(HARVEY_ROOT), "python", "-m", "evaluation.run_eval",
        "--run-id", run_id, "--task", task, "--judge-model", judge_model,
    ]
    return subprocess.run(cmd, cwd=str(HARVEY_ROOT), env=env).returncode


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--judge-model", default="claude-sonnet-4-6")
    p.add_argument("--pandoc-dir", default=None)
    args = p.parse_args()
    return score_run(args.run_id, args.task, args.judge_model, args.pandoc_dir)


if __name__ == "__main__":
    raise SystemExit(main())
