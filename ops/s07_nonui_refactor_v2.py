from pathlib import Path
src=Path('ops/s07_nonui_refactor.py').read_text(encoding='utf-8')
old="for banned in ('ACK', 'Server revision', 'Master revision', 'Master data tự làm mới', 'Màu giao diện được đổi'):"
new="for banned in ('server ACK', 'Log local chờ ACK', 'nhận ACK', 'Server revision', 'Master revision', 'Master data tự làm mới', 'Màu giao diện được đổi'):"
if src.count(old)!=1:
    raise SystemExit('S07 copy guard anchor changed')
src=src.replace(old,new,1)
exec(compile(src,'ops/s07_nonui_refactor.py','exec'))
