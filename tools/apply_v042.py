import pathlib

root = pathlib.Path(__file__).resolve().parents[1]

p = root / 'app/src/main/java/vn/pickpack1291/app/beta/MasterDataCache.kt'
s = p.read_text(encoding='utf-8')
old = '.replace(Regex("\\p{Mn}+"), "").uppercase().trim()'
new = '.replace(Regex("\\\\p{Mn}+"), "").uppercase().trim()'
if old not in s:
    raise SystemExit('MasterDataCache regex target missing')
p.write_text(s.replace(old, new, 1), encoding='utf-8')

p = root / 'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
s = p.read_text(encoding='utf-8')
old = 'if(isAdmin()){box.addView(gap(10));box.addView(supportGrid(rootJson.optJSONObject("support")))}'
new = 'if(isAdmin()){box.addView(gap(10));box.addView(supportGrid(rootJson.optJSONObject("support")))}'
# The source needs one more closing parenthesis for box.addView(...).
new = 'if(isAdmin()){box.addView(gap(10));box.addView(supportGrid(rootJson.optJSONObject("support")))}'.replace('))}', ')))}')
if old not in s:
    raise SystemExit('Operations report target missing')
p.write_text(s.replace(old, new, 1), encoding='utf-8')

print('compile fixes applied')
