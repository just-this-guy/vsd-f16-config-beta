import json,pathlib
from PIL import Image,ImageDraw,ImageFont

WORK=pathlib.Path(__file__).resolve().parent;PAYLOAD=WORK/'payload';OUT=WORK/'dist';OUT.mkdir(exist_ok=True)
profiles=json.loads((PAYLOAD/'profiles.json').read_text());plugin=PAYLOAD/'org.f16vsd.cycling.sdPlugin';catalog=json.loads((plugin/'controls.json').read_text())
for p in profiles:
    root=PAYLOAD/'profiles'/p['folder'];base=json.loads((root/'manifest.json').read_text())
    for i,page in enumerate(base['Pages']['Pages']):
        folder=root if i==0 else root/'profiles'/page;m=json.loads((folder/'manifest.json').read_text());xl=p['device']=='VSDXL'
        im=Image.new('RGB',(1600 if xl else 1120,1100 if xl else 1040),'#0c0d10');d=ImageDraw.Draw(im)
        d.text((25,20),'VSD F16 Config Beta  /  '+p['sim']+'  /  '+p['device']+f'  /  {i+1}',font=ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf',28),fill='white')
        for coord,a in m['Actions'].items():
            x,y=map(int,coord.split(','));s=a['States'][0];c=catalog.get(a.get('Settings',{}).get('control'))
            asset=plugin/c['images'][c['initial']] if c else folder/'Images'/s['Image']
            size=185 if xl else 195;knob=a.get('Controller')=='Knob'
            px=25+x*(195 if xl else 216);py=110+y*220 if xl else 110+(2-y)*265
            if knob:px=30+x*267;py=745
            im.paste(Image.open(asset).convert('RGB').resize((size,size),Image.Resampling.LANCZOS),(px,py))
        out=OUT/'Gallery';out.mkdir(exist_ok=True);im.save(out/f"{p['sim']}-{p['device']}-{i+1}.png")
contact=Image.new('RGB',(5*276,2*306),'#0c0d10');d=ImageDraw.Draw(contact)
for i,(id,index) in enumerate([('main',2),('main',0),('fuel',0),('fuel',1),('ins',0),('ins',1),('ins',2),('ins',3),('lightmaster',4),('ralt',1)]):
    c=catalog[id];image=Image.open(plugin/c['images'][index]);contact.paste(image,((i%5)*276+10,(i//5)*306+30))
contact.save(OUT/'Larger-labels-and-indicators.png')
print(OUT/'Larger-labels-and-indicators.png')
