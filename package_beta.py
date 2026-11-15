"""Package the standalone beta, source, documentation, and runtime licenses."""
import argparse,hashlib,json,pathlib,shutil,zipfile

WORK=pathlib.Path(__file__).resolve().parent;OUT=WORK/'dist'
SOURCES=['portable_gui.py','share_installer.py','beta_install.py','binding_review.py','binding_editor.py','dcs_prerequisites.py','f16_plugin.py','graphics.py','regenerate_graphics.py','render_preview.py','build_beta.py','test_beta.py','test_runtime.py','panel-layout.json','apply_panel_layout.py','test_panel_layout.py','explicit_bms.py','package_beta.py']
README='VSD F16 Config Beta\n\nrearanged icons to more closely match Block 50 layout\n\nExtract the ZIP and run VSD F16 Config Beta.exe from the top-level folder.\nClose VSD Craft and the simulators first. Back up any layout you have edited.\n\nChoose BMS, DCS, or both, and the panels you use. Check prerequisites, review\nand edit the shortcuts, then review your choices and apply.\n\nDCS needs DCS Interface by Charlie Tytler and DCS-ExportScript; the installer\nincludes links. BMS must have keyboard focus when using the buttons.\n\nBMS icons remember commands sent through VSD, so mouse/HOTAS changes can leave\nthem out of sync until another successful button press. DCS uses cockpit feedback.\n\nThis is an informal, unsigned beta. Expect rough edges.\n'

def package(license_source):
    report=json.loads((OUT/'exe-self-check.json').read_text())
    assert report['status']=='ok' and report['bundled_python'] and report['pages']==sum(p['pages'] for p in json.loads((WORK/'payload/profiles.json').read_text()))
    readme=README
    (OUT/'Read me.txt').write_text(readme,encoding='utf-8')
    release={'product':'VSD F16 Config Beta','version':'0.3.3-beta','profiles':4,'pages':report['pages']}
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
