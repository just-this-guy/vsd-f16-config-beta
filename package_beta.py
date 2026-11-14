"""Package the standalone beta, source, documentation, and runtime licenses."""
import argparse,hashlib,json,pathlib,shutil,zipfile

WORK=pathlib.Path(__file__).resolve().parent;OUT=WORK/'dist'
SOURCES=['portable_gui.py','share_installer.py','beta_install.py','binding_review.py','binding_editor.py','dcs_prerequisites.py','f16_plugin.py','graphics.py','regenerate_graphics.py','render_preview.py','build_beta.py','test_beta.py','test_runtime.py','panel-layout.json','apply_panel_layout.py','test_panel_layout.py','package_beta.py']
README='''VSD F16 Config Beta — portable Windows setup

Run VSD F16 Config Beta.exe. Python is included; no separate Python installation is required. You may share this EXE directly, or share the portable ZIP with these instructions and runtime licenses.

1. Close VSD Craft and the simulator(s) you want to configure.
2. Confirm the detected VSD XL / N4 Pro panels and software folders.
3. Select BMS only, DCS only, or both. Select either panel or both panels.
4. Check the prerequisites. DCS Interface by Charlie Tytler and DCS-ExportScript are separate prerequisites; download/help buttons open their authors' pages. Missing prerequisites stop installation. BMS-only setup does not require DCS.
5. Choose the BMS keyfiles you actually use. Open Review / edit shortcuts to inspect all proposed assignments, find conflicts, edit keys/modifiers, and save/load your mapping. Edits are applied to the simulator bindings and corresponding control buttons together.
6. Choose Review choices, then Apply changes. Choose whether to keep rollback backups when prompted. Conflicts and incomplete checks stop Apply.
7. Open VSD Craft and choose the matching F-16 profile for each panel. Restart DCS after changing its export scripts.

The latest design is included: one button per switch/selector, repeated presses to toggle or cycle, changing graphics, larger bold top-center labels, and larger state captions. Bottom-left red/green indicators have twice the previous diameter. Long labels wrap. The package contains four profiles and 28 pages.

The control runtime installs with the profiles in VSD Craft's plugin folder. Existing matching F-16 profiles can be updated. Single-simulator installations show a simulator badge rather than a toggle to an unavailable simulator. With both simulators installed, logo toggles can switch the selected panel or both panels. No Windows service, startup task, automatic download, or system-wide Python installation is created.

BMS switch graphics track commands made through VSD; they are not live cockpit telemetry. Starting a new flight or changing switches elsewhere can desynchronize them. BMS must be the foreground application. A yellow warning triangle after a rejected press can mean BMS does not have keyboard focus; bring the running BMS cockpit to the foreground and retry. Rejected presses do not change the displayed state. Release unrelated held keyboard modifiers before pressing.

DCS switch graphics follow cockpit feedback. Gray / NO DATA means no fresh F-16 feedback is available. DCS command routing follows the checked DCS-ExportScript listener port; dedicated F-16 telemetry uses loopback port 26028. Existing export hooks remain chained. Red means OFF (or a closed refueling door); green indicates an active named setting. Selectors without an OFF setting use green for their named modes.

Backups default to Documents/VSD F16 Config Beta/Backups. Each contains a restore-manifest.json, changed original files/directories, the VSD database when affected, a binding-review.json report, and an installation report. Unrelated profiles, keyboard entries and joystick/MFD assignments are preserved. If installation fails after changes begin, the installer attempts to restore the prior files automatically, retaining backup evidence.

Validation: 19 isolated installation tests and 16 offline runtime tests; standalone EXE/GUI self-check with Python removed from PATH; all 28 pages and 174 editable shortcut rows verified. Fresh BMS-only, DCS-only, both-simulator and single-panel scenarios, updates, backups, edited bindings, prerequisite failures, conflict blocking and rollback are covered. Physical-device/in-flight validation is still pending. This beta EXE is unsigned.

DCS Interface plugin ID: com.ctytler.dcs.sdPlugin. The separately installed DCS Interface and other third-party simulator software are not bundled. Simulator logos and third-party components retain their owners' rights. Runtime license notices are included in the ZIP. No open-source license has been selected for the original profile/application code.
'''

