"""Portable binding proposals, non-executing default scan and synchronized profile edits."""
import ast,copy,csv,json,os,pathlib,re,sys,importlib
from dcs_prerequisites import uncomment

SCAN_VK={**dict(zip(range(0x10,0x1a),map(ord,'QWERTYUIOP'))),**dict(zip(range(0x1e,0x27),map(ord,'ASDFGHJKL'))),**dict(zip(range(0x2c,0x33),map(ord,'ZXCVBNM'))),**dict(zip(range(2,12),map(ord,'1234567890'))),**{s:0x70+s-0x3b for s in range(0x3b,0x45)},0x57:122,0x58:123,0x4e:107,0x4a:109,0x0c:189,0x0d:187,0x1a:219,0x1b:221,0x27:186,0x28:222,0x29:192,0x33:188,0x34:190,0x35:191,0x39:32,0x0f:9,0x1c:13,0x01:27,0x0e:8}
VK_NAME={**{v:chr(v) for v in range(48,91)},**{v:'F'+str(v-111) for v in range(112,124)},189:'-',187:'=',219:'[',221:']',186:';',222:"'",192:'`',188:',',190:'.',191:'/',32:'Space',9:'Tab',107:'Num+',109:'Num-',13:'Enter',27:'Escape',8:'Back'}
NAME_SCAN={VK_NAME[v]:s for s,v in SCAN_VK.items()}
MODS=['LShift','LCtrl','LAlt','RShift','RCtrl','RAlt','LWin','RWin']
QUOTED=r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|\[\[.*?\]\]"
def field(name):return r'(?:\b'+name+r'|\[\s*[\"\']'+name+r'[\"\']\s*\])\s*=\s*'
def lua_engine():
    for name in ['share_installer','install','__main__']:
        m=sys.modules.get(name)
        if m and hasattr(m,'lua_load'):return m
    return importlib.import_module('share_installer' if (pathlib.Path(__file__).parent/'share_installer.py').exists() else 'install')

def chord(key,mods=()):return (str(key).upper(),tuple(sorted(mods or ())))
def combo(c):return chord(c['key'],c.get('reformers',{}).values() if isinstance(c.get('reformers'),dict) else c.get('reformers',[]))
def hotkey_chord(h):
    key=VK_NAME.get(h.get('VKeyCode'))
    return chord(key,[m for field,m in [('KeyShift','LShift'),('KeyCtrl','LCtrl'),('KeyOption','LAlt'),('RKeyShift','RShift'),('RKeyCtrl','RCtrl'),('RKeyOption','RAlt'),('KeyCmd','LWin'),('RKeyCmd','RWin')] if h.get(field)]) if key else None
def label(key,mods):return '+'.join([*mods,key])
def validate_edit(row,key,mods):
    if key not in NAME_SCAN:raise ValueError('Choose one of the supported keys.')
    if set(mods)-set(MODS):raise ValueError('Unsupported modifier.')
    if row['sim']=='BMS' and set(mods)-{'LShift','LCtrl','LAlt'}:raise ValueError('BMS profiles support left Shift/Ctrl/Alt modifiers.')

def proposals(payload,overrides=None):
    engine=lua_engine()
    payload=pathlib.Path(payload);rows=[]
    for b in json.loads((payload/'bindings/BMS-keyboard-bindings.json').read_text()):
        key=VK_NAME[SCAN_VK[b['scan_code']]];mods=[m for bit,m in [(1,'LShift'),(2,'LCtrl'),(4,'LAlt')] if b['modifier_mask']&bit]
        rows.append({'id':'BMS:'+b['callback'],'sim':'BMS','command':b['callback'],'name':b['description'],'key':key,'mods':mods,'original':chord(key,mods)})
    data=engine.lua_load((payload/'bindings/DCS-Keyboard.diff.lua').read_text())
    for command,entry in data['keyDiffs'].items():
        for index,c in entry['added'].items():
            mods=list(c.get('reformers',{}).values())
            rows.append({'id':'DCS:'+command+':'+str(index),'sim':'DCS','command':command,'slot':index,'name':entry['name'],'key':c['key'],'mods':mods,'original':combo(c)})
    for row in rows:
        if row['id'] in (overrides or {}):
            edit=overrides[row['id']];validate_edit(row,edit['key'],edit['mods']);row.update(key=edit['key'],mods=list(edit['mods']))
    return rows

def bms_bindings(payload,overrides=None):
    rows={r['command']:r for r in proposals(payload,overrides) if r['sim']=='BMS'}
    data=json.loads((pathlib.Path(payload)/'bindings/BMS-keyboard-bindings.json').read_text())
    for b in data:
        r=rows[b['callback']];b.update(scan_code=NAME_SCAN[r['key']],modifier_mask=sum(bit for bit,m in [(1,'LShift'),(2,'LCtrl'),(4,'LAlt')] if m in r['mods']))
    return data

