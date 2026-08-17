create table if not exists public.pp_command_receipts (
  event_id uuid primary key,
  command_type text not null,
  business_date date not null,
  mnv text not null,
  session_id uuid not null references public.pp_work_sessions(id) on delete cascade,
  actor_login text not null references public.pp_accounts(login_id),
  result jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.pp_command_receipts enable row level security;
revoke all on table public.pp_command_receipts from public, anon, authenticated;
grant select, insert on table public.pp_command_receipts to service_role;

create or replace function public.pp_change_resources(
  p_event_id uuid,
  p_business_date date,
  p_mnv text,
  p_work_choice text,
  p_pda_serial text,
  p_user_pick text,
  p_pack_table text,
  p_user_pack text,
  p_operator text
)
returns jsonb
language plpgsql
security definer
set search_path to 'public'
as $function$
declare
  v_existing public.pp_events%rowtype;
  v_receipt public.pp_command_receipts%rowtype;
  s public.pp_work_sessions%rowtype;
  old_s jsonb;
  v_seq bigint;
  v_result jsonb;
  v_work_choice text := upper(btrim(coalesce(p_work_choice,'')));
  v_pda_serial text := nullif(btrim(coalesce(p_pda_serial,'')),'');
  v_user_pick text := nullif(btrim(coalesce(p_user_pick,'')),'');
  v_pack_table text := nullif(btrim(coalesce(p_pack_table,'')),'');
  v_user_pack text := nullif(btrim(coalesce(p_user_pack,'')),'');
begin
  select * into v_existing from public.pp_events where event_id=p_event_id;
  if found then
    select * into s from public.pp_work_sessions where id=v_existing.session_id;
    return jsonb_build_object('ok',true,'idempotent',true,'changed',true,'server_seq',v_existing.server_seq,'session',to_jsonb(s));
  end if;

  select * into v_receipt from public.pp_command_receipts where event_id=p_event_id;
  if found then
    return v_receipt.result || jsonb_build_object('idempotent',true);
  end if;

  perform pg_advisory_xact_lock(hashtextextended(p_mnv || '|' || p_business_date::text, 0));
  select * into s from public.pp_work_sessions where business_date=p_business_date and mnv=p_mnv for update;
  if not found then raise exception 'PP_SESSION_NOT_ENTERED'; end if;
  if s.state <> 'ACTIVE' then raise exception 'PP_SESSION_ALREADY_ENDED'; end if;

  if v_work_choice not in ('PICK','PACK','KHÔNG') then raise exception 'PP_WORK_CHOICE_INVALID'; end if;
  if v_work_choice='PICK' and v_pda_serial is null then raise exception 'PP_PDA_REQUIRED'; end if;
  if v_work_choice='PACK' and (v_pack_table is null or v_user_pack is null) then raise exception 'PP_PACK_BUNDLE_REQUIRED'; end if;
  if v_work_choice='KHÔNG' and (v_pda_serial is not null or v_user_pick is not null or v_pack_table is not null or v_user_pack is not null) then raise exception 'PP_RESOURCE_NOT_ALLOWED'; end if;

  if s.work_choice is not distinct from v_work_choice
     and s.pda_serial is not distinct from v_pda_serial
     and s.user_pick is not distinct from v_user_pick
     and s.pack_table is not distinct from v_pack_table
     and s.user_pack is not distinct from v_user_pack then
    v_result := jsonb_build_object(
      'ok',true,
      'idempotent',false,
      'changed',false,
      'server_seq',s.server_seq,
      'session',to_jsonb(s)
    );
    insert into public.pp_command_receipts(event_id,command_type,business_date,mnv,session_id,actor_login,result)
    values (p_event_id,'RESOURCE_CHANGE_NOOP',p_business_date,p_mnv,s.id,p_operator,v_result);
    return v_result;
  end if;

  old_s := to_jsonb(s);

  if v_pda_serial is not null and v_pda_serial is distinct from s.pda_serial then
    begin insert into public.pp_resource_current(resource_type,resource_key,session_id,mnv) values ('PDA',v_pda_serial,s.id,p_mnv);
    exception when unique_violation then raise exception 'PP_RESOURCE_CONFLICT:PDA:%',v_pda_serial; end;
  end if;

  if v_user_pick is not null and v_user_pick is distinct from s.user_pick then
    begin insert into public.pp_day_user_consumption(business_date,resource_type,resource_key,first_session_id,first_mnv) values (p_business_date,'USER_PICK',v_user_pick,s.id,p_mnv);
    exception when unique_violation then raise exception 'PP_USER_PICK_USED_TODAY:%',v_user_pick; end;
    begin insert into public.pp_resource_current(resource_type,resource_key,session_id,mnv) values ('USER_PICK',v_user_pick,s.id,p_mnv);
    exception when unique_violation then raise exception 'PP_RESOURCE_CONFLICT:USER_PICK:%',v_user_pick; end;
  end if;

  if v_pack_table is not null and v_pack_table is distinct from s.pack_table then
    begin insert into public.pp_resource_current(resource_type,resource_key,session_id,mnv) values ('PACK_TABLE',v_pack_table,s.id,p_mnv);
    exception when unique_violation then raise exception 'PP_RESOURCE_CONFLICT:PACK_TABLE:%',v_pack_table; end;
  end if;

  if v_user_pack is not null and v_user_pack is distinct from s.user_pack then
    begin insert into public.pp_day_user_consumption(business_date,resource_type,resource_key,first_session_id,first_mnv) values (p_business_date,'USER_PACK',v_user_pack,s.id,p_mnv);
    exception when unique_violation then raise exception 'PP_USER_PACK_USED_TODAY:%',v_user_pack; end;
    begin insert into public.pp_resource_current(resource_type,resource_key,session_id,mnv) values ('USER_PACK',v_user_pack,s.id,p_mnv);
    exception when unique_violation then raise exception 'PP_RESOURCE_CONFLICT:USER_PACK:%',v_user_pack; end;
  end if;

  delete from public.pp_resource_current r where r.session_id=s.id and not (
    (r.resource_type='PDA' and r.resource_key=coalesce(v_pda_serial,'')) or
    (r.resource_type='USER_PICK' and r.resource_key=coalesce(v_user_pick,'')) or
    (r.resource_type='PACK_TABLE' and r.resource_key=coalesce(v_pack_table,'')) or
    (r.resource_type='USER_PACK' and r.resource_key=coalesce(v_user_pack,''))
  );

  v_seq := nextval('public.pp_server_seq_seq');
  update public.pp_work_sessions
  set work_choice=v_work_choice,
      pda_serial=v_pda_serial,
      user_pick=v_user_pick,
      pack_table=v_pack_table,
      user_pack=v_user_pack,
      version=version+1,
      server_seq=v_seq,
      updated_at=now()
  where id=s.id
  returning * into s;

  insert into public.pp_events(event_id,event_type,business_date,mnv,session_id,actor_login,payload,server_seq)
  values (p_event_id,'RESOURCE_CHANGE',p_business_date,p_mnv,s.id,p_operator,jsonb_build_object('before',old_s,'after',to_jsonb(s)),v_seq);

  return jsonb_build_object('ok',true,'idempotent',false,'changed',true,'server_seq',v_seq,'session',to_jsonb(s));
end;
$function$;
