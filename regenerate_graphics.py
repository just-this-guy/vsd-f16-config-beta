"""Larger text and fresh image names for both VSD models and both simulators."""
import csv,hashlib,json,pathlib,shutil
from graphics import tile

WORK=pathlib.Path(__file__).resolve().parent;PAYLOAD=WORK/'payload';PLUGIN=PAYLOAD/'org.f16vsd.cycling.sdPlugin'

def save_image(image,folder):
    name='beta-large-'+hashlib.sha256(image.tobytes()).hexdigest()[:20]+'.png'
    image.save(folder/name);return name

def main():
    catalog=json.loads((PLUGIN/'controls.json').read_text())
    for c in catalog.values():
        c['images']=['images/'+save_image(tile(c['label'],state,c['kind'],i,len(c['states'])),PLUGIN/'images') for i,state in enumerate(c['states'])]
        c['offline']='images/'+save_image(tile(c['label'],'NO DATA',c['kind'],offline=True),PLUGIN/'images')
    (PLUGIN/'controls.json').write_text(json.dumps(catalog,indent=2))
    profiles=json.loads((PAYLOAD/'profiles.json').read_text());rows=list(csv.DictReader((PAYLOAD/'controls.csv').open(encoding='utf-8-sig')))
    layout=json.loads((WORK/'panel-layout.json').read_text()) if (WORK/'panel-layout.json').exists() else None
    knob_labels=[['COMM 1','COMM 2','MSL TONE','THREAT'],['HUD SYM','HMCS BRT','INST PNL','FLOOD CNS'],['HUD SYM','HMCS BRT','INST PNL','FLOOD CNS'],['INST PNL','DED BRT','FLOOD CNS','HUD SYM'],['FORM LIGHT','AAR LIGHT','INST PNL','FLOOD CNS'],['COMM 1','COMM 2','INST PNL','FLOOD CNS'],['HUD SYM','HMCS BRT','INST PNL','FLOOD CNS']]
    for p in profiles:
        root=PAYLOAD/'profiles'/p['folder'];base=json.loads((root/'manifest.json').read_text())
        names=p.get('page_titles') or list(dict.fromkeys(r['page'] for r in rows if (r['sim'],r['device'])==(p['sim'],p['device'])))
        for pi,page in enumerate(base['Pages']['Pages']):
            folder=root if pi==0 else root/'profiles'/page;m=json.loads((folder/'manifest.json').read_text());images=folder/'Images'
            page_rows=[r for r in rows if (r['sim'],r['device'],r['page'])==(p['sim'],p['device'],names[pi])]
            for coord,a in m['Actions'].items():
                kind=a['UUID']
                if kind=='org.f16vsd.cycling.selector':
                    c=catalog[a['Settings']['control']];index=a['Settings']['index']
                    source=PLUGIN/(c['offline'] if p['sim']=='DCS' else c['images'][index])
                    name=source.name;shutil.copy2(source,images/name);a['States']=[{'Image':name,'Title':'','ShowTitle':False}]
                elif a.get('Controller')=='Knob':
                    column=coord.split(',')[0]
                    if layout:
                        from apply_panel_layout import KNOB_LABELS
                        label=KNOB_LABELS[layout[p['device']][pi]['knobs'][column]]
                    else:label=knob_labels[pi][int(column)]
                    legend='ROTATE'
                    row=next((r for r in page_rows if r['coordinate']==coord and r['trigger']=='knob press'),None)
                    if row and a['Settings']['Hotkeys'][2].get('VKeyCode',-1)>=0:legend=row['control'].replace('PUSH KNOB 4: ','PUSH ')
                    name=save_image(tile(label,legend,'rotary',active=True),images);a['States']=[{'Image':name,'Title':'','ShowTitle':False}]
                elif kind.startswith('com.hotspot.streamdock.page.'):
                    suffix=kind.rsplit('.',1)[-1]
                    label,text=('PREVIOUS','←') if suffix=='previous' else ('NEXT','→') if suffix=='next' else (names[pi],f'{pi+1} / {len(base["Pages"]["Pages"])}')
                    name=save_image(tile(label,text,'nav'),images);a['States']=[{'Image':name,'Title':'','ShowTitle':False}]
                elif kind=='com.ctytler.dcs.lamp.button.two-state' or kind=='com.hotspot.streamdock.system.hotkey':
                    row=next((r for r in page_rows if r['coordinate']==coord and r['trigger']=='key'),None)
                    if not row:continue
                    for i,state in enumerate(a['States']):state['Image']=save_image(tile(row['control'],'PRESS','button',active=i>0),images)
            if pi==0:m['Name']=p['name']
            (folder/'manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8')
            used={s['Image'] for a in m['Actions'].values() for s in a['States']}
            for image in images.iterdir():
                if image.is_file() and image.name not in used:image.unlink()
    used={pathlib.Path(name).name for c in catalog.values() for name in [*c['images'],c['offline']]}
    manifest=json.loads((PLUGIN/'manifest.json').read_text());used.add(pathlib.Path(manifest['Icon']).name+'.png')
    for image in (PLUGIN/'images').iterdir():
        if image.is_file() and image.name not in used:image.unlink()
    print(json.dumps({'product':'VSD F16 Config Beta','profiles':4,'pages':28,'label_font':37,'previous_label_font':32,'status_font':31,'fresh_image_names':True},indent=2))

if __name__=='__main__':main()
