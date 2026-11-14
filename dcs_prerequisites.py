"""Read-only checks for separately installed DCS dependencies. Never execute Lua."""
import json
import os
import pathlib
import re

LINKS = {
    'VSD plugin downloads': 'https://www.vsdinside.com/blogs/tutorial/plugin-download',
    'DCS-ExportScripts download': 'https://github.com/s-d-a/DCS-ExportScripts',
    'DCS export installation guide': 'https://github.com/s-d-a/DCS-ExportScripts/wiki',
    'DCS Interface settings guide': 'https://github.com/enertial/streamdeck-dcs-interface/blob/master/Sources/com.ctytler.dcs.sdPlugin/helpDocs/helpContents.md',
}
REQUIRED_ACTIONS = {'com.ctytler.dcs.up-down.switch.two-state',
                    'com.ctytler.dcs.lamp.button.two-state'}

def uncomment(text):
    # Preserve quoted and long-bracket strings while discarding Lua comments.
    pattern = r"--\[(=*)\[.*?\]\1\]|--[^\n]*|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|\[(=*)\[.*?\]\2\]"
    return re.sub(pattern, lambda m: '\n' * m[0].count('\n') if m[0].startswith('--') else m[0], text, flags=re.S)

def check(vsd_root, dcs_root):
    vsd = pathlib.Path(vsd_root) if vsd_root else pathlib.Path(os.environ.get('APPDATA', pathlib.Path.home()/'AppData/Roaming'))/'HotSpot/StreamDock'
    dcs = pathlib.Path(dcs_root)
    rows = []
    def add(name, ok, detail):
        rows.append({'name': name, 'ok': bool(ok), 'detail': detail})
    plugin = vsd/'plugins/com.ctytler.dcs.sdPlugin'
    try:
        manifest = json.loads((plugin/'manifest.json').read_text(encoding='utf-8-sig'))
        actions = {a.get('UUID') for a in manifest.get('Actions', [])}
        code = manifest.get('CodePathWin') or manifest.get('CodePath')
        binary = (plugin/str(code)).resolve() if code else None
        ok = REQUIRED_ACTIONS <= actions and binary and binary.is_relative_to(plugin.resolve()) and binary.is_file() and binary.stat().st_size > 0
        add('DCS Interface plugin', ok, ('Found version '+str(manifest.get('Version', 'unknown'))) if ok else 'Install the VSD-compatible DCS Interface plugin in VSD Craft; required actions or its executable are missing.')
    except (OSError, ValueError, TypeError, AttributeError):
        add('DCS Interface plugin', False, 'Install DCS Interface through VSD Craft / SPACE, then select the correct VSD data folder. The Elgato package alone does not establish a VSD installation.')
    scripts = dcs/'Scripts'
    export = scripts/'DCS-ExportScript'
    for name, path in [('DCS export loader', export/'ExportScript.lua'), ('F-16C export module', export/'ExportsModules/F-16C_50.lua')]:
        add(name, path.is_file() and path.stat().st_size > 0, str(path))
    hook = scripts/'Export.lua'
    text = uncomment(hook.read_text(encoding='utf-8-sig')) if hook.is_file() else ''
    # Require a direct, enabled dofile hook rather than a filename in a comment.
    normalized = text.replace('\\\\', '/').replace('\\', '/')
    enabled = bool(re.search(r'dofile\s*\(\s*lfs\.writedir\s*\(\s*\)\s*\.\.\s*(?:\[\[|[\"\'])Scripts/DCS-ExportScript/ExportScript\.lua(?:\]\]|[\"\'])\s*\)', normalized, re.I))
    add('DCS export hook', enabled, 'Enabled standard dofile hook found.' if enabled else 'No recognized enabled DCS-ExportScript hook in Scripts/Export.lua. Follow the export installation guide, preserving hooks for other tools. Custom loader arrangements need manual review.')
    cfg = export/'Config.lua'
    config = uncomment(cfg.read_text(encoding='utf-8-sig')) if cfg.is_file() else ''
    def value(key):
        matches = re.findall(r'ExportScript\.Config\.'+key+r'\s*=\s*([^\n;]+)', config)
        return matches[-1].strip().strip('\"\'') if matches else None
    for key, label in [('IkarusExport', 'DCS feedback enabled'), ('Listener', 'DCS command listener enabled')]:
        ok = value(key) == 'true'
        add(label, ok, 'Enabled in Config.lua.' if ok else 'ExportScript.Config.'+key+' must be true in Config.lua.')
    warnings = []
    expected = {'IkarusHost': '127.0.0.1', 'IkarusPort': '1725', 'ListenerPort': '26027', 'IkarusSeparator': ':'}
    different = [key+'='+str(value(key)) for key, val in expected.items() if value(key) != val]
    if different:
        warnings.append('Custom or missing communication settings: '+', '.join(different)+'. Match these to DCS Interface settings before flying. Typical local settings: host 127.0.0.1, receive 1725, send 26027, separator colon.')
    port=value('ListenerPort')
    valid_port=bool(port and port.isdigit() and 1 <= int(port) <= 65535 and int(port)!=26028)
    add('F-16 control routing',valid_port,'Commands use configured listener port '+str(port)+'; dedicated F-16 feedback uses loopback 26028.' if valid_port else 'Set a numeric ListenerPort (1–65535) other than 26028, which is reserved for F-16 feedback.')
    return {'checks': rows, 'ready': all(row['ok'] for row in rows), 'warnings': warnings,'command_port':int(port) if valid_port else None,
            'limit': 'Checks verify installed files and recognized configuration only. Confirm live switch feedback in a running F-16 cockpit; plugin activation, firewall and actual traffic are not tested.'}

def describe(report, links=False):
    lines = [('PASS' if row['ok'] else 'MISSING')+' — '+row['name']+': '+row['detail'] for row in report['checks']]
    lines += ['CHECK — '+warning for warning in report['warnings']]
    lines.append(report['limit'])
    if links: lines += [name+': '+url for name, url in LINKS.items()]
    return '\n'.join(lines)

def require(vsd_root, dcs_root):
    report = check(vsd_root, dcs_root)
    if not report['ready']:
        raise ValueError('DCS prerequisites need attention. No installation changes have been made.\n\n'+describe(report, links=True))
    print('DCS prerequisite files/configuration checked.\n'+describe(report))
    return report
