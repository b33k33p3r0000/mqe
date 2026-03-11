#!/usr/bin/env python3
"""Build dynamic prompt for Claude Code agent iteration.

Usage:
    python3 agent/build_prompt.py decide       → prompt for "analyze + implement"
    python3 agent/build_prompt.py evaluate_val  → prompt for "evaluate validation run"
    python3 agent/build_prompt.py evaluate_full → prompt for "compare with best"
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


AGENT_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = AGENT_DIR / "agent_prompt.md"
STATE_PATH = AGENT_DIR / "state.json"
HISTORY_PATH = AGENT_DIR / "history.json"


TASK_INSTRUCTIONS = {
    "decide": """Analyze the previous run results and decide what to change next.

1. Read the results from the latest run (path in state)
2. Read key source files to understand current configuration
3. Based on your level ({{LEVEL}}), propose ONE change that will improve the Resilience Score
4. Implement the change in the codebase
5. Commit to the current branch with message: "agent(iter-{{ITERATION}}): <description>"
6. Write agent/decision.json with action="implement"

If you believe the current result is optimal (Score >= 85 AND improvements are plateauing),
write decision.json with action="stop" and stop_reason="top_achieved".
""",
    "evaluate_val": """Evaluate the validation run results.

1. Read results from: {{VAL_RUN_DIR}}
2. Check if the change shows promise (directional improvement)
3. Write agent/decision.json:
   - action="implement" with run_mode="full" if promising
   - action="rollback" if not promising

Write your assessment to stdout. Be concise.
""",
    "evaluate_full": """Compare the full run with the current best.

1. Read full run results from: {{FULL_RUN_DIR}}
2. Compute Resilience Score: python3 agent/resilience.py compute-score {{FULL_RUN_DIR}}
3. Compare with best_score={{BEST_SCORE}}
4. If new_score > best_score + 1.0: write decision.json with action="promote"
5. If new_score <= best_score + 1.0: write decision.json with action="rollback"
6. Check stop conditions:
   - Score >= 85 AND last 3 iters < 2pts improvement → action="stop", stop_reason="top_achieved"
   - Level L3 AND 2 consecutive no-improvement → action="stop", stop_reason="plateau_exhaustion"
""",
}


def load_history(max_recent: int = 10) -> tuple:
    """Load history with windowing. Returns (recent_detail, lessons_learned)."""
    if not HISTORY_PATH.exists():
        return "No history yet.", "No lessons yet."

    history = json.loads(HISTORY_PATH.read_text())
    if not history:
        return "No history yet.", "No lessons yet."

    # Recent entries (full detail)
    recent = history[-max_recent:]
    recent_lines = []
    for entry in recent:
        status = "PROMOTE" if entry.get("result") == "promote" else "ROLLBACK"
        recent_lines.append(
            f"- Iter {entry['iteration']} ({entry['level']}): "
            f"{entry['change_description']} → {status} "
            f"(score: {entry.get('score', 'N/A')})"
        )

    # Lessons learned (aggregated from ALL rollbacks)
    failures: Dict[str, int] = {}
    for entry in history:
        if entry.get("result") == "rollback":
            desc = entry.get("change_description", "unknown")
            category = desc.split(":")[0] if ":" in desc else desc[:50]
            failures[category] = failures.get(category, 0) + 1

    lessons_lines = []
    for category, count in sorted(failures.items(), key=lambda x: -x[1]):
        lessons_lines.append(f"- {category}: tried {count}x, never improved")

    return (
        "\n".join(recent_lines) if recent_lines else "No history yet.",
        "\n".join(lessons_lines) if lessons_lines else "No failed patterns yet.",
    )


def build_prompt(task_type: str, extra_vars: Dict[str, str] = None) -> str:
    """Build the full prompt from template + dynamic state."""
    template = TEMPLATE_PATH.read_text()

    # Load state
    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}

    # Load history
    history_text, lessons_text = load_history()

    # Build replacements
    replacements = {
        "{{ITERATION}}": str(state.get("iteration", 0)),
        "{{LEVEL}}": state.get("level", "L1"),
        "{{BEST_SCORE}}": str(state.get("best_score", 0)),
        "{{BEST_RUN}}": state.get("best_run", ""),
        "{{NO_IMPROVEMENT_COUNT}}": str(state.get("consecutive_no_improvement", 0)),
        "{{TASK_TYPE}}": task_type,
        "{{TASK_INSTRUCTIONS}}": TASK_INSTRUCTIONS.get(task_type, ""),
        "{{HISTORY_COUNT}}": str(min(10, len(json.loads(HISTORY_PATH.read_text())) if HISTORY_PATH.exists() else 0)),
        "{{HISTORY}}": history_text,
        "{{LESSONS_LEARNED}}": lessons_text,
        "{{FORENSICS_CONTEXT}}": "",
    }

    if extra_vars:
        for key, val in extra_vars.items():
            replacements[f"{{{{{key}}}}}"] = val

    # Handle FORENSICS_CONTEXT_FILE — read file content and inject
    forensics_file = extra_vars.get("FORENSICS_CONTEXT_FILE") if extra_vars else None
    if forensics_file:
        forensics_path = Path(forensics_file)
        if forensics_path.exists():
            replacements["{{FORENSICS_CONTEXT}}"] = forensics_path.read_text(encoding="utf-8")

    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)

    return result


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: build_prompt.py <task_type> [key=value ...]")
        print("Task types: decide, evaluate_val, evaluate_full")
        sys.exit(1)

    task_type = sys.argv[1]
    extra_vars = {}
    for arg in sys.argv[2:]:
        if "=" in arg:
            key, val = arg.split("=", 1)
            extra_vars[key] = val

    prompt = build_prompt(task_type, extra_vars)
    print(prompt)


if __name__ == "__main__":
    main()
