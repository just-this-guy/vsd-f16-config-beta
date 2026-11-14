import json,pathlib,sys,unittest
WORK=pathlib.Path(__file__).resolve().parent
RUNTIME=WORK/"payload/org.f16vsd.cycling.sdPlugin"
sys.path.insert(0,str(RUNTIME))
import f16_plugin as runtime

class FakeWS:
    def __init__(self): self.messages=[]
    def send(self,msg): self.messages.append(msg)

class FakeUDP:
    def __init__(self): self.sent=[]
    def sendto(self,data,peer): self.sent.append((data,peer))

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.controls=json.loads((RUNTIME/'controls.json').read_text())
        self.ws=FakeWS();self.udp=FakeUDP();self.keys=[];self.now=100
        self.p=runtime.Plugin(self.ws,self.controls,self.udp,self.keys.append,lambda:self.now)
    def appear(self,id='main',sim='BMS',context='a',index=None):
        s={'sim':sim,'control':id}
        if index is not None:s['index']=index
        self.p.receive({'event':'willAppear','context':context,'payload':{'settings':s}})
    def press(self,context='a'):
        self.p.receive({'event':'keyDown','context':context});self.p.receive({'event':'keyUp','context':context})
    def test_every_control_wraps_at_last_state(self):
        for id,c in self.controls.items():
            self.appear(id,index=len(c['states'])-1);self.press()
            self.assertEqual(self.p.local[id],0)
            self.assertEqual(self.keys[-1]['callback'],c['callbacks'][0])
    def test_two_state_toggle(self):
        self.appear('fuel',index=0);self.press();self.assertEqual(self.p.local['fuel'],1)
        self.press();self.assertEqual(self.p.local['fuel'],0)
    def test_three_state_cycle(self):
        self.appear('main',index=2)
        for target in [0,1,2,0]:self.press();self.assertEqual(self.p.local['main'],target)
    def test_eight_state_cycle(self):
        self.appear('anticoll',index=0)
        for target in [1,2,3,4,5,6,7,0]:self.press();self.assertEqual(self.p.local['anticoll'],target)
    def test_shared_visible_bms_state(self):
        self.appear('main',index=2);self.appear('main',context='b',index=0);self.press()
        self.assertEqual(self.p.contexts['b']['index'],0);self.press('b');self.assertEqual(self.p.local['main'],1)
    def test_repeat_keydown_does_not_skip_states(self):
        self.appear('main',index=2)
        for _ in range(5):self.p.receive({'event':'keyDown','context':'a'})
        self.assertEqual(len(self.keys),1)
    def test_bms_injection_failure_does_not_change_state(self):
        self.appear('main',index=2)
        def fail(binding):raise RuntimeError('No focus')
        self.p.inject=fail;self.press();self.assertEqual(self.p.local['main'],2)
        self.assertEqual(self.ws.messages[-1]['event'],'showAlert')
    def test_dcs_requires_current_f16_feedback(self):
        self.appear(sim='DCS');self.press();self.assertFalse(self.udp.sent)
        self.p.ingest(b'F16|1|510=-1');self.press()
        self.assertEqual(self.udp.sent[-1],(b'C3,3001,1\n',('127.0.0.1',26027)))
    def test_dcs_tracks_external_cockpit_change(self):
        self.appear(sim='DCS');self.p.ingest(b'F16|1|510=0');self.press()
        self.assertEqual(self.udp.sent[-1][0],b'C3,3001,-1\n')
    def test_dcs_graphic_waits_for_confirmed_feedback(self):
        self.appear(sim='DCS');self.p.ingest(b'F16|1|510=-1');self.press();self.p.refresh()
        self.assertEqual(self.p.last['a'],self.controls['main']['images'][2])
        self.p.ingest(b'F16|2|510=1');self.p.refresh()
        self.assertEqual(self.p.last['a'],self.controls['main']['images'][0])
    def test_dcs_rapid_repeated_presses_cycle(self):
        self.appear(sim='DCS');self.p.ingest(b'F16|1|510=-1')
        for _ in range(3):self.press()
        self.assertEqual([p[0] for p in self.udp.sent],[b'C3,3001,1\n',b'C3,3001,0\n',b'C3,3001,-1\n'])
    def test_dcs_stale_feedback_blocks_commands(self):
        self.appear(sim='DCS');self.p.ingest(b'F16|1|510=1');self.now+=2;self.press()
        self.assertFalse(self.udp.sent);self.p.refresh();self.assertEqual(self.p.last['a'],self.controls['main']['offline'])
    def test_unknown_selector_position_blocks_command(self):
        self.appear(sim='DCS');self.p.ingest(b'F16|1|510=0.5');self.press();self.assertFalse(self.udp.sent)
    def test_foreign_aircraft_packet_ignored(self):
        self.p.ingest(b'F18|1|510=1');self.assertFalse(self.p.feedback)
    def test_mission_restart_clears_pending_commands(self):
        self.appear(sim='DCS');self.p.ingest(b'F16|200|510=-1');self.press()
        self.p.ingest(b'F16|0|510=-1');self.assertFalse(self.p.pending)

class RoutingTests(unittest.TestCase):
    def test_configured_dcs_listener_port(self):
        controls=json.loads((RUNTIME/'controls.json').read_text());udp=FakeUDP();p=runtime.Plugin(FakeWS(),controls,udp,clock=lambda:100,command_port=26029)
        p.receive({'event':'willAppear','context':'a','payload':{'settings':{'sim':'DCS','control':'main'}}})
        p.ingest(b'F16|1|510=-1');p.activate('a')
        self.assertEqual(udp.sent[-1][1],('127.0.0.1',26029))

if __name__=="__main__":unittest.main()
