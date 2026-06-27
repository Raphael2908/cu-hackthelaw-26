"""Q-light — a single Harvey-anchored holistic quality score in [0,1] for a produced deliverable.

One independent judge call (claude-sonnet-4-6) grading the rendered deliverable against the task
brief. This is the cheap proxy for the y-axis in Track C — NOT the 46-criterion rubric judge
(that is Q-full / Track A). It is deliberately independent of our own pipeline/provider so a
correlation against our supervision `uncertainty` isn't us grading ourselves. See TRACK_C_PLAN.md.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import anthropic

REPO_ROOT = Path(__file__).resolve().parents[3]
HARVEY_ROOT = REPO_ROOT / "harvey-labs"
TASKS_ROOT = HARVEY_ROOT / "tasks"
RESULTS_ROOT = HARVEY_ROOT / "results"
JUDGE_MODEL = "claude-sonnet-4-6"
# Sonnet 4.6 list price, USD per 1M tokens (in / out). Used only for a rough cost line.
_PRICE_IN, _PRICE_OUT = 3.0, 15.0


def _load_key() -> None:
    """Inject ANTHROPIC_API_KEY from the repo-root .env if not already set."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    env = REPO_ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("ANTHROPIC_API_KEY="):
            val = line.split("=", 1)[1].split("#")[0].strip().strip('"').strip("'")
            if val:
                os.environ["ANTHROPIC_API_KEY"] = val


def _deliverable_text(run_id: str) -> str:
    import docx

    out_dir = RESULTS_ROOT / run_id / "output"
    parts: list[str] = []
    for path in sorted(out_dir.glob("*.docx")):
        document = docx.Document(str(path))
        body = "\n".join(p.text for p in document.paragraphs if p.text.strip())
        parts.append(f"===== {path.name} =====\n{body}")
    if not parts:
        raise FileNotFoundError(f"no .docx deliverable under {out_dir}")
    return "\n\n".join(parts)


def _task_brief(task_id: str) -> tuple[str, str]:
    cfg = json.loads(
        (TASKS_ROOT / Path(*task_id.split("/")) / "task.json").read_text(encoding="utf-8")
    )
    return cfg.get("title", task_id), cfg.get("instructions", "")


_PROMPT = """You are a senior lawyer grading a junior's work-product deliverable against its task brief.

TASK: {title}

INSTRUCTIONS:
{instructions}

DELIVERABLE:
{deliverable}

Rate how well the DELIVERABLE satisfies the TASK on a continuous scale from 0.0 (does not address
the task at all) to 1.0 (fully satisfies every requirement to a high professional standard). Judge
substance: are the required issues identified, recommendations made, and figures correct?

Respond ONLY with JSON: {{"quality": <float between 0 and 1>, "reasoning": "<one sentence>"}}."""


def score_quality_light(task_id: str, run_id: str) -> dict:
    """Return {quality, reasoning, judge_model, usage} for one task's deliverable."""
    _load_key()
    title, instructions = _task_brief(task_id)
    deliverable = _deliverable_text(run_id)
    prompt = _PROMPT.format(
        title=title, instructions=instructions[:20000], deliverable=deliverable[:40000]
    )
    client = anthropic.Anthropic(max_retries=1)
    resp = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=500,
        temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"judge returned no JSON: {text[:200]}")
    data = json.loads(match.group(0))
    u = resp.usage
    cost = (u.input_tokens * _PRICE_IN + u.output_tokens * _PRICE_OUT) / 1_000_000
    return {
        "quality": max(0.0, min(1.0, float(data["quality"]))),
        "reasoning": data.get("reasoning", ""),
        "judge_model": JUDGE_MODEL,
        "usage": {
            "input_tokens": u.input_tokens,
            "output_tokens": u.output_tokens,
            "cost_usd": round(cost, 5),
        },
    }
