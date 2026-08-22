#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest_path = ROOT / "ops/beta-ota-current.json"
gas_path = ROOT / "google-apps-script/PICK_PACK_API.gs"

m = json.loads(manifest_path.read_text(encoding="utf-8"))
assert m.get("source") == "GITHUB_RELEASE"
assert m.get("channel") == "BETA"
version = str(m["version_name"])
code = int(m["version_code"])
url = str(m["apk_url"])
sha = str(m["sha256"]).lower()
size = int(m["size"])
published = str(m.get("published_at", ""))
notes = str(m.get("notes", f"Pick Pack 1291 Beta {version}"))
mandatory = bool(m.get("mandatory", False))
assert version.startswith("0.4.2-beta.")
assert url.startswith("https://github.com/") and "/releases/download/" in url
assert len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)
assert size > 0

def js(v):
    return json.dumps(v, ensure_ascii=False)

new = f'''// PP_GITHUB_RELEASE_OTA_CANONICAL_V1: metadata is canonical in ops/beta-ota-current.json; APK bytes are GitHub Release assets.
function ppUpdateCheck_(body) {{
  const channel=ppFold_(body.channel||body._app_channel)==='STABLE'?'STABLE':'BETA';
  const current=String(body.current_version||body._app_version||'').trim();
  if(channel==='STABLE') return {{ok:true,source:'GITHUB_RELEASE',channel:'STABLE',available:false,reason:'NO_RELEASE'}};
  const version={js(version)}, available=ppOtaCompare_(version,current)>0;
  const out={{ok:true,source:'GITHUB_RELEASE',channel:'BETA',available:available,version_name:version,version_code:{code},size:{size},published_at:{js(published)},notes:{js(notes)},mandatory:{str(mandatory).lower()}}};
  if(!available)return out;
  out.sha256={js(sha)};
  out.apk_url={js(url)};
  return out;
}}
'''

s = gas_path.read_text(encoding="utf-8")
start = s.find("function ppUpdateCheck_(body) {")
if start < 0:
    raise SystemExit("ppUpdateCheck_ start not found")
next_fn = s.find("function ppJson_(obj)", start)
if next_fn < 0:
    raise SystemExit("ppJson_ anchor not found")
# Replace the entire ppUpdateCheck_ block plus any intervening whitespace.
s = s[:start] + new + "\n" + s[next_fn:]
gas_path.write_text(s, encoding="utf-8")
print(f"Applied canonical GitHub OTA: {version} -> {url}")