def package(license_source):
    report=json.loads((OUT/'exe-self-check.json').read_text())
    assert report['status']=='ok' and report['bundled_python'] and report['pages']==30
    readme=README.replace('four profiles and 28 pages','four profiles and 30 pages').replace('offline runtime tests;','offline runtime tests; 10 panel-layout checks;')
    readme+='\nCockpit layout: seven XL pages and eight N4 Pro pages per simulator use deliberate rows/columns and gaps. N4 avionics power is split into an upper/middle view and an INS/MIDS lower view. See docs/PANEL-LAYOUT.md in the source or GitHub repository for references and hardware compromises.\n'
    (OUT/'Read me.txt').write_text(readme,encoding='utf-8')
    release={'product':'VSD F16 Config Beta','version':'0.3.1-beta','date':'2026-11-14','profiles':4,'pages':30,'installer_tests':19,'runtime_tests':16,'layout_tests':10,'binding_editor_rows':174,'layout':'cockpit-like rows and columns','labels':'larger bold top-center labels','state_dots':'twice the previous diameter','in_flight_validation':'pending'}
    (OUT/'release.json').write_text(json.dumps(release,indent=2))
    licenses=OUT/'Third-party licenses'
    if not licenses.exists():shutil.copytree(license_source,licenses)
    selected=[OUT/'VSD F16 Config Beta.exe',OUT/'Read me.txt',OUT/'release.json']+[p for p in licenses.rglob('*') if p.is_file()]
    checks=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(OUT).as_posix()+'\n' for p in sorted(selected))
    (OUT/'SHA256SUMS').write_text(checks)
    with zipfile.ZipFile(OUT/'VSD-F16-Config-Beta-Portable.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in selected+[OUT/'SHA256SUMS']:z.write(p,p.relative_to(OUT).as_posix())
    with zipfile.ZipFile(OUT/'VSD-F16-Config-Beta-Source.zip','w',zipfile.ZIP_DEFLATED) as z:
        z.write(OUT/'VSD F16 Config Beta.exe','VSD F16 Config Beta.exe')
        for name in SOURCES:z.write(WORK/name,name)
        for p in (WORK/'payload').rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.log']:z.write(p,p.relative_to(WORK).as_posix())
        z.writestr('Read me.txt',readme)
        for p in (WORK/'docs').rglob('*'):
            if p.is_file():z.write(p,p.relative_to(WORK).as_posix())
        for p in licenses.rglob('*'):
            if p.is_file():z.write(p,'licenses/'+p.relative_to(licenses).as_posix())
        z.writestr('Build.txt','Install Python 3.10+ with Tk and PyInstaller. Run:\npython build_beta.py --python "C:/path/to/python.exe"\n\nFor image regeneration also install Pillow, then run python regenerate_graphics.py before building.\nRun python test_beta.py and python test_runtime.py for offline tests.\nOutput: dist/VSD F16 Config Beta.exe. No simulator commands are issued by the tests.\n')
    for path in OUT.glob('VSD-F16-Config-Beta-*.zip'):
        with zipfile.ZipFile(path) as z:assert z.testzip() is None
    home=[str(pathlib.Path.home()).encode().lower(),str(pathlib.Path.home()).replace('\\','/').encode().lower()]
    for p in [WORK/name for name in SOURCES]+list((WORK/'payload').rglob('*.json')):
        for needle in home:assert needle not in p.read_bytes().lower(),p
    for p in (WORK/'payload/profiles').rglob('manifest.json'):
        data=json.loads(p.read_text());assert not data.get('DeviceSerialNumber')
        def serials(node):
            if isinstance(node,dict):
                if 'serialNumber' in node:assert node['serialNumber']==''
                for v in node.values():serials(v)
            elif isinstance(node,list):
                for v in node:serials(v)
        serials(data)
    print(json.dumps({'exe':str(OUT/'VSD F16 Config Beta.exe'),'portable_zip':str(OUT/'VSD-F16-Config-Beta-Portable.zip'),'size_MB':round((OUT/'VSD F16 Config Beta.exe').stat().st_size/1048576,2)},indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--licenses',type=pathlib.Path,required=True);package(parser.parse_args().licenses)
