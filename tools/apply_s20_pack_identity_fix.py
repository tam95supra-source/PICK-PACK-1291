#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
s=p.read_text()
MARK='S20_PACK_IDENTITY_APPLIED'
if MARK in s:
    print('S20 PACK identity already applied.')
    raise SystemExit(0)

# ENTER screen: the UI already renders table + user-pack, but old code retained only the table.
old='''        val pdas=masters.optJSONArray("pdas")?:JSONArray();val picks=masters.optJSONArray("user_picks")?:JSONArray();val packs=masters.optJSONArray("pack_tables")?:JSONArray()
        val pickValues=mutableListOf<String>();val packValues=mutableListOf<String>();var pdaField:AutoCompleteTextView?=null;var pickSpinner:Spinner?=null;var packSpinner:Spinner?=null
        fun rebuild(){resourceBox.removeAllViews();pickValues.clear();packValues.clear();pdaField=null;pickSpinner=null;packSpinner=null;when(choice.selectedItem.toString()){
'''
new='''        // S20_PACK_IDENTITY_APPLIED: PACK selection preserves the composite table + user-pack identity.
        val pdas=masters.optJSONArray("pdas")?:JSONArray();val picks=masters.optJSONArray("user_picks")?:JSONArray();val packs=masters.optJSONArray("pack_tables")?:JSONArray()
        val pickValues=mutableListOf<String>();val packValues=mutableListOf<String>();val packUsers=mutableListOf<String>();var pdaField:AutoCompleteTextView?=null;var pickSpinner:Spinner?=null;var packSpinner:Spinner?=null
        fun rebuild(){resourceBox.removeAllViews();pickValues.clear();packValues.clear();packUsers.clear();pdaField=null;pickSpinner=null;packSpinner=null;when(choice.selectedItem.toString()){
'''
if s.count(old)!=1: raise SystemExit(f'S20 enter declaration anchor mismatch: {s.count(old)}')
s=s.replace(old,new,1)

old='''            "PACK"->{val labels=mutableListOf<String>();val selectedShift=shift.selectedItem.toString();for(i in 0 until packs.length()){val p=packs.optJSONObject(i)?:continue;if(p.optString("shift")!=selectedShift)continue;val table=p.optString("table");if(table.isNotBlank()){packValues.add(table);labels.add("$table • ${p.optString("user_pack")}")}};packSpinner=spinner((if(labels.isEmpty())listOf("Không có bàn Pack khả dụng")else labels).toTypedArray());resourceBox.addView(labelled("Bàn Pack + User Pack",packSpinner!!))}
'''
new='''            "PACK"->{val labels=mutableListOf<String>();val selectedShift=shift.selectedItem.toString();for(i in 0 until packs.length()){val p=packs.optJSONObject(i)?:continue;if(p.optString("shift")!=selectedShift)continue;val table=p.optString("table");val user=p.optString("user_pack");if(table.isNotBlank()&&user.isNotBlank()){packValues.add(table);packUsers.add(user);labels.add("$table • $user")}};packSpinner=spinner((if(labels.isEmpty())listOf("Không có bàn Pack + User Pack khả dụng")else labels).toTypedArray());resourceBox.addView(labelled("Bàn Pack + User Pack",packSpinner!!))}
'''
if s.count(old)!=1: raise SystemExit(f'S20 enter PACK options anchor mismatch: {s.count(old)}')
s=s.replace(old,new,1)

old='''if(work=="PACK"){if(packValues.isEmpty()){showError("Không còn bàn Pack khả dụng.");return@setOnClickListener};payload.put("pack_table",packValues[packSpinner?.selectedItemPosition?:0])};enter.isEnabled=false;'''
new='''if(work=="PACK"){if(packValues.isEmpty()||packUsers.size!=packValues.size){showError("Không còn cặp Bàn Pack + User Pack khả dụng.");return@setOnClickListener};val ix=packSpinner?.selectedItemPosition?:0;val table=packValues.getOrNull(ix).orEmpty();val user=packUsers.getOrNull(ix).orEmpty();if(table.isBlank()||user.isBlank()){showError("Cặp Bàn Pack + User Pack không hợp lệ.");return@setOnClickListener};payload.put("pack_table",table).put("user_pack",user)};enter.isEnabled=false;'''
if s.count(old)!=1: raise SystemExit(f'S20 enter payload anchor mismatch: {s.count(old)}')
s=s.replace(old,new,1)