def dcs_additions(payload,overrides=None):
    engine=lua_engine()
    data=engine.lua_load((pathlib.Path(payload)/'bindings/DCS-Keyboard.diff.lua').read_text())
    for row in proposals(payload,overrides):
        if row['sim']=='DCS':
            c={'key':row['key']}
            if row['mods']:c['reformers']={i+1:v for i,v in enumerate(row['mods'])}
            data['keyDiffs'][row['command']]['added'][row['slot']]=c
    return engine.lua_dump(data)

def remove_replaced_dcs_chords(existing,payload,overrides=None):
    if not existing or not overrides:return existing
    engine=lua_engine()
    data=engine.lua_load(existing)
    for r in proposals(payload,overrides):
        if r['sim']!='DCS' or r['original']==chord(r['key'],r['mods']):continue
        entry=data.get('keyDiffs',{}).get(r['command'],{})
        if 'added' in entry:entry['added']={i:c for i,c in entry['added'].items() if combo(c)!=r['original']}
    return engine.lua_dump(data)

def rewrite_profile(data,sim,rows):
    mapping={r['original']:r for r in rows if r['sim']==sim}
    for action in data.get('Actions',{}).values():
        for h in action.get('Settings',{}).get('Hotkeys',[]):
            old=hotkey_chord(h)
            if old not in mapping:continue
            r=mapping[old];h['VKeyCode']=SCAN_VK[NAME_SCAN[r['key']]]
            for field,m in [('KeyShift','LShift'),('KeyCtrl','LCtrl'),('KeyOption','LAlt'),('RKeyShift','RShift'),('RKeyCtrl','RCtrl'),('RKeyOption','RAlt'),('KeyCmd','LWin'),('RKeyCmd','RWin')]:h[field]=m in r['mods']
    return data

def dcs_install_default():
    candidates=[]
    if os.name=='nt':
        import winreg
        for hive in [winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE]:
            for name in ['DCS World','DCS World OpenBeta']:
                try:
                    with winreg.OpenKey(hive,'Software/Eagle Dynamics/'+name) as k:candidates.append(pathlib.Path(winreg.QueryValueEx(k,'Path')[0]))
                except OSError:pass
    for drive in ['C','D','E','F','G']:
        for tail in ['Program Files/Eagle Dynamics/DCS World','DCS World','Games/DCS World','Program Files (x86)/Steam/steamapps/common/DCSWorld']:candidates.append(pathlib.Path(drive+':/')/tail)
    return next((str(p) for p in candidates if (p/'Mods/aircraft/F-16C/Input').is_dir()),'')

def bms_paths(args):
    root=pathlib.Path(args.bms_config) if args.bms_config else None
    if root is None:return []
    names=getattr(args,'bms_keyfiles',None)
    paths=[pathlib.Path(p) for p in names] if names else [root/n for n in ['BMS - Full.key','BMS - Auto.key']]
    if not paths:raise ValueError('Select at least one BMS keyfile.')
    return list(dict.fromkeys(p.resolve() for p in paths))

def table_spans(text):
    # Map braces outside strings. Used for literal command rows without running Lua.
    token=re.compile(QUOTED+r'|[{}]',re.S);stack=[];spans={}
    for m in token.finditer(text):
        if m[0]=='{':stack.append(m.start())
        elif m[0]=='}':
            if not stack:raise ValueError('Unbalanced Lua table')
            start=stack.pop();spans[start]=m.end()
    if stack:raise ValueError('Unbalanced Lua table')
    return spans

def containing(spans,pos):return max((s for s,e in spans.items() if s<pos<e),default=None)
def quoted_value(token):
    if token.startswith('[['):return token[2:-2]
    return ast.literal_eval(token)

