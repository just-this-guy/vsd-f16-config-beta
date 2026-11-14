"""Fresh installs, updates, prerequisite checks and synchronized binding edits in isolated folders."""
import argparse,contextlib,copy,io,json,pathlib,shutil,sqlite3,sys,tempfile,types,unittest
from unittest.mock import patch
import share_installer as engine
import beta_install as beta
import binding_review as br
import dcs_prerequisites as deps

WORK=pathlib.Path(__file__).resolve().parent;engine.HERE=WORK/'payload'

def snapshot(root):return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}

class InstallerTests(unittest.TestCase):
    def setUp(self):
        runs=WORK/'test-runs';runs.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=runs);self.root=pathlib.Path(self.temp.name)
        self.vsd=self.root/'vsd';(self.vsd/'config').mkdir(parents=True)
        self.config=self.vsd/'config/StreamDockConfig.ini'
        self.config.write_text('[StreamDockCurrentDevice]\nVSDXL\\SerialNumber=TEST-XL\nVSDN4Pro\\SerialNumber=TEST-N4\n[Selections]\nKeep=existing\n')
        c=sqlite3.connect(self.vsd/'config/DataCache.db')
        for table in ['VSDXL','VSDN4Pro']:c.execute('create table '+table+' (Profile TEXT)')
        c.execute('create table unrelated(value TEXT)');c.execute("insert into unrelated values ('preserve')");c.commit();c.close()
        (self.vsd/'profiles/untouched').mkdir(parents=True);(self.vsd/'profiles/untouched/keep.txt').write_bytes(b'keep unrelated profile')
        self.bms=self.root/'bms';self.bms.mkdir()
        self.bindings=json.loads((engine.HERE/'bindings/BMS-keyboard-bindings.json').read_text())
        self.keytext=''.join(f"{b['callback']} -1 0 0x{b['scan_code']:X} {b['modifier_mask']} 0 0 1 \"{b['description']}\"\n" for b in self.bindings)+'Unrelated -1 0 0xEE 0 0 0 1 "Keep keyboard"\nDXKeep -1 -2 0x3 0 0 0 1 "Keep MFD"\n'
        for name in ['BMS - Full.key','BMS - Auto.key']:(self.bms/name).write_text(self.keytext)
        self.dcs=self.root/'dcs';export=self.dcs/'Scripts/DCS-ExportScript';(export/'ExportsModules').mkdir(parents=True)
        (export/'ExportScript.lua').write_text('-- prerequisite fixture, never executed')
        (export/'ExportsModules/F-16C_50.lua').write_text('ExportScript.ConfigEveryFrameArguments = {}\n-- keep existing aircraft exports\n')
        (export/'Config.lua').write_text('ExportScript.Config.IkarusExport = true\nExportScript.Config.Listener = true\nExportScript.Config.ListenerPort = 26027\nExportScript.Config.IkarusHost = "127.0.0.1"\nExportScript.Config.IkarusPort = 1725\nExportScript.Config.IkarusSeparator = ":"\n')
        (self.dcs/'Scripts/Export.lua').write_text('dofile(lfs.writedir()..[[Scripts\\DCS-ExportScript\\ExportScript.lua]])\n-- keep other tool hooks\n')
        plugin=self.vsd/'plugins/com.ctytler.dcs.sdPlugin';plugin.mkdir(parents=True)
        (plugin/'manifest.json').write_text(json.dumps({'Actions':[{'UUID':id} for id in deps.REQUIRED_ACTIONS],'CodePathWin':'fixture.exe'}));(plugin/'fixture.exe').write_bytes(b'never execute fixture')
        self.program=self.root/'DCS-program'
        for rel,text in [('Mods/aircraft/F-16C/Input/F-16C/keyboard/default.lua',"local res = external_profile('Config/Input/Aircrafts/common_keyboard_binding.lua')\nreturn res"),('Config/Input/Aircrafts/common_keyboard_binding.lua','return {keyCommands={}}'),('Config/Input/UiLayer/keyboard/default.lua','return {keyCommands={}}'),('Scripts/Input/DefaultAssignments.lua','default_assignments["Keyboard"] = {pitch_up={key="Up"}}')]:
            p=self.program/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
        self.args=argparse.Namespace(sim='both',devices=['VSDXL','VSDN4Pro'],vsd_root=str(self.vsd),bms_config=str(self.bms),dcs_saved_games=str(self.dcs),prerequisite_vsd_root=str(self.vsd),prerequisite_bms_root=str(self.bms),prerequisite_dcs_root=str(self.dcs),dcs_install=str(self.program),bms_keyfiles=None,binding_overrides={},paired=True,replace_existing=True,backup_dir=str(self.root/'backups'),create_backup=True,apply=True)
    def tearDown(self):self.temp.cleanup()
    def install(self,args=None):
        with patch.object(beta.subprocess,'run',return_value=types.SimpleNamespace(stdout='')),contextlib.redirect_stdout(io.StringIO()):return engine.install(args or self.args)
    def manifests(self):return [json.loads(p.read_text()) for p in (self.vsd/'profiles').rglob('manifest.json')]
    def test_review_is_read_only(self):
        before=snapshot(self.root);self.args.apply=False;self.install();self.assertEqual(before,snapshot(self.root))
    def test_fresh_both_install_includes_runtime_hook_and_30_pages(self):
        original=self.config.read_bytes();backup=self.install()
        self.assertEqual(len(self.manifests()),30);self.assertTrue((self.vsd/'plugins'/beta.PLUGIN/'VSD F16 Controls.exe').is_file())
        self.assertTrue((self.dcs/'Scripts/VSD-F16-States.lua').exists());self.assertEqual(self.config.read_bytes(),original)
        self.assertIn('-- keep other tool hooks',(self.dcs/'Scripts/Export.lua').read_text());self.assertTrue((pathlib.Path(backup)/'restore-manifest.json').exists())
        c=sqlite3.connect(self.vsd/'config/DataCache.db');self.assertEqual(c.execute('select value from unrelated').fetchone()[0],'preserve');self.assertEqual(c.execute('select count(*) from VSDXL').fetchone()[0],2);c.close()
        self.assertEqual((self.vsd/'profiles/untouched/keep.txt').read_bytes(),b'keep unrelated profile')
    def test_bms_only_needs_no_dcs_and_disables_simulator_toggle(self):
        self.args.sim='bms';self.args.dcs_saved_games=None;shutil.rmtree(self.dcs);shutil.rmtree(self.program)
        self.install();self.assertEqual(len(self.manifests()),15);self.assertFalse(self.dcs.exists())
        for m in self.manifests():
            for a in m['Actions'].values():
                if a['UUID']=='com.hotspot.streamdock.multiactions.routine':self.assertFalse(a['Actions']);self.assertEqual(a['States'][0]['Title'],'BMS ONLY')
    def test_dcs_only_needs_no_bms_files(self):
        self.args.sim='dcs';self.args.bms_config=None;shutil.rmtree(self.bms);self.install();self.assertEqual(len(self.manifests()),15);self.assertFalse(self.bms.exists())
    def test_single_panel_both_installs_only_its_profiles(self):
        self.args.devices=['VSDXL'];self.args.paired=False;self.install();self.assertEqual(len(self.manifests()),14)
        for m in self.manifests():
            self.assertEqual(m['DeviceUUID'],'VSDXL')
            for a in m['Actions'].values():
                for step in a.get('Actions',[]):self.assertEqual(step['Settings']['deviceUUID'],'VSDXL')
    def test_missing_prerequisite_blocks_before_changes(self):
        (self.vsd/'plugins/com.ctytler.dcs.sdPlugin/fixture.exe').unlink();before=snapshot(self.root)
        with self.assertRaisesRegex(ValueError,'prerequisites'):self.install()
        self.assertEqual(before,snapshot(self.root))
    def test_commented_export_hook_is_rejected(self):
        hook=self.dcs/'Scripts/Export.lua';hook.write_text('--[[\n'+hook.read_text()+'\n]]')
        with self.assertRaisesRegex(ValueError,'prerequisites'):self.install()
    def test_custom_listener_port_is_carried_into_runtime(self):
        config=self.dcs/'Scripts/DCS-ExportScript/Config.lua';config.write_text(config.read_text().replace('26027','26029'));self.install()
        self.assertEqual(json.loads((self.vsd/'plugins'/beta.PLUGIN/'runtime-settings.json').read_text())['command_port'],26029)
    def test_conflicting_feedback_listener_port_is_rejected(self):
        config=self.dcs/'Scripts/DCS-ExportScript/Config.lua';config.write_text(config.read_text().replace('26027','26028'))
        with self.assertRaisesRegex(ValueError,'prerequisites'):self.install()
    def test_update_backs_up_profiles_runtime_and_retains_database_entries(self):
        self.install();old=self.vsd/'profiles'/json.loads((engine.HERE/'profiles.json').read_text())[0]['folder']/'old-only.txt';old.write_text('old asset')
        backup=pathlib.Path(self.install());self.assertFalse(old.exists());self.assertTrue(list((backup/'directories').glob('*/old-only.txt')))
        self.assertTrue(list((backup/'directories').glob('*/controls.json')))
        c=sqlite3.connect(self.vsd/'config/DataCache.db');self.assertEqual(c.execute('select count(*) from VSDXL').fetchone()[0],2);c.close()
        self.assertEqual((self.dcs/'Scripts/Export.lua').read_text().count('VSD-F16-States.lua'),1)
    def test_no_backup_choice_keeps_no_persistent_backup(self):
        self.args.create_backup=False;self.assertIsNone(self.install());self.assertFalse(list((self.root/'backups').iterdir()))
    def test_application_running_blocks_before_backup_and_changes(self):
        before=snapshot(self.root)
        with patch.object(beta.subprocess,'run',return_value=types.SimpleNamespace(stdout='"VSD Craft.exe","1"\n')),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'Close these programs'):engine.install(self.args)
        self.assertEqual(before,snapshot(self.root))
    def test_factory_shortcut_conflict_is_rejected(self):
        row=next(r for r in br.proposals(engine.HERE) if r['sim']=='DCS');combo={'key':row['key'],'reformers':{i+1:v for i,v in enumerate(row['mods'])}}
        (self.program/'Config/Input/Aircrafts/common_keyboard_binding.lua').write_text('return {keyCommands={{combos={'+engine.lua_dump(combo)+'},down=42,name=_("Factory conflict")}}}')
        before=snapshot(self.root)
        with self.assertRaisesRegex(ValueError,'Factory conflict'):self.install()
        self.assertEqual(before,snapshot(self.root))
    def test_selected_custom_bms_keyfile_is_only_one_changed(self):
        custom=self.bms/'Custom.key';custom.write_text(self.keytext);self.args.bms_keyfiles=[str(custom)]
        before=(self.bms/'BMS - Full.key').read_bytes();self.install();self.assertEqual((self.bms/'BMS - Full.key').read_bytes(),before)
        self.assertIn('DXKeep -1 -2',custom.read_text());self.assertIn('Unrelated -1 0 0xEE',custom.read_text())
    def test_bms_edit_reaches_keyfile_runtime_and_native_buttons(self):
        proposal=next(r for r in br.proposals(engine.HERE) if r['sim']=='BMS' and r['command']=='SimMasterFuelOn')
        self.args.binding_overrides={proposal['id']:{'key':'Enter','mods':['LShift','LCtrl','LAlt']}}
        self.install();catalog=json.loads((self.vsd/'plugins'/beta.PLUGIN/'controls.json').read_text())
        entry=next(b for b in catalog['fuel']['bindings'] if b['callback']=='SimMasterFuelOn')
        self.assertEqual((entry['scan_code'],entry['modifier_mask']),(0x1c,7))
        self.assertIn('0X1C 7',next(l for l in (self.bms/'BMS - Auto.key').read_text().splitlines() if l.startswith('SimMasterFuelOn ')))
    def test_dcs_edit_reaches_diff_and_native_encoder(self):
        row=next(r for r in br.proposals(engine.HERE) if r['sim']=='DCS')
        self.args.binding_overrides={row['id']:{'key':'Enter','mods':['LShift','LCtrl','LAlt']}}
        self.install();key=self.dcs/'Config/Input/F-16C_50/keyboard/Keyboard.diff.lua';data=engine.lua_load(key.read_text())
        self.assertTrue(any(br.combo(c)==br.chord('Enter',['LShift','LCtrl','LAlt']) for c in data['keyDiffs'][row['command']]['added'].values()))
        matched=0
        for p in json.loads((engine.HERE/'profiles.json').read_text()):
            if p['sim']!='DCS':continue
            for path in (engine.HERE/'profiles'/p['folder']).rglob('manifest.json'):
                source=json.loads(path.read_text());target=json.loads((self.vsd/path.relative_to(engine.HERE)).read_text())
                for coord,a in source['Actions'].items():
                    for i,h in enumerate(a.get('Settings',{}).get('Hotkeys',[])):
                        if br.hotkey_chord(h)==row['original']:
                            self.assertEqual(br.hotkey_chord(target['Actions'][coord]['Settings']['Hotkeys'][i]),br.chord('Enter',['LShift','LCtrl','LAlt']));matched+=1
        self.assertGreater(matched,0)
    def test_missing_packaged_runtime_blocks_without_mutation(self):
        source=engine.HERE;fake=self.root/'payload';shutil.copytree(source,fake);(fake/beta.PLUGIN/'VSD F16 Controls.exe').unlink();engine.HERE=fake
        try:
            before=snapshot(self.root)
            with self.assertRaisesRegex(ValueError,'runtime is missing'):self.install()
            self.assertEqual(before,snapshot(self.root))
        finally:engine.HERE=source
    def test_transaction_failure_restores_original_files(self):
        self.install();before=snapshot(self.vsd);bms_before=snapshot(self.bms);dcs_before=snapshot(self.dcs)
        real=pathlib.Path.write_bytes;fired=False
        def fail_once(path,data):
            nonlocal fired
            if path.name.startswith('beta-large-') and not fired:fired=True;raise OSError('Simulated write failure')
            return real(path,data)
        with patch.object(pathlib.Path,'write_bytes',fail_once):
            with self.assertRaisesRegex(OSError,'Simulated'):self.install()
        self.assertTrue(fired);self.assertEqual(before,snapshot(self.vsd));self.assertEqual(bms_before,snapshot(self.bms));self.assertEqual(dcs_before,snapshot(self.dcs))
    def test_dcs_only_update_preserves_custom_bms_runtime_mapping(self):
        self.test_bms_edit_reaches_keyfile_runtime_and_native_buttons();catalog=self.vsd/'plugins'/beta.PLUGIN/'controls.json';before=json.loads(catalog.read_text())['fuel']['bindings']
        self.args.binding_overrides={};self.args.sim='dcs';self.args.bms_config=None;self.install()
        self.assertEqual(json.loads(catalog.read_text())['fuel']['bindings'],before)


if __name__=='__main__':unittest.main()
