"""Transactional installation of VSD F16 Config Beta profiles, bindings and runtime."""
import copy, csv, datetime, hashlib, json, os, pathlib, re, shutil, sqlite3, subprocess, tempfile
import binding_review as bindings
import dcs_prerequisites as prerequisites
import share_installer as core

PLUGIN='org.f16vsd.cycling.sdPlugin'
SELECTOR='org.f16vsd.cycling.selector'
HOOK='\ndofile(lfs.writedir()..[[Scripts\\VSD-F16-States.lua]])\n'


def _existing_bms(payload,args):
    """Profiles-only must use the actual selected keyfile, never assume portable shortcuts."""
    checked=copy.copy(args)
    checked.bms_config=args.bms_config or getattr(args,'prerequisite_bms_root',None)
    paths=bindings.bms_paths(checked)
    if not paths:raise ValueError('Choose the BMS keyfile(s) used by these profiles.')
    requested={b['callback'] for b in bindings.bms_bindings(payload,getattr(args,'binding_overrides',None))}
    result=None
    for path in paths:
        found={}
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            parts=line.split()
            if len(parts)>8 and parts[0] in requested and re.fullmatch('0[xX][0-9A-Fa-f]+',parts[3]):
                scan=int(parts[3],16);mod=int(parts[4])
                if scan!=0xffffffff:
                    if scan not in bindings.SCAN_VK or mod & ~7:raise ValueError('Unsupported BMS binding: '+parts[0])
                    value=(scan,mod)
                    if parts[0] in found and found[parts[0]]!=value:raise ValueError('Ambiguous BMS callback: '+parts[0])
                    found[parts[0]]=value
        if set(found)!=requested:raise ValueError('Some BMS callbacks are not bound. Enable simulator bindings or select the correct keyfiles.')
        if result is not None and result!=found:raise ValueError('Selected BMS keyfiles have different shortcuts. Enable simulator bindings to synchronize them.')
        result=found
    output=[]
    for b in bindings.bms_bindings(payload):
        scan,mod=result[b['callback']];output.append(dict(b,scan_code=scan,modifier_mask=mod))
    return output


