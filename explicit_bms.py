"""Migrate the five BMS ECM buttons from toggle callbacks to explicit positions."""
import argparse, copy, csv, io, json, pathlib
import binding_review as br
from graphics import tile
from regenerate_graphics import save_image

WORK = pathlib.Path(__file__).resolve().parent
PAYLOAD = WORK / 'payload'
PLUGIN = PAYLOAD / 'org.f16vsd.cycling.sdPlugin'


def migrate(keyfiles=()):
    catalog = json.loads((PLUGIN / 'controls.json').read_text())
    bindings = json.loads((PAYLOAD / 'bindings/BMS-keyboard-bindings.json').read_text())
    occupied = {(b['scan_code'], b['modifier_mask']) for b in bindings}
    for path in keyfiles:
        for line in pathlib.Path(path).read_text(encoding='utf-8-sig').splitlines():
            parts = line.split()
            if len(parts) > 8:
                try: occupied.add((int(parts[3], 16), int(parts[4])))
                except ValueError: pass
    available = iter((scan, mask) for mask in [7, 6, 5, 3, 4, 2, 1]
                     for scan in sorted(br.SCAN_VK) if scan not in (1, 14, 15, 28, 57)
                     and (scan, mask) not in occupied)
    for i in range(1, 6):
        ident = f'ecm{i}'
        if ident in catalog: continue
        callbacks = [f'SimEcmMode{i}Off', f'SimEcmMode{i}On']
        new = []
        for state, callback in zip(['OFF', 'ON'], callbacks):
            scan, mask = next(available)
            new.append(dict(callback=callback, scan_code=scan, modifier_mask=mask,
                            description=f'ECM: Mode {i} - {state}'))
        c = dict(id=ident, label=f'ECM {i}', states=['OFF', 'ON'], callbacks=callbacks,
                 group='ECM', kind='toggle', initial=0, values=[0, 1], arg=-1,
                 dcs={}, bindings=new, simulators=['BMS'])
        c['images'] = ['images/' + save_image(tile(c['label'], state, index=j), PLUGIN / 'images')
                       for j, state in enumerate(c['states'])]
        c['offline'] = 'images/' + save_image(tile(c['label'], 'NO DATA', offline=True), PLUGIN / 'images')
        catalog[ident] = c
        bindings = [b for b in bindings if b['callback'] != f'SimEcmMode{i}Toggle'] + new
    (PLUGIN / 'controls.json').write_text(json.dumps(catalog, indent=2))
    (PAYLOAD / 'bindings/BMS-keyboard-bindings.json').write_text(json.dumps(bindings, indent=2))
    path = PAYLOAD / 'controls.csv'
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding='utf-8-sig'))))
    profiles = json.loads((PAYLOAD / 'profiles.json').read_text())
    count = 0
    for p in profiles:
        if p['sim'] != 'BMS': continue
        root = PAYLOAD / 'profiles' / p['folder']
        base = json.loads((root / 'manifest.json').read_text())
        for pi, page in enumerate(base['Pages']['Pages']):
            folder = root if pi == 0 else root / 'profiles' / page
            path = folder / 'manifest.json'
            data = json.loads(path.read_text())
            for row in rows:
                if (row['sim'], row['device'], row['page'], row['trigger']) != ('BMS', p['device'], p['page_titles'][pi], 'key'): continue
                if row['control'] not in [f'ECM {i}' for i in range(1, 6)]: continue
                ident = 'ecm' + row['control'].split()[-1]
                c = catalog[ident]
                a = data['Actions'][row['coordinate']]
                a.update(Name='F-16 selector', UUID='org.f16vsd.cycling.selector', State=0,
                         Settings=dict(sim='BMS', control=ident, index=0), SoftwareSettings={})
                a['States'] = [dict(Image=pathlib.Path(c['images'][0]).name, Title='', ShowTitle=False)]
                (folder / 'Images' / a['States'][0]['Image']).write_bytes((PLUGIN / c['images'][0]).read_bytes())
                row.update(positions='OFF → ON → OFF', BMS_callbacks=' / '.join(c['callbacks']))
                count += 1
            path.write_text(json.dumps(data, indent=2), encoding='utf-8')
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    (PAYLOAD / 'controls.csv').write_text(output.getvalue(), encoding='utf-8')
    print(json.dumps(dict(explicit_selectors=len(catalog), ecm_buttons=count, toggle_callbacks_remaining=[b['callback'] for b in bindings if 'Toggle' in b['callback']]), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--keyfiles', nargs='*', type=pathlib.Path, default=[])
    migrate(parser.parse_args().keyfiles)
