"""Create a separate competition variant; keep the submitted baseline untouched."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICY = """

## Context budget for this run

- Keep the original issue, expected behavior, current hypothesis and latest test
  result explicit. Separate verified facts from guesses and rejected hypotheses.
- On first inspection, read at most 60 relevant lines of a file. Read the next
  relevant range only when needed. Limit exploratory shell output to relevant
  matches and test failures; never dump an entire repository, log or code graph.
- Pass a bounded assignment: issue, objective, allowed scope, acceptance criteria,
  current evidence locations, and the unresolved question. Do not forward the
  full conversation or repeat all earlier reports, loaded skills or source code.
- Return at most 2500 characters in each role handoff. Preserve required fields,
  the decisive observation, exact targeted test command and outcome, unresolved
  questions, and next action. Save detailed evidence in the existing excluded
  .agent_state directory and return paths plus line ranges. Do not put these
  records in the patch. Never replace evidence with an unsupported summary.
- Read a compact current-state record, not the whole append-only audit history.
  Retrieve an original source or test excerpt when a specific claim needs checking.
- If a report exceeds this handoff budget, request a shorter report with required
  fields instead of copying it wholesale into the next assignment.
- Final patch delivery is exempt from report truncation. Validate the repair and
  call submit_patch as the final tool action; do not paste the whole diff in prose.
"""


def main():
    source = ROOT / "notes/official_kit/submission"
    out = ROOT / "dist/context_variant"
    target = out / "submission"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)
    sampling = target / "configs/sampling.yaml"
    config = yaml.safe_load(sampling.read_text(encoding="utf-8"))
    config["max_output_tokens"] = 8192
    config["thinking_config"]["include_thoughts"] = False
    # Keep thinking_budget=4096: reasoning is enabled, but is not replayed in history.
    sampling.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    for name in ["project-manager", "architect", "worker", "checker", "evaluator"]:
        path = target / "prompts" / (name + ".md")
        path.write_text(path.read_text(encoding="utf-8") + POLICY, encoding="utf-8")
    archive = out / "submission.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(target.rglob("*")):
            if path.is_file():
                z.write(path, path.relative_to(target).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and "agent.yaml" in z.namelist()
    manifest = {
        "variant": "context_budget_v1",
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "changes": ["max_output_tokens 16384 -> 8192", "include_thoughts true -> false",
                    "bounded evidence and handoff instructions"],
        "same_model_roles_tools_and_task_budgets": True,
        "prompt_limits_are_soft_constraints": True,
        "official_model_inference_tested": False,
        "submitted_to_competition": False,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
