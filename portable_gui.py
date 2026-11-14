"""One-run portable profile setup. No self-installation or startup registration."""
import argparse,contextlib,ctypes,io,json,os,pathlib,queue,re,sys,threading,traceback,webbrowser
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
import share_installer as engine
import dcs_prerequisites as prerequisites
import binding_review
from binding_editor import BindingEditor

BASE=pathlib.Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else pathlib.Path(__file__).resolve().parent
PAYLOAD=pathlib.Path(getattr(sys,'_MEIPASS',BASE))/'payload'
if not PAYLOAD.exists():PAYLOAD=BASE/'payload'
engine.HERE=PAYLOAD

def usb_ids():
    if os.name!='nt':return ''
    from ctypes import wintypes as w
    dll=ctypes.WinDLL('setupapi');dll.SetupDiGetClassDevsW.restype=ctypes.c_void_p
    dll.SetupDiGetClassDevsW.argtypes=[ctypes.c_void_p,w.LPCWSTR,ctypes.c_void_p,w.DWORD]
    class INFO(ctypes.Structure):_fields_=[('size',w.DWORD),('guid',ctypes.c_byte*16),('inst',w.DWORD),('reserved',ctypes.c_size_t)]
    dll.SetupDiEnumDeviceInfo.argtypes=[ctypes.c_void_p,w.DWORD,ctypes.POINTER(INFO)]
    dll.SetupDiGetDeviceInstanceIdW.argtypes=[ctypes.c_void_p,ctypes.POINTER(INFO),w.LPWSTR,w.DWORD,ctypes.c_void_p]
    dll.SetupDiDestroyDeviceInfoList.argtypes=[ctypes.c_void_p]
    handle=dll.SetupDiGetClassDevsW(None,None,None,6);rows=[]
    if handle in [None,ctypes.c_void_p(-1).value]:return ''
    try:
        i=0
        while True:
            item=INFO();item.size=ctypes.sizeof(item)
            if not dll.SetupDiEnumDeviceInfo(handle,i,ctypes.byref(item)):break
            buf=ctypes.create_unicode_buffer(1024)
            if dll.SetupDiGetDeviceInstanceIdW(handle,ctypes.byref(item),buf,1024,None):rows.append(buf.value.upper())
            i+=1
    finally:dll.SetupDiDestroyDeviceInfoList(handle)
    return '\n'.join(rows)

def detect(root):
    config=pathlib.Path(root)/'config/StreamDockConfig.ini';text=config.read_text(encoding='utf-8-sig') if config.exists() else '';ids=usb_ids();result={}
    for model in ['VSDXL','VSDN4Pro']:
        found=re.search(r'(?m)^'+model+r'\\SerialNumber=([^\r\n]+)',text)
        serial=found[1].strip() if found else ''
        result[model]={'serial':serial,'connected':bool(serial and serial.upper() in ids)}
    return result

def defaults():
    app=pathlib.Path(os.environ.get('APPDATA',pathlib.Path.home()/'AppData/Roaming'))/'HotSpot/StreamDock'
    saved=pathlib.Path.home()/'Saved Games';dcs=next((saved/n for n in ['DCS','DCS.openbeta'] if (saved/n/'Config').exists()),saved/'DCS')
    bms=None
    for drive in ['C','D','E','F','G']:
        root=pathlib.Path(drive+':/')
        if root.exists():
            bms=next((p for p in sorted(root.glob('Falcon BMS */User/Config'),reverse=True) if (p/'BMS - Full.key').exists()),None)
            if bms:break
    return str(app),str(dcs),str(bms or pathlib.Path('C:/Falcon BMS 4.38/User/Config'))

