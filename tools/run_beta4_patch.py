from pathlib import Path
import runpy

p = Path('tools/apply_beta4_minimal_teal.py')
s = p.read_text(encoding='utf-8')
old = "anchor = '    private fun input(hintValue:String,password:Boolean)=EditText(this).apply{'"
idx = s.rfind(old)
if idx < 0:
    raise SystemExit('operations input anchor assignment not found')
s = s[:idx] + "anchor = '    private fun input(h:String,password:Boolean)=EditText(this).apply{'" + s[idx + len(old):]
p.write_text(s, encoding='utf-8')
runpy.run_path(str(p), run_name='__main__')
