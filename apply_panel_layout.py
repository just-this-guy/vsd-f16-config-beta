"""Build explicit cockpit-like row/column layouts without changing control commands."""
import copy,csv,io,json,pathlib,shutil,uuid
from graphics import tile

WORK=pathlib.Path(__file__).resolve().parent;PAYLOAD=WORK/'payload'
LABELS={'main':'MAIN PWR','jfs1':'JFS START 1','jfs2':'JFS START 2','eng':'ENG CONT','fuel':'FUEL MASTER','epu':'EPU','feed':'ENG FEED','refuel':'AIR REFUEL','transfer':'EXT TRANS','elecreset':'ELEC RESET','lamptest':'LAMP TEST','firetest':'FIRE TEST','eputest':'EPU TEST','obogs':'OBOGS TEST','mmc':'MMC','sms':'ST STA','mfd':'MFD','ufc':'UFC','gps':'GPS','dl':'DATALINK','map':'MAP','lhdpt':'L HDPT','rhdpt':'R HDPT','fcr':'FCR','ins':'INS','mids':'MIDS','ralt':'RDR ALT','ice':'ANTI ICE','air':'AIR SOURCE','oxygen':'OXY SUPPLY','scales':'HUD SCALES','fpm':'HUD FPM','ded':'HUD DATA','reticle':'DEPR RET','speed':'HUD SPEED','alt':'HUD ALT','hudbrt':'HUD BRT','digital':'DIG BACKUP','altflaps':'ALT FLAPS','lef':'LE FLAPS','trim':'TRIM / AP','flash':'POSITION','wing':'WING / TAIL','fuselage':'FUSELAGE','lightmaster':'LIGHT MASTER','anticoll':'ANTI COLL','ecmpwr':'ECM OPR','ecmbit':'ECM BIT','ecmxmit':'ECM XMIT',**{f'ecm{i}':f'ECM {i}' for i in range(1,6)}}
KNOB_LABELS={'comm1':'COMM 1','comm2':'COMM 2','msl':'MSL TONE','threat':'THREAT','hud':'HUD SYM','hmcs':'HMCS BRT','inst':'INST PNL','flood':'FLOOD CNS','dedbrt':'DED BRT','formation':'FORM LIGHT','aar':'AAR LIGHT'}
OLD_KNOBS=[['comm1','comm2','msl','threat'],['hud','hmcs','inst','flood'],['hud','hmcs','inst','flood'],['inst','dedbrt','flood','hud'],['formation','aar','inst','flood'],['comm1','comm2','inst','flood'],['hud','hmcs','inst','flood']]

def sdk(coord,device):
    x,y=coord;return f'{x},{y if device=="VSDXL" else 2-y}'

def ident(seed):return str(uuid.uuid5(uuid.NAMESPACE_URL,'vsd-f16-real-panels-v031/'+seed)).upper()

