"""Build the standalone control runtime and shareable VSD F16 Config Beta wizard."""
import argparse,json,pathlib,shutil,subprocess

WORK=pathlib.Path(__file__).resolve().parent

def build(python):
    out=WORK/'dist';out.mkdir(exist_ok=True);plugin=WORK/'payload/org.f16vsd.cycling.sdPlugin'
    shutil.copy2(WORK/'f16_plugin.py',plugin/'f16_plugin.py')
    def freeze(entry,name,dest,extra=()):
        command=[str(python),'-m','PyInstaller','--noconfirm','--onefile','--windowed','--name',name,'--distpath',str(dest),'--workpath',str(WORK/'build'), '--specpath',str(WORK),*extra,str(entry)]
        log=out/(name+'-build.log')
        with log.open('w') as stream:subprocess.run(command,cwd=WORK,stdout=stream,stderr=subprocess.STDOUT,check=True)
        print('Built',name,flush=True)
    freeze(plugin/'f16_plugin.py','VSD F16 Controls',plugin)
    freeze(WORK/'portable_gui.py','VSD F16 Config Beta',out,['--add-data',str(WORK/'payload')+';payload'])
    print(out/'VSD F16 Config Beta.exe',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--python',type=pathlib.Path,required=True);build(parser.parse_args().python)