def plan(args):
    payload=pathlib.Path(core.HERE).resolve();sim=args.sim
    if sim not in ('bms','dcs','both'):raise ValueError('Select BMS, DCS, or both.')
    vsd=pathlib.Path(args.vsd_root).expanduser().resolve() if args.vsd_root else None
    dcs_root=getattr(args,'prerequisite_dcs_root',None) or args.dcs_saved_games
    dependency=None
    if sim in ('dcs','both') and (vsd or args.dcs_saved_games):
        dependency=prerequisites.require(getattr(args,'prerequisite_vsd_root',None) or vsd,dcs_root)
    overrides=getattr(args,'binding_overrides',None) or {}
    rows=bindings.proposals(payload,overrides)
    edited=[r for r in rows if r['id'] in overrides and (sim=='both' or r['sim'].lower()==sim)]
    if edited and (not vsd or any((r['sim']=='BMS' and not args.bms_config) or (r['sim']=='DCS' and not args.dcs_saved_games) for r in edited)):
        raise ValueError('Edited shortcuts require profiles and corresponding simulator bindings so both sides stay synchronized.')
    review=bindings.require(payload,args)
    records=json.loads((payload/'profiles.json').read_text())
    chosen=[p for p in records if (sim=='both' or p['sim'].lower()==sim) and (not getattr(args,'devices',None) or p['device'] in args.devices)]
    if vsd and not chosen:raise ValueError('Select at least one panel.')
    files={};directories={};db_records=[];serials={};bms_map=None
    if args.bms_config and sim in ('bms','both'):
        bms_map=bindings.bms_bindings(payload,overrides)
        for path in bindings.bms_paths(args):
            files[path]=core.patch_bms(path.read_text(encoding='utf-8-sig'),bms_map).encode('utf-8')
    if args.dcs_saved_games and sim in ('dcs','both'):
        dcs=pathlib.Path(args.dcs_saved_games).expanduser().resolve()
        key=dcs/'Config/Input/F-16C_50/keyboard/Keyboard.diff.lua'
        existing=key.read_text(encoding='utf-8-sig') if key.exists() else ''
        existing=bindings.remove_replaced_dcs_chords(existing,payload,overrides)
        files[key]=core.merge_dcs(existing,bindings.dcs_additions(payload,overrides)).encode('utf-8')
        export=dcs/'Scripts/DCS-ExportScript/ExportsModules/F-16C_50.lua'
        text=export.read_text(encoding='utf-8-sig')
        if '-- BEGIN VSD F16 SHARED ARGUMENTS' not in text:text+='\n'+(payload/'bindings/DCS-feedback-arguments.lua').read_text()
        files[export]=text.encode('utf-8')
    if vsd:
        config=vsd/'config/StreamDockConfig.ini'
        text=config.read_text(encoding='utf-8-sig') if config.exists() else ''
        for device in ('VSDXL','VSDN4Pro'):
            m=re.search(r'(?m)^'+device+r'\\SerialNumber=([^\r\n]+)',text)
            if m:serials[device]=m[1].strip()
        db=vsd/'config/DataCache.db'
        if not db.is_file():raise ValueError('Start VSD Craft and connect your panels once, then close it before installing.')
        connection=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)
        try:
            tables={r[0] for r in connection.execute("select name from sqlite_master where type='table'")}
            if connection.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('VSD profile database integrity check failed.')
        finally:connection.close()
        paired=bool(getattr(args,'paired',True) and sim=='both')
        if paired and {p['device'] for p in chosen}!={'VSDXL','VSDN4Pro'}:raise ValueError('Linked toggles require both panels. Turn linking off for a single-panel setup.')
        if sim in ('bms','both') and bms_map is None:
            bms_map=_existing_bms(payload,args)
            # Rewrite native encoder/momentary hotkeys to the same actual BMS map.
            current={b['callback']:b for b in bms_map}
            for row in rows:
                if row['sim']=='BMS':
                    b=current[row['command']];row['key']=bindings.VK_NAME[bindings.SCAN_VK[b['scan_code']]]
                    row['mods']=[m for bit,m in [(1,'LShift'),(2,'LCtrl'),(4,'LAlt')] if b['modifier_mask']&bit]
        if not args.dcs_saved_games and sim in ('dcs','both'):
            missing=[r['name'] for r in review['rows'] if r['sim']=='DCS' and r['status']!='Already assigned']
            if missing:raise ValueError('DCS encoder shortcuts are not installed. Enable simulator bindings or install the reviewed shortcuts first.')
        for p in chosen:
            if not re.fullmatch(r'[A-F0-9-]+\.sdProfile',p['folder']) or p['device'] not in ('VSDXL','VSDN4Pro'):raise ValueError('Invalid packaged profile identity.')
            if p['device'] not in serials or p['device'] not in tables:raise ValueError('Connect '+p['device']+' to VSD Craft once and choose its VSD data folder.')
            target=vsd/'profiles'/p['folder'];source=payload/'profiles'/p['folder']
            if target.exists() and not getattr(args,'replace_existing',False):raise ValueError('Matching F-16 profile already exists. Enable updating existing profiles.')
            contents={}
            for path in source.rglob('*'):
                if not path.is_file():continue
                rel=path.relative_to(source)
                if path.name!='manifest.json':contents[rel]=path.read_bytes();continue
                data=json.loads(path.read_text());data['DeviceSerialNumber']=serials[p['device']]
                bindings.rewrite_profile(data,p['sim'],rows)
                for a in data['Actions'].values():
                    if a['UUID']!='com.hotspot.streamdock.multiactions.routine':continue
                    if sim!='both':
                        a['Actions']=[];a['Name']='Simulator display'
                        for state in a['States']:state.update(Title=p['sim']+' ONLY',ShowTitle=True)
                    elif not paired:
                        a['Actions']=[s for s in a.get('Actions',[]) if s['Settings'].get('deviceUUID')==p['device']]
                    for step in a.get('Actions',[]):
                        device=step['Settings']['deviceUUID']
                        if device not in serials:raise ValueError('No saved VSD identity for linked panel '+device)
                        step['Settings']['serialNumber']=serials[device]
                contents[rel]=json.dumps(data,indent=2).encode('utf-8')
            directories[target]=contents;db_records.append((p['device'],p['folder']))
        runtime=payload/PLUGIN
        manifest=json.loads((runtime/'manifest.json').read_text())
        binary=manifest.get('CodePathWin');binary_path=(runtime/str(binary)).resolve()
        if not binary or not binary_path.is_relative_to(runtime) or not binary_path.is_file():raise ValueError('The bundled F-16 control runtime is missing. Download the complete installer.')
        contents={p.relative_to(runtime):p.read_bytes() for p in runtime.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.suffix!='.log'}
        catalog=json.loads(contents[pathlib.Path('controls.json')]);existing_catalog=vsd/'plugins'/PLUGIN/'controls.json'
        if sim=='dcs' and existing_catalog.exists():
            old=json.loads(existing_catalog.read_text())
            for id,c in catalog.items():
                if id in old:c['bindings']=old[id]['bindings']
        if bms_map:
            by_callback={b['callback']:b for b in bms_map}
            for c in catalog.values():c['bindings']=[by_callback[cb] for cb in c['callbacks']]
        contents[pathlib.Path('controls.json')]=json.dumps(catalog,indent=2).encode('utf-8')
        settings={'command_port':26027}
        existing_settings=vsd/'plugins'/PLUGIN/'runtime-settings.json'
        if existing_settings.exists():settings.update(json.loads(existing_settings.read_text()))
        if dependency:settings['command_port']=dependency['command_port']
        contents[pathlib.Path('runtime-settings.json')]=json.dumps(settings,indent=2).encode('utf-8')
        directories[vsd/'plugins'/PLUGIN]=contents
        if sim in ('dcs','both'):
            dcs=pathlib.Path(dcs_root).expanduser().resolve()
            export=dcs/'Scripts/Export.lua';text=export.read_text(encoding='utf-8-sig')
            if 'VSD-F16-States.lua' not in prerequisites.uncomment(text):text+=HOOK
            files[export]=text.encode('utf-8')
            files[dcs/'Scripts/VSD-F16-States.lua']=(payload/'bindings/VSD-F16-States.lua').read_bytes()
    if not files and not directories:raise ValueError('Select profiles, simulator bindings, or both.')
    # A shortcuts-only update must not leave existing cycling controls on different BMS keys.
    if not vsd and bms_map:
        root=getattr(args,'prerequisite_vsd_root',None)
        catalog_path=pathlib.Path(root)/'plugins'/PLUGIN/'controls.json' if root else None
        if catalog_path and catalog_path.exists():
            catalog=json.loads(catalog_path.read_text());new={b['callback']:b for b in bms_map}
            if any((b['scan_code'],b['modifier_mask'])!=(new[b['callback']]['scan_code'],new[b['callback']]['modifier_mask']) for c in catalog.values() for b in c['bindings']):
                raise ValueError('Enable profiles too so installed cycling controls receive the same changed BMS shortcuts.')
    return {'payload':payload,'vsd':vsd,'chosen':chosen if vsd else [],'files':files,'directories':directories,'db_records':db_records,'review':review}


