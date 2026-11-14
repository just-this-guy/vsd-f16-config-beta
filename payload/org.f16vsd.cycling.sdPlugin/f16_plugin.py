"""F-16 VSD cycling controls. DCS uses sampled feedback; BMS uses local state."""
import argparse, base64, ctypes, json, logging, math, os, pathlib, socket, sys, time
from transport import WebSocket

BASE = pathlib.Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent


def send_chord(binding):
    """Send a complete scan-code chord without stealing focus or releasing held modifiers."""
    from ctypes import wintypes as w
    user = ctypes.WinDLL('user32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    user.GetForegroundWindow.restype = w.HWND
    user.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
    user.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user.GetAsyncKeyState.restype = ctypes.c_short
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    pid = w.DWORD()
    user.GetWindowThreadProcessId(user.GetForegroundWindow(), ctypes.byref(pid))
    handle = kernel.OpenProcess(0x1000, False, pid.value)
    if not handle:
        raise RuntimeError('BMS must have keyboard focus')
    try:
        name = ctypes.create_unicode_buffer(32768); length = w.DWORD(32768)
        if not kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(length)) or pathlib.Path(name.value).name.lower() != 'falcon bms.exe':
            raise RuntimeError('BMS must have keyboard focus')
    finally:
        kernel.CloseHandle(handle)
    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [('wVk', w.WORD), ('wScan', w.WORD), ('dwFlags', w.DWORD), ('time', w.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [('dx', w.LONG), ('dy', w.LONG), ('mouseData', w.DWORD), ('dwFlags', w.DWORD), ('time', w.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
    class UNION(ctypes.Union):
        _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT)]
    class INPUT(ctypes.Structure):
        _fields_ = [('type', w.DWORD), ('u', UNION)]
    events = []; pressed = []
    def key(scan, up=False):
        events.append(INPUT(1, UNION(ki=KEYBDINPUT(0, scan, 8 | (2 if up else 0), 0, 0))))
    mask = binding['modifier_mask']
    # Refuse an extra physical modifier, which would select a different BMS callback.
    for bit, scan, vkeys in [(2, 0x1d, (0xa2, 0xa3)), (4, 0x38, (0xa4, 0xa5)), (1, 0x2a, (0xa0, 0xa1))]:
        held = any(user.GetAsyncKeyState(vk) & 0x8000 for vk in vkeys)
        if held and not mask & bit:
            raise RuntimeError('Release extra keyboard modifiers first')
        if mask & bit and not held:
            key(scan); pressed.append(scan)
    key(binding['scan_code']); key(binding['scan_code'], True)
    for scan in reversed(pressed): key(scan, True)
    array = (INPUT * len(events))(*events)
    user.SendInput.argtypes = [w.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    sent = user.SendInput(len(events), array, ctypes.sizeof(INPUT))
    if sent != len(events):
        # Release only keys injected here, including the main key, on a partial send.
        releases = [INPUT(1, UNION(ki=KEYBDINPUT(0, scan, 10, 0, 0))) for scan in [binding['scan_code'], *reversed(pressed)]]
        user.SendInput(len(releases), (INPUT * len(releases))(*releases), ctypes.sizeof(INPUT))
        raise OSError('BMS keyboard injection failed')


class Plugin:
    def __init__(self, ws, controls, udp=None, inject=send_chord, clock=time.monotonic, command_port=26027):
        self.ws, self.controls, self.udp, self.inject, self.clock = ws, controls, udp, inject, clock
        self.contexts = {}; self.local = {}; self.feedback = {}; self.stamp = -1e9
        self.pending = {}; self.last = {}; self.images = {}; self.down = set(); self.model_time = None
        self.command_port = command_port

    def emit(self, event, context, payload=None):
        msg = {'event': event, 'context': context}
        if payload is not None: msg['payload'] = payload
        self.ws.send(msg)

    def ingest(self, packet):
        parts = packet.decode('ascii').strip().split('|')
        if len(parts) < 3 or parts[0] != 'F16': return
        model_time = float(parts[1])
        values = {int(k): float(v) for k, v in (p.split('=', 1) for p in parts[2:])}
        if not all(math.isfinite(v) for v in values.values()) or not math.isfinite(model_time): return
        if self.model_time is not None and model_time < self.model_time:
            self.pending.clear()
        self.model_time = model_time; self.feedback = values; self.stamp = self.clock()

    def current(self, sim, c):
        ident = c['id']
        if sim not in c.get('simulators', ['BMS', 'DCS']): return None
        if sim == 'BMS': return self.local.get(ident, c['initial'])
        if self.clock() - self.stamp > 1.5: return None
        value = self.feedback.get(c['arg'])
        if value is None: return None
        index = min(range(len(c['values'])), key=lambda i: abs(c['values'][i] - value))
        if abs(c['values'][index] - value) > .035: return None
        return index

    def activate(self, context):
        s = self.contexts.get(context, {}); c = self.controls.get(s.get('control'))
        if not c: return
        sim = s['sim']; index = self.current(sim, c)
        if index is None:
            self.emit('showAlert', context); return
        key = (sim, c['id'])
        pending = self.pending.get(key)
        if pending and pending[1] > self.clock(): index = pending[0]
        target = (index + 1) % len(c['states'])
        try:
            if sim == 'DCS':
                d = c['dcs']
                self.udp.sendto(f"C{d['device']},{d['command']},{c['values'][target]:g}\n".encode(), ('127.0.0.1', self.command_port))
                self.pending[key] = (target, self.clock() + .75)
            else:
                self.inject(c['bindings'][target]); self.local[c['id']] = target
                for ctx, settings in self.contexts.items():
                    if settings.get('sim') == 'BMS' and settings.get('control') == c['id']:
                        settings['index'] = target; self.emit('setSettings', ctx, dict(settings))
        except (OSError, RuntimeError):
            logging.exception('Control command failed'); self.emit('showAlert', context)

    def receive(self, message):
        event = message.get('event'); context = message.get('context'); p = message.get('payload', {})
        if event in ('willAppear', 'didReceiveSettings'):
            s = p.get('settings', {}); self.contexts[context] = s; self.last.pop(context, None)
            c = self.controls.get(s.get('control'))
            if c and s.get('sim') == 'BMS':
                index = s.get('index', c['initial'])
                if not isinstance(index, int) or not 0 <= index < len(c['states']): index = c['initial']
                self.local.setdefault(c['id'], index)
        elif event == 'willDisappear':
            self.contexts.pop(context, None); self.last.pop(context, None); self.down.discard(context)
        elif event == 'keyDown' and context not in self.down:
            self.down.add(context); self.activate(context)
        elif event == 'keyUp': self.down.discard(context)

    def refresh(self):
        for context, settings in list(self.contexts.items()):
            c = self.controls.get(settings.get('control'))
            if not c: continue
            index = self.current(settings['sim'], c)
            # DCS graphic changes only when confirmed by cockpit telemetry.
            name = c['offline'] if index is None else c['images'][index]
            if self.last.get(context) == name: continue
            if name not in self.images:
                path = (BASE / name).resolve()
                if not path.is_relative_to(BASE): raise ValueError('Image outside plugin')
                self.images[name] = 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode()
            self.emit('setImage', context, {'target': 0, 'image': self.images[name]})
            self.last[context] = name


def main():
    if '--self-check' in sys.argv:
        controls = json.loads((BASE / 'controls.json').read_text())
        for c in controls.values():
            assert len(c['states']) == len(c['values']) == len(c['bindings']) == len(c['images'])
            for name in [*c['images'], c['offline']]: assert (BASE / name).is_file()
        pathlib.Path(sys.argv[sys.argv.index('--self-check') + 1]).write_text(json.dumps({'status': 'ok', 'controls': len(controls)})); return
    parser = argparse.ArgumentParser()
    parser.add_argument('-port', type=int, required=True); parser.add_argument('-pluginUUID', required=True)
    parser.add_argument('-registerEvent', required=True); parser.add_argument('-info', default='{}')
    args = parser.parse_args()
    logging.basicConfig(filename=str(BASE / 'plugin.log'), level=logging.INFO)
    config_path=BASE/'runtime-settings.json'
    config=json.loads(config_path.read_text()) if config_path.exists() else {}
    command_port=int(config.get('command_port',26027))
    if not 1 <= command_port <= 65535 or command_port==26028:raise ValueError('Invalid DCS command port')
    ws = WebSocket(args.port); ws.send({'event': args.registerEvent, 'uuid': args.pluginUUID})
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Exclusive binding: do not share/drop telemetry with another process.
    udp.bind(('127.0.0.1', 26028)); udp.setblocking(False)
    plugin = Plugin(ws, json.loads((BASE / 'controls.json').read_text()), udp, command_port=command_port)
    while True:
        for message in ws.receive(.03): plugin.receive(message)
        for _ in range(100):
            try: packet, peer = udp.recvfrom(65536)
            except BlockingIOError: break
            if peer[0] != '127.0.0.1': continue
            try: plugin.ingest(packet)
            except (ValueError, UnicodeError): logging.warning('Ignored malformed telemetry')
        plugin.refresh()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Windowed PyInstaller programs otherwise leave an error dialog and orphan process.
        logging.exception('F-16 cycling runtime stopped')
        sys.exit(1)