def apply():
    layout=json.loads((WORK/'panel-layout.json').read_text());profiles=json.loads((PAYLOAD/'profiles.json').read_text());rows=list(csv.DictReader(io.StringIO((PAYLOAD/'controls.csv').read_text(encoding='utf-8-sig'))))
    prior_layout=json.loads((PAYLOAD/'panel-layout.json').read_text()) if (PAYLOAD/'panel-layout.json').exists() else None
    # Templates retain all original UUIDs, settings, state graphics and simulator commands.
    keys={};knobs={};utilities={};source_rows={};bases={};page_ids={}
    by_label={v:k for k,v in LABELS.items()}
    for p in profiles:
        root=PAYLOAD/'profiles'/p['folder'];base=json.loads((root/'manifest.json').read_text());bases[p['folder']]=base;page_ids[p['folder']]=base['Pages']['Pages']
        names=p.get('page_titles') or list(dict.fromkeys(r['page'] for r in rows if (r['sim'],r['device'])==(p['sim'],p['device'])))
        for i,page in enumerate(base['Pages']['Pages']):
            folder=root if i==0 else root/'profiles'/page;m=json.loads((folder/'manifest.json').read_text())
            for coord,a in m['Actions'].items():
                assets={state['Image']:(folder/'Images'/state['Image']).read_bytes() for state in a['States']}
                control=a.get('Settings',{}).get('control')
                row=next((r for r in rows if (r['sim'],r['device'],r['page'],r['coordinate'],r['trigger'])==(p['sim'],p['device'],names[i],coord,'key')),None) if i<len(names) else None
                if control or row:
                    role=control or by_label[row['control']]
                    keys.setdefault((p['sim'],role),(copy.deepcopy(a),assets))
                    if row:source_rows.setdefault((p['sim'],role),row)
                if a.get('Controller')=='Knob' and p['device']=='VSDN4Pro':
                    column=coord.split(',')[0]
                    role=prior_layout[p['device']][i]['knobs'][column] if prior_layout else OLD_KNOBS[i][int(column)]
                    knobs.setdefault((p['sim'],role),(copy.deepcopy(a),assets))
                if a['UUID'].startswith('com.hotspot.streamdock.page.') or a['UUID']=='com.hotspot.streamdock.multiactions.routine':utilities.setdefault((p['sim'],p['device'],a['UUID']),(copy.deepcopy(a),assets))
    new_rows=[]
    for p in profiles:
        root=PAYLOAD/'profiles'/p['folder'];base=bases[p['folder']];specs=layout[p['device']]
        old_ids=page_ids[p['folder']];pages=old_ids[:len(specs)]+[ident(p['sim']+'/'+p['device']+'/'+str(i))+'.sdProfile' for i in range(len(old_ids),len(specs))]
        # This function is run against the clean versioned payload, never against installed user profiles.
        assert root.resolve().is_relative_to((PAYLOAD/'profiles').resolve())
        shutil.rmtree(root);root.mkdir()
        for i,spec in enumerate(specs):
            folder=root if i==0 else root/'profiles'/pages[i];(folder/'Images').mkdir(parents=True)
            data=copy.deepcopy(base);data.update(Name=p['name'] if i==0 else spec['title'],Actions={},Pages={'Current':pages[0],'Pages':pages},DeviceSerialNumber='')
            actions=data['Actions'];used=set()
            def insert(role,coord,template,assets):
                position=sdk(coord,p['device']);assert position not in used,(spec['title'],position);used.add(position)
                a=copy.deepcopy(template);a['ActionID']=ident(p['sim']+'/'+p['device']+'/'+str(i)+'/'+role)
                for name,content in assets.items():(folder/'Images'/name).write_bytes(content)
                actions[position]=a;return a
            for role,coord in spec['keys'].items():
                a,assets=keys[p['sim'],role];insert(role,coord,a,assets)
                row=dict(source_rows[p['sim'],role]);row.update(device=p['device'],page=spec['title'],coordinate=sdk(coord,p['device']),trigger='key');new_rows.append(row)
            for column,role in spec.get('knobs',{}).items():
                a,_=copy.deepcopy(knobs[p['sim'],role]);a['Settings']['Hotkeys'][2]=dict(a['Settings']['Hotkeys'][2],VKeyCode=-1)
                for field in ['KeyCmd','KeyCtrl','KeyOption','KeyShift','RKeyCmd','RKeyCtrl','RKeyOption','RKeyShift']:a['Settings']['Hotkeys'][2][field]=False
                name='knob-'+role+'.png';tile(KNOB_LABELS[role],'ROTATE','rotary',active=True).save(folder/'Images'/name);a['States']=[{'Image':name,'Title':'','ShowTitle':False}]
                position=f'{column},0';assert position not in used;used.add(position);a['ActionID']=ident(p['sim']+'/'+p['device']+'/'+str(i)+'/knob/'+role);actions[position]=a
            for direction in ['previous','next']:
                uuid_='com.hotspot.streamdock.page.'+direction;a,_=utilities[p['sim'],p['device'],uuid_]
                coord=spec.get(direction,[0,3] if direction=='previous' else [7,3]) if p['device']=='VSDXL' else spec.get(direction,[3,1] if direction=='previous' else [4,1])
                name='nav-'+direction+'.png';tile(direction.upper(),'←' if direction=='previous' else '→','nav').save(folder/'Images'/name)
                a=copy.deepcopy(a);a['States']=[{'Image':name,'Title':'','ShowTitle':False}];insert(direction,coord,a,{})
            uuid_='com.hotspot.streamdock.multiactions.routine';a,assets=utilities[p['sim'],p['device'],uuid_]
            coord=spec.get('simulator',[6,3] if p['device']=='VSDXL' else [4,0]);insert('simulator',coord,a,assets)
            if p['device']=='VSDXL':
                uuid_='com.hotspot.streamdock.page.indicator';a,_=utilities[p['sim'],p['device'],uuid_];a=copy.deepcopy(a)
                name='page-indicator.png';tile(spec['title'],f'{i+1} / {len(specs)}','nav').save(folder/'Images'/name);a['States']=[{'Image':name,'Title':'','ShowTitle':False}];insert('indicator',[3,3],a,{})
            (folder/'manifest.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
        p['pages']=len(specs);p['page_titles']=[spec['title'] for spec in specs]
    with (PAYLOAD/'controls.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(new_rows)
    (PAYLOAD/'profiles.json').write_text(json.dumps(profiles,indent=2))
    shutil.copy2(WORK/'panel-layout.json',PAYLOAD/'panel-layout.json')
    print(json.dumps({'profiles':4,'pages':sum(p['pages'] for p in profiles),'control_rows':len(new_rows),'new_N4_pages':len(layout['VSDN4Pro'])},indent=2))

if __name__=='__main__':apply()
