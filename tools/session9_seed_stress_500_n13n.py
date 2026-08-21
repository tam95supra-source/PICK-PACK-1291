#!/usr/bin/env python3
import os,sys,json,random,hashlib,urllib.request,urllib.parse
from datetime import date,datetime,timedelta,timezone

N=date.fromisoformat(os.environ.get('N_DATE','2026-08-20'))
START_SEQ=int(os.environ.get('START_SEQ','0'))
EPOCH=int(os.environ.get('AUTH_EPOCH','8'))
GEN=os.environ.get('SERVICE_GENERATION','m2-prod')
SHEET_ID=os.environ.get('SHEET_ID','1E7ZWz-4eMcBliQxDYBVoogIoeSYyiaXGwj0I6mbMm78')
TZ=timezone(timedelta(hours=7)); RNG=random.Random(12910820)
NOTE='STRESS TEST 500 N13-N'; ACTOR='tamnv2'; DEVICE='stress-seed-20260820'

POSITIONS=['Trưởng kho','Trưởng nhóm','Chuyên viên','Điều phối','Tổ trưởng','Kéo hàng','5S','Phúc Long','Pick','Pack']
SUPPLIERS=['Nguồn Lực Việt','Hoa Anh Đào','Việt Work','Man Power','Mega Link','Hà Gia Phát','Inhouse']
DEPTS=['Pick Pack','Invent','Outbound','Inbound','Giao vận','Khác']; WARE=['HY1','HY2']
LABOR_TYPES=['Hỗ trợ 1399','Hỗ trợ 1386','Hỗ trợ 1368','Hỗ trợ Inbound','Hỗ trợ Outbound','Hỗ trợ Invent','Hỗ trợ scan lại vị trí trong pickface','Hỗ trợ 5S','Chờ kế hoạch','Hỗ trợ Pick','Hỗ trợ Pack','Hỗ trợ thay thế điều phối chẵn','Hỗ trợ thay thế điều phối lẻ','Hỗ trợ thay thế điều phối chờ xuất','Hỗ trợ Pick Pack Phúc Long','Khác']
MARKERS=['Trong ngày','Qua 24:00','Sau 24:00']
SURN=['Nguyễn','Trần','Lê','Phạm','Hoàng','Huỳnh','Phan','Vũ','Võ','Đặng','Bùi','Đỗ','Hồ','Ngô','Dương','Lý','Đinh','Mai','Tạ','Chu']
MIDS=['Văn','Hữu','Đức','Thanh','Minh']; GIVENS=['An','Bình','Dũng','Hải','Nam']

def sh(v): return v.strftime('%d/%m/%Y %H:%M:%S')
def sd(v): return v.strftime('%d/%m/%Y')
def iso(v): return v.isoformat(timespec='seconds')
def q(v):
    if v is None:return 'NULL'
    if isinstance(v,(int,float)):return str(v)
    return "'"+str(v).replace("'","''")+"'"
def h(v): return hashlib.sha256(v.encode()).hexdigest()
def multi(table,cols,rows,n=100):
    out=[]
    for i in range(0,len(rows),n):
        vals=',\n'.join('('+','.join(q(x) for x in r)+')' for r in rows[i:i+n])
        out.append(f"INSERT INTO {table}({','.join(cols)}) VALUES\n{vals};")
    return '\n'.join(out)