def scan_defaults(install):
    """Read F-16, common and UI keyboard definitions plus literal dependencies."""
    root=pathlib.Path(install).resolve();keyboard=root/'Mods/aircraft/F-16C/Input/F-16C/keyboard/default.lua'
    if not keyboard.is_file():raise ValueError('Select the DCS program folder containing Mods/aircraft/F-16C/Input/F-16C/keyboard/default.lua.')
    cockpit=root/'Mods/aircraft/F-16C/Cockpit/Scripts';assignment=root/'Scripts/Input/DefaultAssignments.lua'
    assign={};issues=[];records=[];files=[]
    if not assignment.is_file():raise ValueError('DCS default keyboard assignments file is missing: '+str(assignment))
    at=uncomment(assignment.read_text(encoding='utf-8-sig'));sp=table_spans(at)
    start=re.search(r'default_assignments\s*\[\s*[\"\']Keyboard[\"\']\s*\]\s*=\s*\{',at)
    if not start:raise ValueError('Cannot read the DCS default Keyboard assignment table.')
    pos=at.index('{',start.start());body=at[pos:sp[pos]]
    for m in re.finditer(r'(\w+)\s*=\s*(\{)',body):
        try:assign[m[1]]=lua_engine().lua_load(body[m.start(2):table_spans(body)[m.start(2)]])
        except (ValueError,AssertionError,IndexError):pass
    files.append(str(assignment));pending=[keyboard,root/'Config/Input/UiLayer/keyboard/default.lua'];seen=set()
    while pending:
        path=pending.pop().resolve()
        if path in seen:continue
        seen.add(path)
        if not path.is_relative_to(root) or not path.is_file():raise ValueError('DCS keyboard dependency missing or outside its program folder: '+str(path))
        text=uncomment(path.read_text(encoding='utf-8-sig'));files.append(str(path));spans=table_spans(text)
        for match in re.finditer(r'\b(?:external_profile|dofile)\s*\(\s*(?:(cockpit)\s*\.\.\s*)?([\"\'])(.*?\.lua)\2',text):
            target=(cockpit/match[3] if match[1] else root/match[3]).resolve()
            # devices/command definitions do not carry bindings, and can load simulator APIs.
            if target.name not in ['devices.lua','command_defs.lua']:pending.append(target)
        for m in re.finditer(field('combos'),text):
            owner=containing(spans,m.start());end=spans.get(owner,len(text));row=text[owner:end] if owner is not None else text[m.start():end]
            nm=re.search(field('name')+r'(?:_\s*\(\s*)?('+QUOTED+')',row,re.S);name=quoted_value(nm[1]) if nm else 'Generated keyboard command'
            tail=text[m.end():];combos=[]
            if tail.startswith('{'):
                block=text[m.end():spans[m.end()]]
                keys=list(re.finditer(field('key'),block))
                for km in keys:
                    bs=table_spans(block);ks=containing(bs,km.start());kt=block[km.end():]
                    literal=re.match(QUOTED,kt,re.S)
                    if literal:
                        cc=lua_engine().lua_load(block[ks:bs[ks]]);combos.append(cc)
                    else:
                        # Common add-on generator: for _,entry in ipairs(keys), key=entry[1].
                        dynamic=re.match(r'(\w+)\[1\]',kt)
                        loop=re.search(r'for\s+[^\n]*\b'+re.escape(dynamic[1] if dynamic else '__none__')+r'\s+in\s+ipairs\((\w+)\)',text)
                        source=re.search(r'local\s+'+re.escape(loop[1])+r'\s*=\s*\{' ,text) if loop else None
                        if source:
                            ss=text.index('{',source.start());sb=text[ss:spans[ss]]
                            mods=re.search(r'reformers\s*=\s*(\{[^}]*\})',block)
                            modvals=lua_engine().lua_load(mods[1]) if mods else {}
                            spans_sb=table_spans(sb)
                            for kmatch in re.finditer(r'\{\s*('+QUOTED+r')\s*,',sb):
                                part=sb[kmatch.start():spans_sb[kmatch.start()]]
                                literals=[quoted_value(q[0]) for q in re.finditer(QUOTED,part,re.S)]
                                combos.append({'key':quoted_value(kmatch[1]),'reformers':modvals,'_name':literals[-1] if len(literals)>1 else name})
                        else:issues.append(str(path)+': cannot resolve a generated keyboard shortcut.')
            elif tail.startswith('defaultDeviceAssignmentFor'):
                am=re.match(r'defaultDeviceAssignmentFor\(\s*[\"\'](.*?)[\"\']\s*\)',tail)
                if am and am[1] in assign:combos=[assign[am[1]]]
                else:issues.append(str(path)+': cannot resolve defaultDeviceAssignmentFor.')
            else:issues.append(str(path)+': unsupported keyboard assignment expression.')
            for c in combos:
                if not isinstance(c.get('key'),str):issues.append(str(path)+': unresolved key.');continue
                records.append({'chord':combo(c),'name':c.get('_name',name),'source':str(path),'command':None,'layer':'ui' if 'UiLayer' in path.parts else 'aircraft'})
    return records,files,list(dict.fromkeys(issues))