# Resource-change screen: same composite identity bug.
old='''        val pdas=masters.optJSONArray("pdas")?:JSONArray();val picks=masters.optJSONArray("user_picks")?:JSONArray();val packs=masters.optJSONArray("pack_tables")?:JSONArray();val pickVals=mutableListOf<String>();val packVals=mutableListOf<String>();var pdaField:AutoCompleteTextView?=null;var pickSp:Spinner?=null;var packSp:Spinner?=null
        fun rebuild(){box.removeAllViews();pickVals.clear();packVals.clear();pdaField=null;pickSp=null;packSp=null;when(choice.selectedItem.toString()){
'''
new='''        val pdas=masters.optJSONArray("pdas")?:JSONArray();val picks=masters.optJSONArray("user_picks")?:JSONArray();val packs=masters.optJSONArray("pack_tables")?:JSONArray();val pickVals=mutableListOf<String>();val packVals=mutableListOf<String>();val packUsers=mutableListOf<String>();var pdaField:AutoCompleteTextView?=null;var pickSp:Spinner?=null;var packSp:Spinner?=null
        fun rebuild(){box.removeAllViews();pickVals.clear();packVals.clear();packUsers.clear();pdaField=null;pickSp=null;packSp=null;when(choice.selectedItem.toString()){
'''
if s.count(old)!=1: raise SystemExit(f'S20 resource declaration anchor mismatch: {s.count(old)}')
s=s.replace(old,new,1)

old='''            "PACK"->{val labels=mutableListOf<String>();for(i in 0 until packs.length()){val p=packs.optJSONObject(i)?:continue;if(p.optString("shift")!=s.optString("shift"))continue;val t=p.optString("table");if(t.isNotBlank()){packVals.add(t);labels.add("$t • ${p.optString("user_pack")}")}};packSp=spinner(labels.toTypedArray());box.addView(labelled("Bàn Pack + User Pack",packSp!!));selectByValue(packSp!!,packVals,s.optString("pack_table"))}
'''
new='''            "PACK"->{val labels=mutableListOf<String>();for(i in 0 until packs.length()){val p=packs.optJSONObject(i)?:continue;if(p.optString("shift")!=s.optString("shift"))continue;val t=p.optString("table");val u=p.optString("user_pack");if(t.isNotBlank()&&u.isNotBlank()){packVals.add(t);packUsers.add(u);labels.add("$t • $u")}};packSp=spinner((if(labels.isEmpty())listOf("Không có bàn Pack + User Pack khả dụng")else labels).toTypedArray());box.addView(labelled("Bàn Pack + User Pack",packSp!!));selectByValue(packSp!!,packVals,s.optString("pack_table"))}
'''
if s.count(old)!=1: raise SystemExit(f'S20 resource PACK options anchor mismatch: {s.count(old)}')
s=s.replace(old,new,1)

old='''if(work=="PACK"){if(packVals.isEmpty()){showError("Không có bàn Pack khả dụng.");return@setOnClickListener};p.put("pack_table",packVals[packSp?.selectedItemPosition?:0])};save.isEnabled=false;'''
new='''if(work=="PACK"){if(packVals.isEmpty()||packUsers.size!=packVals.size){showError("Không có cặp Bàn Pack + User Pack khả dụng.");return@setOnClickListener};val ix=packSp?.selectedItemPosition?:0;val table=packVals.getOrNull(ix).orEmpty();val user=packUsers.getOrNull(ix).orEmpty();if(table.isBlank()||user.isBlank()){showError("Cặp Bàn Pack + User Pack không hợp lệ.");return@setOnClickListener};p.put("pack_table",table).put("user_pack",user)};save.isEnabled=false;'''
if s.count(old)!=1: raise SystemExit(f'S20 resource payload anchor mismatch: {s.count(old)}')
s=s.replace(old,new,1)

p.write_text(s)
print('Applied S20 PACK composite identity fix.')
