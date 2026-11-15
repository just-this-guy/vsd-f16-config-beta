"""Check the captured layouts and their packaged assets."""
import csv,io,json,pathlib,unittest
from apply_panel_layout import apply
WORK=pathlib.Path(__file__).resolve().parent;PAYLOAD=WORK/'payload'
class PanelLayoutTests(unittest.TestCase):
    def setUp(self):
        self.profiles=json.loads((PAYLOAD/'profiles.json').read_text())
        self.catalog=json.loads((PAYLOAD/'org.f16vsd.cycling.sdPlugin/controls.json').read_text())
    def pages(self):
        for p in self.profiles:
            root=PAYLOAD/'profiles'/p['folder'];base=json.loads((root/'manifest.json').read_text())
            self.assertEqual(len(base['Pages']['Pages']),p['pages'])
            self.assertEqual(len(p['page_titles']),p['pages'])
            for i,page in enumerate(base['Pages']['Pages']):
                folder=root if i==0 else root/'profiles'/page
                yield p,i,folder,json.loads((folder/'manifest.json').read_text())
    def test_saved_positions_match_layout_snapshot(self):apply()
    def test_all_actions_fit_and_have_assets(self):
        count=0
        for p,i,folder,m in self.pages():
            count+=1;ids=set()
            for coord,a in m['Actions'].items():
                x,y=map(int,coord.split(','));self.assertTrue(0<=x<(8 if p['device']=='VSDXL' else 5));self.assertTrue(0<=y<=(3 if p['device']=='VSDXL' else 2))
                self.assertNotIn(a['ActionID'],ids);ids.add(a['ActionID'])
                for s in a['States']:self.assertTrue((folder/'Images'/s['Image']).is_file())
                if a['UUID']=='org.f16vsd.cycling.selector':self.assertIn(a['Settings']['control'],self.catalog)
        self.assertEqual(count,29)
    def test_no_device_identity_is_published(self):
        def check(node):
            if isinstance(node,dict):
                for k,v in node.items():
                    if k in ('DeviceSerialNumber','serialNumber'):self.assertFalse(v)
                    check(v)
            elif isinstance(node,list):
                for v in node:check(v)
        for p,i,folder,m in self.pages():check(m)
    def test_bms_ecm_buttons_keep_explicit_commands(self):
        found=set()
        for p,i,folder,m in self.pages():
            if p['sim']!='BMS':continue
            for a in m['Actions'].values():
                control=a.get('Settings',{}).get('control','')
                if control in {f'ecm{i}' for i in range(1,6)}:
                    found.add(control);self.assertEqual(a['UUID'],'org.f16vsd.cycling.selector')
        self.assertEqual(found,{f'ecm{i}' for i in range(1,6)})
    def test_controls_table_tracks_the_saved_locations(self):
        pages={(p['sim'],p['device'],p['page_titles'][i]):m for p,i,folder,m in self.pages()}
        rows=csv.DictReader(io.StringIO((PAYLOAD/'controls.csv').read_text(encoding='utf-8-sig')))
        for r in rows:self.assertIn(r['coordinate'],pages[r['sim'],r['device'],r['page']]['Actions'])
if __name__=='__main__':unittest.main()
