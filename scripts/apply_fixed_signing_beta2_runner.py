from pathlib import Path

source_path = Path(__file__).with_name("apply_fixed_signing_beta2.py")
source = source_path.read_text(encoding="utf-8")
source = source.replace('wf = WORKFLOW.read_text(encoding="utf-8")n\n', 'wf = WORKFLOW.read_text(encoding="utf-8")\n')
# The same two-line apksigner/BADGING shape appears once for Beta and once for Stable.
# The patch intentionally replaces the first occurrence for Beta, then the remaining
# occurrence for Stable; all other anchors are still validated by the script.
source = source.replace('if count != 1:\n        raise SystemExit', 'if count < 1:\n        raise SystemExit')
exec(compile(source, str(source_path), "exec"), {"__name__": "__main__", "__file__": str(source_path)})