class Wizard(tk.Tk):
    def __init__(self):
        super().__init__();self.title('VSD F16 Config Beta');self.geometry('930x820');self.minsize(800,650);self.configure(bg='#101820')
        style=ttk.Style(self);style.theme_use('clam');style.configure('.',font=('Segoe UI',10),background='#edf2f4',foreground='#14212a');style.configure('TButton',padding=8);style.configure('Title.TLabel',font=('Segoe UI',24,'bold'),background='#101820',foreground='#d6f3e3')
        top=ttk.Frame(self,style='TFrame');top.pack(fill='x');header=tk.Frame(top,bg='#101820');header.pack(fill='x');ttk.Label(header,text='VSD F16 Config Beta',style='Title.TLabel').pack(anchor='w',padx=25,pady=(18,3));tk.Label(header,text='VSD XL + N4 Pro  •  Single-button cycling controls  •  BMS and DCS',bg='#101820',fg='#a8c5b8',font=('Segoe UI',11)).pack(anchor='w',padx=27,pady=(0,16))
        viewport=ttk.Frame(self);viewport.pack(fill='both',expand=True);canvas=tk.Canvas(viewport,highlightthickness=0,bg='#edf2f4');scroll=ttk.Scrollbar(viewport,orient='vertical',command=canvas.yview);scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True);canvas.configure(yscrollcommand=scroll.set);body=ttk.Frame(canvas,padding=20);content=canvas.create_window((0,0),window=body,anchor='nw');body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')));canvas.bind('<Configure>',lambda e:canvas.itemconfigure(content,width=e.width));self.bind_all('<MouseWheel>',lambda e:canvas.yview_scroll(-int(e.delta/120),'units'))
        a,d,b=defaults();self.vsd=tk.StringVar(value=a);self.dcs=tk.StringVar(value=d);self.bms=tk.StringVar(value=b);self.backups=tk.StringVar(value=str(pathlib.Path.home()/'Documents/VSD F16 Config Beta/Backups'));self.sim=tk.StringVar(value='Both simulators');self.profiles=tk.BooleanVar(value=True);self.bindings=tk.BooleanVar(value=True);self.replace=tk.BooleanVar(value=True);self.paired=tk.BooleanVar(value=True);self.panels={x:tk.BooleanVar(value=True) for x in ['VSDXL','VSDN4Pro']};self.status={x:tk.StringVar(value='Checking…') for x in self.panels};self.events=queue.Queue();self.reviewed=None;self.last_backup=None
        self.payload=PAYLOAD;self.binding_overrides={};self.bms_keyfiles=None;self.dcs_install=tk.StringVar(value=binding_review.dcs_install_default());self.keyfile_status=tk.StringVar(value='BMS - Full.key and BMS - Auto.key (default selection)')
        paths=ttk.LabelFrame(body,text='1. Find your software',padding=10);paths.pack(fill='x')
        for row,(label,var) in enumerate([('VSD data folder',self.vsd),('DCS Saved Games folder',self.dcs),('DCS program folder',self.dcs_install),('BMS User / Config folder',self.bms),('Backup folder',self.backups)]):
            ttk.Label(paths,text=label).grid(row=row,column=0,sticky='w',padx=(0,10),pady=3);ttk.Entry(paths,textvariable=var).grid(row=row,column=1,sticky='ew');ttk.Button(paths,text='Browse…',command=lambda v=var:self.browse(v)).grid(row=row,column=2,padx=(8,0))
        paths.columnconfigure(1,weight=1)
        deps=ttk.LabelFrame(body,text='DCS requirements — installed separately',padding=10);deps.pack(fill='x',pady=(10,0))
        self.dependency_status=tk.StringVar(value='Checking installed files…')
        ttk.Label(deps,textvariable=self.dependency_status,wraplength=820).pack(anchor='w')
        links=ttk.Frame(deps);links.pack(fill='x',pady=(5,0))
        ttk.Button(links,text='Check requirements',command=self.check_requirements).pack(side='left')
        for label,key in [('Get VSD plugin','VSD plugin downloads'),('Get export scripts','DCS-ExportScripts download'),('Settings guide','DCS Interface settings guide')]:
            ttk.Button(links,text=label,command=lambda k=key:webbrowser.open(prerequisites.LINKS[k])).pack(side='left',padx=(6,0))
        panels=ttk.LabelFrame(body,text='2. Select panels and simulator',padding=10);panels.pack(fill='x',pady=10)
        for row,(model,label) in enumerate([('VSDXL','XL — 32 keys'),('VSDN4Pro','N4 Pro — keys + four knobs')]):
            ttk.Checkbutton(panels,text=label,variable=self.panels[model]).grid(row=row,column=0,sticky='w');ttk.Label(panels,textvariable=self.status[model]).grid(row=row,column=1,sticky='w',padx=20)
        ttk.Button(panels,text='Detect again',command=self.scan).grid(row=0,column=2,rowspan=2)
        ttk.Label(panels,text='Profiles for').grid(row=2,column=0,sticky='w',pady=(9,0));ttk.Combobox(panels,textvariable=self.sim,values=['Both simulators','DCS only','BMS only'],state='readonly',width=24).grid(row=2,column=1,sticky='w',padx=20,pady=(9,0))
        options=ttk.LabelFrame(body,text='3. Choose what to apply',padding=10);options.pack(fill='x')
        for text,var in [('Add the selected VSD profiles',self.profiles),('Apply the selected simulator key bindings',self.bindings),('Update matching F-16 profiles if already present',self.replace),('Link the logo toggles so either panel switches both — requires both simulators and panels',self.paired)]:ttk.Checkbutton(options,text=text,variable=var).pack(anchor='w',pady=2)
        keys=ttk.Frame(options);keys.pack(fill='x',pady=(5,0));ttk.Button(keys,text='Choose BMS keyfiles…',command=self.choose_keyfiles).pack(side='left');ttk.Label(keys,textvariable=self.keyfile_status,wraplength=590).pack(side='left',padx=8)
        ttk.Button(options,text='Review / edit shortcuts…',command=lambda:BindingEditor(self)).pack(anchor='w',pady=(8,0))
        self.note=tk.StringVar(value='Profiles and their control runtime install together. Close VSD Craft and the selected simulators before Apply.')
        ttk.Label(body,textvariable=self.note,wraplength=850).pack(fill='x',pady=(9,5))
        self.log=tk.Text(body,height=4,wrap='word',font=('Consolas',9),bg='#ffffff',fg='#14212a',state='disabled');self.log.pack(fill='both',expand=True,pady=5)
        buttons=ttk.Frame(self,padding=(20,8));buttons.pack(side='bottom',fill='x');self.review_button=ttk.Button(buttons,text='Review choices',command=self.review);self.review_button.pack(side='left');self.apply_button=ttk.Button(buttons,text='Apply changes',command=self.apply,state='disabled');self.apply_button.pack(side='left',padx=10);ttk.Button(buttons,text='Open backups',command=self.open_backups).pack(side='right');ttk.Button(buttons,text='Exit',command=self.destroy).pack(side='right',padx=8)
        ttk.Label(body,text='Runs once. Prerequisites stay separate; no automatic downloads or Windows startup tasks.',font=('Segoe UI',9)).pack(anchor='w',pady=(12,0))
        for var in [self.vsd,self.dcs,self.dcs_install,self.bms,self.backups,self.sim,self.profiles,self.bindings,self.replace,self.paired,*self.panels.values()]:var.trace_add('write',lambda *_:self.invalidate())
        self.bms.trace_add('write',lambda *_:self.reset_keyfiles())
        self.sim.trace_add('write',lambda *_:self.update_linking())
        for var in self.panels.values():var.trace_add('write',lambda *_:self.update_linking())
        self.after(100,self.scan);self.after(100,self.poll)
    def update_linking(self):
        if self.sim.get()!='Both simulators' or not all(v.get() for v in self.panels.values()):self.paired.set(False)
    def invalidate(self):
        self.reviewed=None
        if hasattr(self,'apply_button'):self.apply_button.configure(state='disabled')
        if hasattr(self,'dependency_status'):self.dependency_status.set('BMS only: DCS requirements are not needed.' if self.sim.get()=='BMS only' else 'Requirements need rechecking after a selection changes. Review choices checks them again before applying.')
    def check_requirements(self,show=True):
        try:
            if self.sim.get()=='BMS only':
                self.dependency_status.set('BMS only: DCS requirements are not needed.');return
            report=prerequisites.check(self.vsd.get(),self.dcs.get())
            missing=[row['name'] for row in report['checks'] if not row['ok']]
            self.dependency_status.set(('Missing / needs attention: '+', '.join(missing)) if missing else 'Required files and export configuration found. Live cockpit feedback still needs confirmation.'+(' Custom communication settings need review.' if report['warnings'] else ''))
            if show:self.write(prerequisites.describe(report,links=True))
        except Exception as error:self.dependency_status.set('Unable to verify: '+str(error))
    def browse(self,var):
        folder=filedialog.askdirectory(parent=self,initialdir=var.get() if pathlib.Path(var.get()).exists() else str(pathlib.Path.home()))
        if folder:var.set(folder)
    def reset_keyfiles(self):
        self.bms_keyfiles=None;self.keyfile_status.set('BMS - Full.key and BMS - Auto.key (default selection)')
    def choose_keyfiles(self):
        files=filedialog.askopenfilenames(parent=self,title='Select the BMS keyfile(s) you use; only selected files will be updated',initialdir=self.bms.get(),filetypes=[('BMS keyfiles','*.key')])
        if files:self.bms_keyfiles=list(files);self.keyfile_status.set('; '.join(pathlib.Path(p).name for p in files));self.invalidate()
    def write(self,text):
        self.log.configure(state='normal');self.log.delete('1.0','end');self.log.insert('end',text);self.log.configure(state='disabled')
    def scan(self):
        try:
            found=detect(self.vsd.get())
            for model,data in found.items():
                self.status[model].set('Connected' if data['connected'] else 'Saved in VSD; not detected over USB' if data['serial'] else 'Not registered in this VSD folder')
                if not data['serial']:self.panels[model].set(False)
            if not all(self.panels[x].get() for x in self.panels):self.paired.set(False)
        except Exception as error:self.write('Panel detection: '+str(error))
        self.check_requirements(show=False)
    def args(self):
        devices=[x for x,v in self.panels.items() if v.get()];sim={'Both simulators':'both','DCS only':'dcs','BMS only':'bms'}[self.sim.get()]
        if not self.profiles.get() and not self.bindings.get():raise ValueError('Choose profiles, key bindings, or both.')
        if self.profiles.get() and not devices:raise ValueError('Select at least one panel.')
        if self.profiles.get() and self.paired.get() and (len(devices)!=2 or sim!='both'):raise ValueError('Paired simulator toggles require both panels and both simulator profiles. Turn linking off for a single-panel or single-simulator setup.')
        if self.binding_overrides and (not self.profiles.get() or not self.bindings.get()):raise ValueError('Edited shortcuts require both profiles and simulator bindings to be enabled.')
        return argparse.Namespace(sim=sim,devices=devices,vsd_root=self.vsd.get() if self.profiles.get() else None,bms_config=self.bms.get() if self.bindings.get() and sim in ['bms','both'] else None,dcs_saved_games=self.dcs.get() if self.bindings.get() and sim in ['dcs','both'] else None,apply=False,replace_existing=self.replace.get(),paired=self.paired.get() and sim=='both',backup_dir=self.backups.get(),prerequisite_vsd_root=self.vsd.get(),prerequisite_dcs_root=self.dcs.get(),prerequisite_bms_root=self.bms.get(),dcs_install=self.dcs_install.get(),bms_keyfiles=self.bms_keyfiles,binding_overrides=json.loads(json.dumps(self.binding_overrides)))
    def review(self):
        self.invalidate();self.check_requirements(show=False)
        try:
            args=self.args();out=io.StringIO()
            with contextlib.redirect_stdout(out):engine.install(args)
            self.reviewed=args;self.write(out.getvalue()+'\nBackups: '+self.backups.get()+'\n\nBindings for affected functions may change. Unrelated keyboard and joystick/MFD assignments are retained.\nReady to apply these choices.');self.apply_button.configure(state='normal')
        except Exception as error:self.write(str(error));messagebox.showerror('Please check these choices',str(error),parent=self)
    def apply(self):
        if not self.reviewed:return
        backup=messagebox.askyesnocancel('Apply changes — create a backup?','Create a rollback backup before applying the reviewed changes?\n\nYes: back up changed files and profiles, then apply.\nNo: apply without creating a backup.\nCancel: make no changes.',parent=self)
        if backup is None:return
        args=self.reviewed;args.apply=True;args.create_backup=backup;self.apply_button.configure(state='disabled');self.review_button.configure(state='disabled');self.note.set('Applying reviewed choices…')
        def work():
            out=io.StringIO()
            try:
                with contextlib.redirect_stdout(out):backup=engine.install(args)
                self.events.put((True,out.getvalue(),backup))
            except Exception as error:self.events.put((False,out.getvalue()+'\n'+str(error),None))
        threading.Thread(target=work,daemon=True).start()
    def poll(self):
        try:
            ok,text,backup=self.events.get_nowait();self.write(text);self.last_backup=backup;self.review_button.configure(state='normal');self.invalidate();self.note.set('Finished. Open VSD Craft and select the matching F-16 profile on each panel.' if ok else 'Setup stopped. Review the message below; backups are retained if changes began.')
            (messagebox.showinfo if ok else messagebox.showerror)('Setup finished' if ok else 'Setup stopped',('Selected changes were applied.\n'+('Backups: '+str(backup) if backup else 'Backup skipped by your choice.')) if ok else text[-1800:],parent=self)
        except queue.Empty:pass
        self.after(100,self.poll)
    def open_backups(self):
        path=pathlib.Path(self.last_backup or self.backups.get())
        if path.exists():os.startfile(path)
        else:messagebox.showinfo('Backups','A backup folder will be created when changes are applied.',parent=self)

