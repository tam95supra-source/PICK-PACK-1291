from pathlib import Path

source_path = Path(__file__).with_name("apply_fixed_signing_beta2.py")
source = source_path.read_text(encoding="utf-8")
source = source.replace('wf = WORKFLOW.read_text(encoding="utf-8")n\n', 'wf = WORKFLOW.read_text(encoding="utf-8")\n')
exec(compile(source, str(source_path), "exec"), {"__name__": "__main__", "__file__": str(source_path)})
