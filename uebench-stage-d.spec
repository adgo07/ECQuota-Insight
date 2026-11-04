# 水泥隔离验收专用；普通构建始终使用 uebench.spec。
from pathlib import Path

UEBENCH_ENTRY_SCRIPT = "run_stage_d_cement.py"
shared_spec = Path(SPECPATH) / "uebench.spec"
exec(compile(shared_spec.read_text(encoding="utf-8"), str(shared_spec), "exec"))
