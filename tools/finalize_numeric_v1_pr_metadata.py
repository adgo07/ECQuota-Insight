from pathlib import Path

report = Path("docs/governance/NUMERIC_V1_ADOPTION_REPORT.md")
text = report.read_text(encoding="utf-8")
old = "PR: to be assigned after governance cleanup; PR must not be self-merged."
new = "PR: `#4` — `https://github.com/adgo07/ECQuota-Insight/pull/4`; execution task must not self-merge it."
if text.count(old) != 1:
    raise SystemExit(f"Expected exactly one report PR placeholder, got {text.count(old)}")
report.write_text(text.replace(old, new, 1), encoding="utf-8")

task = Path("TASK_STATE.md")
text = task.read_text(encoding="utf-8")
anchor = "不要自行合并 PR。"
replacement = "PR：`#4` — `https://github.com/adgo07/ECQuota-Insight/pull/4`。\n\n不要自行合并 PR。"
if "pull/4" not in text:
    if text.count(anchor) != 1:
        raise SystemExit(f"Expected exactly one TASK_STATE PR anchor, got {text.count(anchor)}")
    text = text.replace(anchor, replacement, 1)
    task.write_text(text, encoding="utf-8")

print("Final PR metadata written")
