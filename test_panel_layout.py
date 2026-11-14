"""Check output geometry against the reviewed cockpit panel arrangements."""
import contextlib,csv,hashlib,io,json,pathlib,unittest
from apply_panel_layout import LABELS,sdk

WORK=pathlib.Path(__file__).resolve().parent;PAYLOAD=WORK/'payload'

class PanelLayoutTests(unittest.TestCase):
    def setUp(self):
        self.layout=json.loads((WORK/'panel-layout.json').read_text());self.profiles=json.loads((PAYLOAD/'profiles.json').read_text())
    def manifest(self,device,title,sim='BMS'):
        p=next(p for p in self.profiles if p['device']==device and p['sim']==sim)
        root=PAYLOAD/'profiles'/p['folder'];base=json.loads((root/'manifest.json').read_text());i=p['page_titles'].index(title)
        folder=root if i==0 else root/'profiles'/base['Pages']['Pages'][i]
        return json.loads((folder/'manifest.json').read_text()),folder
    def position(self,device,title,control):
        m,_=self.manifest(device,title)
        coord=next(coord for coord,a in m['Actions'].items() if a.get('Settings',{}).get('control')==control)
        x,y=map(int,coord.split(','));return x,y if device=='VSDXL' else 2-y
    def test_hud_four_upper_three_lower_on_both_models(self):
        for device in ['VSDXL','VSDN4Pro']:
            for x,id in enumerate(['scales','fpm','ded','reticle']):self.assertEqual(self.position(device,'HUD PANEL',id),(x,0))
            for x,id in enumerate(['speed','alt','hudbrt']):self.assertEqual(self.position(device,'HUD PANEL',id),(x,1))
    def test_avionics_five_switch_row_and_offset_gps_dl(self):
        for device in ['VSDXL','VSDN4Pro']:
            for x,id in enumerate(['mmc','sms','mfd','ufc','map']):self.assertEqual(self.position(device,'AVIONICS POWER',id),(x,0))
            self.assertEqual(self.position(device,'AVIONICS POWER','gps'),(2,1));self.assertEqual(self.position(device,'AVIONICS POWER','dl'),(3,1))
    def test_ins_mids_keep_columns_in_lower_n4_view(self):
        for id,x in [('ins',1),('mids',4)]:
            self.assertEqual(self.position('VSDXL','AVIONICS POWER',id),(x,2));self.assertEqual(self.position('VSDN4Pro','INS / MIDS',id),(x,0))
    def test_sensor_power_keeps_four_switches_in_one_row(self):
        for device,title in [('VSDXL','SNSR / AIR / OXY'),('VSDN4Pro','AUDIO / SENSOR')]:
            for x,id in enumerate(['lhdpt','rhdpt','fcr','ralt']):self.assertEqual(self.position(device,title,id),(x,0))
    def test_external_lighting_rows_match_both_manuals(self):
        for device in ['VSDXL','VSDN4Pro']:
            for x,id in enumerate(['anticoll','flash','wing','fuselage']):self.assertEqual(self.position(device,'EXT LIGHTING',id),(x,0))
            self.assertEqual(self.position(device,'EXT LIGHTING','lightmaster'),(1,1))
    def test_ecm_module_grid_and_bit_position(self):
        m,_=self.manifest('VSDXL','ECM PANEL');rows=list(csv.DictReader(io.StringIO((PAYLOAD/'controls.csv').read_text(encoding='utf-8-sig'))))
        mapping={r['control']:r['coordinate'] for r in rows if (r['sim'],r['device'],r['page'])==('BMS','VSDXL','ECM PANEL')}
        for i,x in [(1,2),(2,3),(3,4),(4,5)]:self.assertEqual(mapping['ECM '+str(i)],f'{x},0')
        self.assertEqual(mapping['ECM 5'],'2,1');self.assertEqual(mapping['ECM BIT'],'1,1')
    def test_all_original_control_functions_remain_available(self):
        rows=list(csv.DictReader(io.StringIO((PAYLOAD/'controls.csv').read_text(encoding='utf-8-sig'))))
        for sim in ['BMS','DCS']:
            actual={r['control'] for r in rows if r['sim']==sim}
            self.assertFalse(set(LABELS.values())-actual)
        knobs={k for p in self.layout['VSDN4Pro'] for k in p.get('knobs',{}).values()}
        self.assertEqual(knobs,{'comm1','comm2','msl','threat','hud','hmcs','inst','flood','dedbrt','formation','aar'})
    def test_all_actions_are_in_bounds_unique_and_have_graphics(self):
        count=0
        for p in self.profiles:
            root=PAYLOAD/'profiles'/p['folder'];base=json.loads((root/'manifest.json').read_text())
            self.assertEqual(len(base['Pages']['Pages']),p['pages'])
            for i,page in enumerate(base['Pages']['Pages']):
                count+=1;folder=root if i==0 else root/'profiles'/page;m=json.loads((folder/'manifest.json').read_text());ids=set();roles=set()
                for coord,a in m['Actions'].items():
                    x,y=map(int,coord.split(','));self.assertTrue(0<=x<(8 if p['device']=='VSDXL' else 5));self.assertTrue(0<=y<=(3 if p['device']=='VSDXL' else 2))
                    self.assertNotIn(a['ActionID'],ids);ids.add(a['ActionID'])
                    id=a.get('Settings',{}).get('control')
                    if id:self.assertNotIn(id,roles);roles.add(id)
                    for state in a['States']:self.assertTrue((folder/'Images'/state['Image']).is_file())
        self.assertEqual(count,30)
    def test_bms_dcs_key_positions_match(self):
        for device in ['VSDXL','VSDN4Pro']:
            for spec in self.layout[device]:
                b,_=self.manifest(device,spec['title'],'BMS');d,_=self.manifest(device,spec['title'],'DCS')
                for role,coord in spec['keys'].items():
                    pos=sdk(coord,device)
                    if b['Actions'][pos]['UUID']=='org.f16vsd.cycling.selector':
                        if role in {f'ecm{i}' for i in range(1,6)}:
                            self.assertEqual(b['Actions'][pos]['Settings']['control'],role)
                            self.assertNotEqual(d['Actions'][pos]['UUID'],'org.f16vsd.cycling.selector')
                        else:self.assertEqual(b['Actions'][pos]['Settings']['control'],d['Actions'][pos]['Settings']['control'])
    def test_compiler_repeat_keeps_identical_art_and_commands(self):
        from apply_panel_layout import apply
        snapshot=lambda:{str(p.relative_to(PAYLOAD)):hashlib.sha256(p.read_bytes()).hexdigest() for p in PAYLOAD.rglob('*') if p.is_file()}
        before=snapshot()
        with contextlib.redirect_stdout(io.StringIO()):apply()
        self.assertEqual(before,snapshot())

if __name__=='__main__':unittest.main()
