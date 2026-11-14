"""Editable pre-installation shortcut review."""
import csv,json,pathlib,tkinter as tk
from tkinter import ttk,filedialog,messagebox
import binding_review as bindings

class BindingEditor(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent);self.host=parent;self.title('Review and edit panel shortcuts');self.geometry('1100x760');self.minsize(850,620)
        self.report=None;self.selected=None
        ttk.Label(self,text='Edits update the simulator bindings and matching panel controls together when you Apply.',padding=12).pack(anchor='w')
        bar=ttk.Frame(self,padding=(12,0));bar.pack(fill='x')
        self.search=tk.StringVar();self.only_conflicts=tk.BooleanVar()
        ttk.Label(bar,text='Find').pack(side='left');ttk.Entry(bar,textvariable=self.search,width=40).pack(side='left',padx=8)
        ttk.Checkbutton(bar,text='Conflicts only',variable=self.only_conflicts,command=self.render).pack(side='left');ttk.Button(bar,text='Recheck files',command=self.recheck).pack(side='right')
        self.summary=tk.StringVar();ttk.Label(self,textvariable=self.summary,wraplength=1030,padding=12).pack(fill='x')
        grid=ttk.Frame(self,padding=(12,0));grid.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(grid,columns=('sim','function','key','status'),show='headings',selectmode='browse')
        for name,title,width in [('sim','Simulator',70),('function','Panel function',560),('key','Proposed shortcut',240),('status','Status',120)]:self.tree.heading(name,text=title);self.tree.column(name,width=width,minwidth=60,stretch=name=='function')
        scroll=ttk.Scrollbar(grid,orient='vertical',command=self.tree.yview);self.tree.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');self.tree.pack(fill='both',expand=True)
        self.tree.tag_configure('Conflict',foreground='#b62027');self.tree.tag_configure('Not checked',foreground='#9a5d00');self.tree.bind('<<TreeviewSelect>>',self.select)
        editor=ttk.LabelFrame(self,text='Edit selected function',padding=10);editor.pack(fill='x',padx=12,pady=10)
        self.key=tk.StringVar();ttk.Combobox(editor,textvariable=self.key,values=list(bindings.NAME_SCAN),state='readonly',width=12).grid(row=0,column=0,padx=(0,10))
        self.mods={m:tk.BooleanVar() for m in bindings.MODS[:6]}
        for i,(name,var) in enumerate(self.mods.items()):ttk.Checkbutton(editor,text=name,variable=var).grid(row=0,column=i+1)
        ttk.Button(editor,text='Use shortcut',command=self.commit).grid(row=1,column=0,columnspan=2,sticky='w',pady=(8,0));ttk.Button(editor,text='Reset selected',command=self.reset).grid(row=1,column=2,columnspan=2,pady=(8,0))
        self.detail=tk.Text(self,height=6,wrap='word',font=('Segoe UI',9));self.detail.pack(fill='x',padx=12);self.detail.configure(state='disabled')
        footer=ttk.Frame(self,padding=12);footer.pack(fill='x')
        for title,cmd in [('Save mapping…',self.save),('Load mapping…',self.load),('Export report…',self.export),('Files checked…',self.files)]:ttk.Button(footer,text=title,command=cmd).pack(side='left',padx=(0,6))
        ttk.Button(footer,text='Close',command=self.destroy).pack(side='right')
        self.search.trace_add('write',lambda *_:self.render());self.recheck()
    def write_detail(self,text):
        self.detail.configure(state='normal');self.detail.delete('1.0','end');self.detail.insert('end',text);self.detail.configure(state='disabled')
    def recheck(self):
        try:
            args=self.host.args();self.report=bindings.audit(self.host.payload,args)
            conflicts=sum(r['status']=='Conflict' for r in self.report['rows']);errors=self.report['errors']
            self.summary.set(f"{len(self.report['rows'])} shortcuts • {conflicts} conflicts • {len(self.report['files'])} files checked"+(' • Scan incomplete: '+ '; '.join(errors) if errors else '\nWindows-wide shortcuts and other applications are outside this scan.'))
            self.render()
            if errors:self.write_detail('\n'.join(errors))
        except Exception as e:self.summary.set('Review needs attention: '+str(e))
    def render(self):
        if not self.report:return
        selected=self.selected;self.tree.delete(*self.tree.get_children());needle=self.search.get().lower()
        for row in self.report['rows']:
            if self.only_conflicts.get() and row['status'] not in ['Conflict','Not checked']:continue
            text=' '.join([row['sim'],row['name'],bindings.label(row['key'],row['mods']),*row['owners']])
            if needle not in text.lower():continue
            self.tree.insert('',tk.END,iid=row['id'],values=(row['sim'],row['name'],bindings.label(row['key'],row['mods']),row['status']),tags=(row['status'],))
        if selected and self.tree.exists(selected):self.tree.selection_set(selected);self.tree.see(selected)
    def select(self,event=None):
        ids=self.tree.selection()
        if not ids:return
        self.selected=ids[0];row=next(r for r in self.report['rows'] if r['id']==self.selected)
        self.key.set(row['key'])
        for name,var in self.mods.items():var.set(name in row['mods'])
        self.write_detail(row['name']+'\n'+row['command']+'\n'+row['status']+('\nExisting / conflicting assignments:\n'+'\n'.join(row['owners']) if row['owners'] else '\nNo conflicting assignment found in the checked files.'))
    def commit(self):
        if not self.selected:return
        row=next(r for r in self.report['rows'] if r['id']==self.selected);mods=[m for m,v in self.mods.items() if v.get()]
        try:
            bindings.validate_edit(row,self.key.get(),mods)
            if not self.host.profiles.get() or not self.host.bindings.get():raise ValueError('Enable both profiles and simulator bindings before editing shortcuts, so both sides stay synchronized.')
            self.host.binding_overrides[self.selected]={'key':self.key.get(),'mods':mods};self.host.invalidate();self.recheck()
        except ValueError as e:messagebox.showerror('Shortcut',str(e),parent=self)
    def reset(self):
        if self.selected:self.host.binding_overrides.pop(self.selected,None);self.host.invalidate();self.recheck()
    def save(self):
        p=filedialog.asksaveasfilename(parent=self,title='Save edited shortcut map',defaultextension='.json',filetypes=[('Shortcut map','*.json')])
        if p:pathlib.Path(p).write_text(json.dumps(self.host.binding_overrides,indent=2))
    def load(self):
        p=filedialog.askopenfilename(parent=self,filetypes=[('Shortcut map','*.json')])
        if not p:return
        try:
            data=json.loads(pathlib.Path(p).read_text());bindings.proposals(self.host.payload,data)
            if not self.host.profiles.get() or not self.host.bindings.get():raise ValueError('Enable both profiles and bindings before loading a shortcut map.')
            self.host.binding_overrides=data;self.host.invalidate();self.recheck()
        except Exception as e:messagebox.showerror('Shortcut map',str(e),parent=self)
    def export(self):
        if not self.report:return
        p=filedialog.asksaveasfilename(parent=self,title='Save binding review report',defaultextension='.csv',filetypes=[('CSV report','*.csv')])
        if p:
            with pathlib.Path(p).open('w',newline='',encoding='utf-8-sig') as f:
                w=csv.writer(f);w.writerow(['Simulator','Function','Shortcut','Status','Existing assignments'])
                for r in self.report['rows']:w.writerow([r['sim'],r['name'],bindings.label(r['key'],r['mods']),r['status'],'; '.join(r['owners'])])
    def files(self):
        if self.report:messagebox.showinfo('Files checked','\n'.join(self.report['files'])+'\n\n'+ '\n'.join(self.report['errors']),parent=self)
