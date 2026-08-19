#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
app=ROOT/'service/public/app.js'
css=ROOT/'service/public/styles.css'

s=app.read_text(encoding='utf-8')
old="body:JSON.stringify({login_id:id,challenge_id:c.challenge_id,proof:p,device_id:state.device,device_label:navigator.userAgent.slice(0,100)})"
new="body:JSON.stringify({login_id:id,challenge_id:c.challenge_id,proof:p,device_id:state.device,device_label:navigator.userAgent.slice(0,100),client_source:'WEB'})"
if new not in s:
    if s.count(old)!=1: raise SystemExit(f'S26 web login anchor mismatch: {s.count(old)}')
    s=s.replace(old,new,1)
app.write_text(s,encoding='utf-8')

c=css.read_text(encoding='utf-8')
fix='.login-wrap[hidden],.admin-app[hidden],.notice[hidden]{display:none!important}'
if fix not in c:
    c=fix+c
css.write_text(c,encoding='utf-8')
print('Applied S26 WEB session source + hidden overlay CSS fix')
