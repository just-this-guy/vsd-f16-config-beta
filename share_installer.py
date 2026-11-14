"""Portable local installer. Dry run unless --apply is supplied. Python 3.9+."""
import argparse,ast,copy,csv,datetime,json,os,pathlib,re,shutil,sqlite3,subprocess,sys
import dcs_prerequisites
import binding_review
HERE=pathlib.Path(__file__).resolve().parent

def lua_load(text):
    # Accept only literal tables produced by DCS. Never execute Lua.
    text=re.sub(r'--\[\[.*?\]\]','',text,flags=re.S)
    text=re.sub(r'--[^\n]*','',text)
    text=text[text.index('{'):]
    tokens=re.findall(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[{}\[\]=,;]|[A-Za-z_]\w*',text)
    i=0
    def value():
        nonlocal i
        token=tokens[i];i+=1
        if token=='{':
            result={};index=1
            while tokens[i]!='}':
                if tokens[i]=='[':
                    i+=1;key=value();assert tokens[i]==']';i+=1;assert tokens[i]=='=';i+=1
                    result[key]=value()
                elif re.match(r'^[A-Za-z_]\w*$',tokens[i]) and tokens[i+1]=='=':
                    key=tokens[i];i+=2;result[key]=value()
                else:result[index]=value();index+=1
                if tokens[i] in [',',';']:i+=1
            i+=1;return result
        if token.startswith(('"',"'")):return ast.literal_eval(token)
        if token=='true':return True
        if token=='false':return False
        if token=='nil':return None
        if re.fullmatch(r'-?\d+',token):return int(token)
        if re.fullmatch(r'-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?',token):return float(token)
        raise ValueError('Non-literal Lua value: '+token)
    return value()

def lua_dump(value,depth=0):
    pad='\t'*depth
    if isinstance(value,dict):
        rows=[]
        for key,v in value.items():
            k=str(key) if isinstance(key,int) else json.dumps(key,ensure_ascii=False)
            rows.append(pad+'\t['+k+'] = '+lua_dump(v,depth+1)+',\n')
        return '{\n'+''.join(rows)+pad+'}'
    if value is None:return 'nil'
    return json.dumps(value,ensure_ascii=False)

def merge_dcs(existing,addition):
    data=lua_load(existing) if existing else {}
    new=lua_load(addition)
    diffs=data.setdefault('keyDiffs',{})
    for command,entry in new['keyDiffs'].items():
        for other_id,other in diffs.items():
            if other_id==command:continue
            for combo in entry['added'].values():
                if any(binding_review.combo(combo)==binding_review.combo(c) for c in other.get('added',{}).values()):raise ValueError('DCS shortcut conflict with '+other.get('name',other_id))
        target=diffs.setdefault(command,{'name':entry['name']})
        added=target.setdefault('added',{})
        for combo in entry['added'].values():
            if combo not in added.values():added[max([0]+list(added))+1]=combo
            removed=target.get('removed',{})
            target['removed']={k:v for k,v in removed.items() if v!=combo}
            if not target['removed']:target.pop('removed',None)
    return 'local diff = '+lua_dump(data)+'\nreturn diff\n'

def patch_bms(text,bindings):
    requested={b['callback']:b for b in bindings};lines=text.splitlines();existing={};present=set()
    for line in lines:
        a=line.split()
        if len(a)>8 and re.fullmatch(r'0[xX][0-9A-Fa-f]+',a[3]):
            scan=int(a[3],16);mod=int(a[4]);existing.setdefault((scan,mod),set()).add(a[0]);present.add(a[0])
    errors=[]
    for b in bindings:
        cb=b['callback'];others=existing.get((b['scan_code'],b['modifier_mask']),set())-{cb}
        others={x for x in others if x not in requested or (requested[x]['scan_code'],requested[x]['modifier_mask'])==(b['scan_code'],b['modifier_mask'])}
        if others:errors.append(cb+' conflicts with '+', '.join(sorted(others)))
        if cb not in present:errors.append('Callback not found in this keyfile: '+cb)
    if errors:raise ValueError('\n'.join(errors))
    result=[]
    for line in lines:
        a=line.split()
        if a and a[0] in requested and len(a)>8 and re.fullmatch(r'0[xX][0-9A-Fa-f]+',a[3]):
            b=requested[a[0]];line=re.sub(r'0[xX][0-9A-Fa-f]+\s+\d+',f"0X{b['scan_code']:X} {b['modifier_mask']}",line,count=1)
        result.append(line)
    return '\n'.join(result)+'\n'


def install(args):
    from beta_install import install as install_beta
    return install_beta(args)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sim',choices=['bms','dcs','both'],default='both')
    parser.add_argument('--vsd-root',help=r'Usually %APPDATA%\HotSpot\StreamDock')
    parser.add_argument('--bms-config',help=r'BMS User\Config directory')
    parser.add_argument('--dcs-saved-games',help=r'Saved Games\DCS directory')
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--dcs-install',help='DCS program folder, for scanning factory shortcuts')
    parser.add_argument('--bms-keyfiles',nargs='+',help='Selected BMS .key files to check and update')
    parser.add_argument('--binding-map',help='Edited binding map saved by the portable GUI')
    parser.add_argument('--no-backup',dest='create_backup',action='store_false',help='Explicitly skip rollback backup')
    args=parser.parse_args()
    if args.binding_map:args.binding_overrides=json.loads(pathlib.Path(args.binding_map).read_text())
    try:install(args)
    except (ValueError,AssertionError,sqlite3.Error,OSError) as error:parser.exit(1,str(error)+'\n')
if __name__=='__main__':main()