def main():
    if '--self-check' in sys.argv:
        target=pathlib.Path(sys.argv[sys.argv.index('--self-check')+1]);profiles=json.loads((PAYLOAD/'profiles.json').read_text());pages=0;selectors=0
        for p in profiles:
            root=PAYLOAD/'profiles'/p['folder'];m=json.loads((root/'manifest.json').read_text())
            for i,page in enumerate(m['Pages']['Pages']):
                folder=root if i==0 else root/'profiles'/page;data=json.loads((folder/'manifest.json').read_text());pages+=1
                for a in data['Actions'].values():
                    for state in a['States']:assert (folder/'Images'/state['Image']).is_file()
                    if a['UUID']=='org.f16vsd.cycling.selector':selectors+=1
        runtime=PAYLOAD/'org.f16vsd.cycling.sdPlugin';manifest=json.loads((runtime/'manifest.json').read_text())
        assert (runtime/manifest['CodePathWin']).is_file()
        controls=json.loads((runtime/'controls.json').read_text())
        for c in controls.values():
            for name in [*c['images'],c['offline']]:assert (runtime/name).is_file()
        binding_rows=len(binding_review.proposals(PAYLOAD))
        app=Wizard();app.withdraw();editor=BindingEditor(app);editor.withdraw();app.update_idletasks();assert editor.report and len(editor.report['rows'])==binding_rows
        editor.search.set('COMM');assert editor.tree.get_children();editor.search.set('');editor.destroy()
        for text,sim in [('BMS only','bms'),('DCS only','dcs'),('Both simulators','both')]:
            app.sim.set(text);assert app.args().sim==sim
            if sim!='both':assert not app.paired.get()
        app.destroy();target.write_text(json.dumps({'status':'ok','product':'VSD F16 Config Beta','profiles':len(profiles),'pages':pages,'selector_buttons':selectors,'cycling_controls':len(controls),'gui_initialized':True,'binding_editor_rows':binding_rows,'simulator_choices':['BMS','DCS','Both'],'bundled_python':getattr(sys,'frozen',False)},indent=2));return
    Wizard().mainloop()
if __name__=='__main__':
    try:main()
    except Exception as error:
        if '--self-check' in sys.argv:
            pathlib.Path(sys.argv[sys.argv.index('--self-check')+1]).write_text(json.dumps({'status':'error','error':traceback.format_exc()}));sys.exit(1)
        messagebox.showerror('VSD F16 Config Beta',str(error))
