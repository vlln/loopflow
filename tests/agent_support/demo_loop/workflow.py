"""Demo loop workflow — generate binary assets, then request approval."""

from pathlib import Path

meta = {"name": "demo", "description": "Demo loop (BL-057/058)"}

_LOOP_DIR = Path(__file__).resolve().parent


def run(agent, intervene, state, **kwargs):
    # Stage 1: assets agent runs under --mock bash; the prompt is executed as
    # a shell command. gen_assets.py lives in the loop dir; it writes
    # chart.png + report.pdf into the current (run working) directory.
    agent(f"python3 {_LOOP_DIR / 'gen_assets.py'}")
    # Stage 2: request human approval (AC-023, source=workflow, resume=replay).
    state.answer = intervene(
        "approve-chart",
        "批准发布 chart.png 与 report.pdf 吗？",
        options=["批准", "拒绝"],
        allow_custom=False,
    )
    return {"answer": state.answer}