def install(args):
    prepared=plan(args);files=prepared['files'];directories=prepared['directories'];vsd=prepared['vsd']
    print('VSD F16 Config Beta — latest single-button cycling design')
    print('Profiles:',len(prepared['chosen']),' Runtime:',int(bool(directories)),' Binding/export files:',len(files))
    for path in directories:print('UPDATE' if path.exists() else 'ADD',path)
    for path in files:print('MERGE',path)
    if not args.apply:print('REVIEW ONLY: no files changed. Close VSD Craft and the selected simulators before Apply.');return
    running=subprocess.run(['tasklist','/FO','CSV','/NH'],capture_output=True,text=True,check=True,creationflags=0x08000000)
    names={r[0].lower() for r in csv.reader(running.stdout.splitlines()) if r}
    must_close=set()
    if directories:must_close.update(['vsd craft.exe','f16 cycling.exe','vsd f16 controls.exe'])
    if args.sim in ('bms','both') and args.bms_config:must_close.add('falcon bms.exe')
    if args.sim in ('dcs','both') and (args.dcs_saved_games or directories):must_close.add('dcs.exe')
    if names & must_close:raise ValueError('Close these programs before applying: '+', '.join(sorted(names & must_close)))
    persistent=bool(getattr(args,'create_backup',True))
    backup_parent=pathlib.Path(getattr(args,'backup_dir',None) or pathlib.Path.home()/'Documents/VSD F16 Config Beta/Backups').expanduser().resolve()
    backup_parent.mkdir(parents=True,exist_ok=True)
    backup=backup_parent/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');backup.mkdir()
    journal=[];db=vsd/'config/DataCache.db' if vsd else None
    for i,(path,data) in enumerate(files.items()):
        row={'file':str(path),'created':not path.exists()}
        if path.exists():saved=backup/'files'/(str(i)+'-'+path.name);saved.parent.mkdir(exist_ok=True);shutil.copy2(path,saved);row['backup']=str(saved)
        journal.append(row)
    for i,path in enumerate(directories):
        row={'directory':str(path),'created':not path.exists()}
        if path.exists():saved=backup/'directories'/str(i);shutil.copytree(path,saved);row['backup']=str(saved)
        journal.append(row)
    if db:
        saved=backup/'DataCache.db'
        # VSD is closed, so preserve exact database bytes for a complete rollback.
        # Do not replace the original until its transaction is actually reached.
        shutil.copy2(db,saved);journal.append({'file':str(db),'backup':str(saved)})
    (backup/'restore-manifest.json').write_text(json.dumps(journal,indent=2))
    (backup/'binding-review.json').write_text(json.dumps(prepared['review'],indent=2))
    try:
        for path,data in files.items():
            path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.vsdf16.tmp');temp.write_bytes(data);os.replace(temp,path)
        for path,contents in directories.items():
            if path.exists():shutil.rmtree(path)
            path.mkdir(parents=True)
            for rel,data in contents.items():
                target=path/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        if db:
            c=sqlite3.connect(db)
            try:
                with c:
                    for table,folder in prepared['db_records']:
                        if not c.execute('select 1 from '+table+' where Profile=?',(folder,)).fetchone():c.execute('insert into '+table+'(Profile) values(?)',(folder,))
                if c.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('VSD database verification failed')
            finally:c.close()
        for path,data in files.items():
            if path.read_bytes()!=data:raise OSError('File verification failed: '+str(path))
        for path,contents in directories.items():
            for rel,data in contents.items():
                if (path/rel).read_bytes()!=data:raise OSError('Profile/runtime verification failed: '+str(path/rel))
    except Exception:
        errors=[]
        for row in reversed(journal):
            try:
                path=pathlib.Path(row.get('directory') or row['file'])
                if 'directory' in row:
                    if path.exists():shutil.rmtree(path)
                    if row.get('backup'):shutil.copytree(row['backup'],path)
                elif row.get('backup'):shutil.copy2(row['backup'],path)
                elif path.exists():path.unlink()
            except Exception as error:errors.append(str(error))
        if errors:print('Rollback needs attention. Keep backups:',backup,'\n'+'\n'.join(errors))
        else:print('Installation stopped; previous files restored. Backups:',backup)
        raise
    report={'product':'VSD F16 Config Beta','profiles':len(prepared['chosen']),'runtime_installed':bool(directories),'state':'installed; physical and cockpit testing pending'}
    (backup/'installation-report.json').write_text(json.dumps(report,indent=2))
    print('Installed. Open VSD Craft and select the matching F-16 profiles.')
    if persistent:print('Rollback backups:',backup);return str(backup)
    shutil.rmtree(backup);print('Persistent backup skipped by choice.');return None