def audit(payload,args):
    engine=lua_engine()
    rows=[dict(r,owners=[],status='Free') for r in proposals(payload,getattr(args,'binding_overrides',None)) if args.sim=='both' or r['sim'].lower()==args.sim]
    files=[];errors=[];occupants={'BMS':[],'DCS':[]};moving={r['sim']:{x['command'] for x in rows if x['sim']==r['sim']} for r in rows}
    bms_root=args.bms_config or getattr(args,'prerequisite_bms_root',None)
    if bms_root and args.sim in ['both','bms']:
        checked=copy.copy(args);checked.bms_config=bms_root
        for p in bms_paths(checked):
            if not p.is_file():errors.append('BMS keyfile not found: '+str(p));continue
            files.append(str(p));present=set()
            for line in p.read_text(encoding='utf-8-sig').splitlines():
                a=line.split()
                if len(a)>8 and re.fullmatch(r'0[xX][0-9A-Fa-f]+',a[3]):
                    present.add(a[0]);scan=int(a[3],16);mod=int(a[4])
                    if scan in SCAN_VK:
                        occupants['BMS'].append({'chord':chord(VK_NAME[SCAN_VK[scan]],[m for bit,m in [(1,'LShift'),(2,'LCtrl'),(4,'LAlt')] if mod&bit]),'name':a[0],'command':a[0],'source':str(p),'moving':a[0] in moving['BMS']})
            absent=moving['BMS']-present
            if absent:errors.append(p.name+': missing panel callbacks: '+', '.join(sorted(absent)))
    if args.sim in ['both','dcs'] and (args.dcs_saved_games or args.vsd_root):
        install=getattr(args,'dcs_install',None) or dcs_install_default()
        try:
            defaults,scanned,issues=scan_defaults(install);files+=scanned;errors+=issues
        except (ValueError,OSError,IndexError,AssertionError) as e:defaults=[];errors.append(str(e))
        saved=pathlib.Path(getattr(args,'prerequisite_dcs_root',None) or args.dcs_saved_games or pathlib.Path.home()/'Saved Games/DCS')
        for layer,folder in [('aircraft','F-16C_50'),('ui','UiLayer')]:
            for p in sorted((saved/'Config/Input'/folder/'keyboard').glob('*.diff.lua')):
                try:data=engine.lua_load(p.read_text(encoding='utf-8-sig'))
                except Exception as e:errors.append('Cannot read '+str(p)+': '+str(e));continue
                files.append(str(p))
                for command,entry in data.get('keyDiffs',{}).items():
                    for c in entry.get('removed',{}).values():
                        # A name match is required when command constants are expressions.
                        defaults=[d for d in defaults if not(d['layer']==layer and d['name']==entry.get('name') and d['chord']==combo(c))]
                    for c in entry.get('added',{}).values():
                        replaced=layer=='aircraft' and any(r['sim']=='DCS' and r['command']==command and r['original']==combo(c) and r['original']!=chord(r['key'],r['mods']) for r in rows)
                        if replaced:continue
                        occupants['DCS'].append({'chord':combo(c),'name':entry.get('name',command),'command':command,'source':str(p),'moving':False,'layer':layer})
        occupants['DCS']+=defaults
    for row in rows:
        c=chord(row['key'],row['mods'])
        same=[r for r in rows if r['sim']==row['sim'] and r['id']!=row['id'] and chord(r['key'],r['mods'])==c and r['command']!=row['command']]
        for other in same:row['owners'].append('Proposed: '+other['name'])
        for owner in occupants[row['sim']]:
            if owner['chord']!=c:continue
            if owner.get('command')==row['command'] and owner.get('layer','aircraft')=='aircraft':
                if not row['owners']:row['status']='Already assigned'
                continue
            if owner.get('moving') and args.bms_config:continue
            row['owners'].append(owner['name']+' ['+owner['source']+']')
        if row['owners']:row['status']='Conflict'
        if row['sim']=='BMS' and not bms_root:row['status']='Not checked'
    return {'rows':rows,'files':list(dict.fromkeys(files)),'errors':errors,'ready':not errors and not any(r['status'] in ['Conflict','Not checked'] for r in rows)}

def require(payload,args):
    report=audit(payload,args)
    problems=report['errors']+[r['name']+' ('+label(r['key'],r['mods'])+'): '+ '; '.join(r['owners']) for r in report['rows'] if r['owners']]
    if any(r['status']=='Not checked' for r in report['rows']):problems.append('Choose BMS keyfiles to check before installing BMS profiles.')
    if problems:raise ValueError('Resolve binding conflicts or incomplete checks before applying:\n'+'\n'.join(problems))
    print('Binding review: '+str(len(report['rows']))+' shortcuts; '+str(len(report['files']))+' files checked.')
    for f in report['files']:print('CHECKED',f)
    return report
