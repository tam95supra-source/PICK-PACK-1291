import pathlib, re

root = pathlib.Path(__file__).resolve().parents[1]

p = root / 'app/src/main/java/vn/pickpack1291/app/beta/MasterDataCache.kt'
s = p.read_text(encoding='utf-8')
s2 = s.replace('Regex("\\p{Mn}+")', 'Regex("\\\\p{Mn}+")')
if s2 == s:
    raise SystemExit('MasterDataCache regex target missing')
p.write_text(s2, encoding='utf-8')

p = root / 'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
s = p.read_text(encoding='utf-8')
pattern = r'(?m)^\s*if\(isAdmin\(\)\)\{box\.addView\(gap\(10\)\);box\.addView\(supportGrid\(rootJson\.optJSONObject\("support"\)\).*?$'
replacement = '                if(isAdmin()){box.addView(gap(10));box.addView(supportGrid(rootJson.optJSONObject("support")))}'
s2, n = re.subn(pattern, replacement, s, count=1)
if n != 1:
    raise SystemExit('Operations report target missing')
p.write_text(s2, encoding='utf-8')

print('compile fixes applied')