def generate():
    staff=[]; staff_sheet=[]
    start0=date(2023,1,1); span=(date(2026,8,1)-start0).days
    for i in range(500):
        s=SURN[i//25]; rem=i%25; m=MIDS[rem//5]; g=GIVENS[rem%5]
        mnv=str(30001+i); full=f'{s} {m} {g}'; phone=f"0{RNG.choice([3,5,7,8,9])}{RNG.randrange(100000000):08d}"
        pos=RNG.choice(POSITIONS); sup=RNG.choice(SUPPLIERS); dep=RNG.choice(DEPTS); wh=RNG.choice(WARE); st=start0+timedelta(days=RNG.randrange(span+1))
        row=[mnv,full,phone,pos,sup,dep,'1291',wh,sd(st),NOTE,ACTOR,'20/08/2026 16:57:00']
        staff_sheet.append(row); checksum=h(json.dumps(row[:10],ensure_ascii=False,separators=(',',':')))
        staff.append({'mnv':mnv,'full':full,'phone':phone,'pos':pos,'sup':sup,'dep':dep,'site':'1291','wh':wh,'start':sd(st),'note':NOTE,'source_row':i+2,'checksum':checksum})
    seq=START_SEQ; att_rows=[]; lab_rows=[]; event_rows=[]; ra_sheet=[]; labor_sheet=[]
    days=[N-timedelta(days=x) for x in range(13,-1,-1)]
    def evrow(eid,etype,entity_type,entity_id,bdate,basev,newv,when,payload,seqno):
        p=json.dumps(payload,ensure_ascii=False,separators=(',',':')); chk=h('|'.join([eid,etype,entity_id,bdate,str(seqno),p]))
        return [eid,etype,entity_type,entity_id,bdate,EPOCH,seqno,GEN,basev,newv,ACTOR,'SUPERADMIN',DEVICE,iso(when),iso(when),p,eid,'STRESS_SEED',1,chk]
    attendance_by_day={}
    for di,d in enumerate(days):
        roster=RNG.sample(staff,360); daymap={}
        for j,e in enumerate(roster,1):
            shift=RNG.choices(['Ca 1','Ca 2','Ca HC'],weights=[40,35,25])[0]
            work_sheet=RNG.choices(['Không','Pick','Pack'],weights=[25,40,35])[0]; work={'Không':'KHONG','Pick':'PICK','Pack':'PACK'}[work_sheet]
            if shift=='Ca 1': hh,base=6,RNG.randrange(0,91)
            elif shift=='Ca HC': hh,base=8,RNG.randrange(0,61)
            else: hh,base=14,RNG.randrange(0,91)
            ent=datetime(d.year,d.month,d.day,hh,0,tzinfo=TZ)+timedelta(minutes=base)
            ex=ent+timedelta(minutes=RNG.randrange(450,541))
            sid=f'STRESS-S-{d:%Y%m%d}-{j:03d}'; ein=f'STRESS-RA-{d:%Y%m%d}-{j:03d}-ENTER'; eout=f'STRESS-RA-{d:%Y%m%d}-{j:03d}-EXIT'
            seq+=1; seq_in=seq; seq+=1; seq_out=seq
            source_last=2+di*720+(j-1)*2+1
            att_rows.append([sid,e['mnv'],d.isoformat(),shift,work,'ENDED',None,None,None,None,iso(ent),iso(ex),ACTOR,ACTOR,2,source_last,iso(ex)])
            p={'mnv':e['mnv'],'shift':shift,'work_choice':work,'note':NOTE}
            event_rows.append(evrow(ein,'ATTENDANCE_ENTER','ATTENDANCE_SESSION',sid,d.isoformat(),0,1,ent,p,seq_in))
            event_rows.append(evrow(eout,'ATTENDANCE_EXIT','ATTENDANCE_SESSION',sid,d.isoformat(),1,2,ex,p,seq_out))
            common=[sd(d),shift,e['mnv'],e['full'],e['phone'],e['sup'],e['dep'],'1291',e['wh'],e['pos'],work_sheet,'','','','']
            ra_sheet.append(common+['VÀO',NOTE,ACTOR,sh(ent),ein,'ENTER',seq_in])
            ra_sheet.append(common+['RA',NOTE,ACTOR,sh(ex),eout,'EXIT',seq_out])
            daymap[e['mnv']]={'emp':e,'shift':shift,'work_sheet':work_sheet,'work':work,'enter':ent,'exit':ex}
        attendance_by_day[d.isoformat()]=daymap
        people=RNG.sample(list(daymap.values()),250); tasks=people+RNG.sample(people,50)
        for k,sess in enumerate(tasks,1):
            e=sess['emp']; ltype=RNG.choice(LABOR_TYPES); marker=RNG.choice(MARKERS)
            available=max(1,int((sess['exit']-sess['enter']).total_seconds()//60)-150)
            st=sess['enter']+timedelta(minutes=30+RNG.randrange(available)); en=min(sess['exit']-timedelta(minutes=5),st+timedelta(minutes=RNG.randrange(30,91)))
            lid=f'STRESS-L-{d:%Y%m%d}-{k:03d}'; se=f'{lid}-START'; fe=f'{lid}-FINISH'
            fixed=e['pos'] in ('Kéo hàng','Tổ trưởng'); deduct=0 if fixed else (1 if RNG.random()<0.25 else 0)
            seq+=1; ss=seq; seq+=1; fs=seq
            lab_rows.append([lid,e['mnv'],d.isoformat(),sess['shift'],ltype,marker,'COMPLETED',iso(st),iso(en),NOTE,deduct,se,fe,2,2+di*300+(k-1),iso(en)])
            ps={'mnv':e['mnv'],'shift':sess['shift'],'labor_type':ltype,'time_marker':marker,'deduct_staff':bool(deduct),'note':NOTE}
            event_rows.append(evrow(se,'LABOR_START','LABOR_SESSION',lid,d.isoformat(),0,1,st,ps,ss))
            event_rows.append(evrow(fe,'LABOR_FINISH','LABOR_SESSION',lid,d.isoformat(),1,2,en,ps,fs))
            labor_sheet.append([sd(d),sess['shift'],e['mnv'],e['full'],e['phone'],e['sup'],e['dep'],'1291',e['wh'],e['pos'],sess['work_sheet'],ltype,sh(st),sh(en),marker,'Hoàn thành',NOTE,ACTOR,sh(en+timedelta(minutes=1)),se,fe,fs,'Có' if deduct else 'Không'])
    assert len(staff_sheet)==500 and len(att_rows)==5040 and len(ra_sheet)==10080 and len(lab_rows)==4200 and len(labor_sheet)==4200 and len(event_rows)==18480
    return staff,staff_sheet,att_rows,lab_rows,event_rows,ra_sheet,labor_sheet,seq,days

def write_sql(path):
    staff,staff_sheet,att,lab,events,ra,lsh,last_seq,days=generate()
    sql=["PRAGMA foreign_keys=ON;",
         "DELETE FROM events WHERE event_type IN ('ATTENDANCE_ENTER','ATTENDANCE_EXIT','LABOR_START','LABOR_FINISH','MASTER_STAFF_UPSERT','MASTER_STAFF_DELETE','MASTER_STAFF_IMPORT');",
         "DELETE FROM labor_sessions;","DELETE FROM attendance_sessions;","DELETE FROM employees;",
         "DELETE FROM source_rows WHERE sheet_name IN ('DANH SÁCH NHÂN SỰ','RA - VÀO TRONG CA','CÔNG NHẬT');",
         "DELETE FROM conflicts WHERE entity_type IN ('ATTENDANCE_SESSION','LABOR_SESSION','EMPLOYEE');"]
    sql.append(multi('employees',['mnv','full_name','phone','main_position','supplier','department','site','warehouse','start_date','note','source_row','source_checksum'],[[e['mnv'],e['full'],e['phone'],e['pos'],e['sup'],e['dep'],e['site'],e['wh'],e['start'],e['note'],e['source_row'],e['checksum']] for e in staff],100))
    sql.append(multi('attendance_sessions',['session_id','mnv','business_date','shift','work_choice','state','pda_serial','user_pick','pack_table','user_pack','enter_at','exit_at','entered_by','exited_by','version','source_last_row','updated_at'],att,80))
    sql.append(multi('labor_sessions',['labor_id','mnv','business_date','shift','labor_type','time_marker','state','start_at','end_at','note','deduct_staff','start_event_id','finish_event_id','version','source_row','updated_at'],lab,80))
    sql.append(multi('events',['event_id','event_type','entity_type','entity_id','business_date','authority_epoch','authority_seq','service_generation','base_version','new_version','actor_id','actor_role','device_id','occurred_at','committed_at','payload_json','idempotency_key','origin','schema_version','checksum'],events,60))
    ds=','.join(q(d.isoformat()) for d in days); sql.append(f"UPDATE business_dates SET source='STRESS_SEED' WHERE business_date IN ({ds});")
    sql.append("UPDATE revision_state SET revision=revision+1,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE namespace='employees';")
    sql.append(f"UPDATE authority_state SET authority_seq={last_seq},updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE singleton_id=1;")
    sql.append("DELETE FROM mutation_assertions WHERE event_id NOT IN (SELECT event_id FROM events);")
    open(path,'w',encoding='utf-8').write('\n'.join(sql))
    print(json.dumps({'staff':500,'attendance_sessions':5040,'ra_rows':10080,'labor_sessions':4200,'labor_rows':4200,'events':18480,'last_seq':last_seq,'from':days[0].isoformat(),'to':days[-1].isoformat()},ensure_ascii=False))

def http_json(url,method='GET',headers=None,body=None):
    data=None if body is None else json.dumps(body,ensure_ascii=False,separators=(',',':')).encode()
    req=urllib.request.Request(url,data=data,method=method,headers=headers or {})
    with urllib.request.urlopen(req,timeout=90) as r:return json.loads(r.read().decode() or '{}')
def token():
    form=urllib.parse.urlencode({'client_id':os.environ['GOOGLE_OAUTH_CLIENT_ID'],'client_secret':os.environ['GOOGLE_OAUTH_CLIENT_SECRET'],'refresh_token':os.environ['GOOGLE_OAUTH_REFRESH_TOKEN'],'grant_type':'refresh_token'}).encode()
    req=urllib.request.Request('https://oauth2.googleapis.com/token',data=form,method='POST',headers={'Content-Type':'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read().decode())['access_token']
def enc_range(r): return urllib.parse.quote(r,safe='')
def getvals(tok,r): return http_json(f'https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{enc_range(r)}',headers={'Authorization':f'Bearer {tok}'})
def fp_google(tok):
    ranges=["'Danh mục'!A1:Z1000","'DANH SÁCH PDA'!A1:Z1000","'DANH SÁCH USER PICK'!A1:Z1000","'DANH SÁCH BÀN PACK'!A1:Z1000","'DANH SÁCH USER PACK'!A1:Z1000"]
    out={}
    for r in ranges: out[r]=hashlib.sha256(json.dumps(getvals(tok,r).get('values',[]),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    return out

def google_seed():
    _,staff,_,_,_,ra,labor,_,days=generate(); tok=token(); hdr={'Authorization':f'Bearer {tok}','Content-Type':'application/json'}; before=fp_google(tok)
    http_json(f'https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values:batchClear','POST',hdr,{'ranges':["'DANH SÁCH NHÂN SỰ'!A2:L997","'RA - VÀO TRONG CA'!A2:V11007","'CÔNG NHẬT'!A2:W10777"]})
    def put(r,vals): http_json(f'https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values:batchUpdate','POST',hdr,{'valueInputOption':'USER_ENTERED','data':[{'range':r,'majorDimension':'ROWS','values':vals}]})
    put("'DANH SÁCH NHÂN SỰ'!A2:L501",staff)
    for i in range(0,len(ra),1000): put(f"'RA - VÀO TRONG CA'!A{i+2}:V{i+1+len(ra[i:i+1000])}",ra[i:i+1000])
    for i in range(0,len(labor),1000): put(f"'CÔNG NHẬT'!A{i+2}:W{i+1+len(labor[i:i+1000])}",labor[i:i+1000])
    after=fp_google(tok)
    if before!=after: raise SystemExit('NON_TARGET_GOOGLE_FINGERPRINT_CHANGED')
    sc=len(getvals(tok,"'DANH SÁCH NHÂN SỰ'!A2:A501").get('values',[])); rc=len(getvals(tok,"'RA - VÀO TRONG CA'!A2:A10081").get('values',[])); lc=len(getvals(tok,"'CÔNG NHẬT'!A2:A4201").get('values',[]))
    if (sc,rc,lc)!=(500,10080,4200): raise SystemExit(f'GOOGLE_COUNTS_BAD:{sc},{rc},{lc}')
    summary={'staff_rows':sc,'ra_rows':rc,'labor_rows':lc,'from':days[0].isoformat(),'to':days[-1].isoformat(),'non_target_fingerprint':'PASS'}
    open('/tmp/session9-google-summary.json','w').write(json.dumps(summary)); print(json.dumps(summary))

if __name__=='__main__':
    if '--sql' in sys.argv: write_sql('/tmp/session9_seed.sql')
    elif '--google' in sys.argv: google_seed()
    else: print('use --sql or --google',file=sys.stderr);sys.exit(2)
