"""Validate the saved VSD Craft arrangements without replacing them."""
import json,pathlib
WORK=pathlib.Path(__file__).resolve().parent
KNOB_LABELS={'comm1':'COMM 1','comm2':'COMM 2','msl':'MSL TONE','threat':'THREAT','hud':'HUD SYM','hmcs':'HMCS BRT','inst':'INST PNL','flood':'FLOOD CNS','dedbrt':'DED BRT','formation':'FORM LIGHT','aar':'AAR LIGHT'}
def sdk(coord,device):
    x,y=coord;return f'{x},{y if device=="VSDXL" else 2-y}'
def apply():
    layout=json.loads((WORK/'panel-layout.json').read_text())
    for folder,specs in layout['profiles'].items():
        root=WORK/'payload/profiles'/folder
        base=json.loads((root/'manifest.json').read_text())
        assert base['Pages']['Pages']==[s['page'] for s in specs]
        for i,s in enumerate(specs):
            page=root if i==0 else root/'profiles'/s['page']
            data=json.loads((page/'manifest.json').read_text())
            assert {k:a['ActionID'] for k,a in data['Actions'].items()}==s['actions']
    print('Saved VSD Craft layouts verified.')
if __name__=='__main__':apply()
