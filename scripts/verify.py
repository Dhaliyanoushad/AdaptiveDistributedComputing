"""Run every automated suite/check and retain actual logs in ignored outputs/."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]


def console_text(text):
    encoding=sys.stdout.encoding or 'utf-8'
    return text.encode(encoding,errors='backslashreplace').decode(encoding)


def stages():
    master=str(ROOT/'master/.venv/Scripts/python.exe')
    worker=str(ROOT/'worker/.venv/Scripts/python.exe')
    npm=['cmd.exe','/d','/c','npm.cmd']
    return [('master',[master,'tests/run_master_tests.py'],ROOT),
            ('worker',[worker,'-m','unittest','discover','-s','tests','-p','test_worker*.py','-q'],ROOT),
            ('benchmark',[worker,'-m','unittest','discover','-s','tests','-p','test_benchmarks.py','-q'],ROOT),
            ('integration_setup',[master,'-m','unittest','discover','-s','tests','-p','test_integration_setup.py','-v'],ROOT),
            ('frontend',npm+['test'],ROOT/'frontend'),('build',npm+['run','build'],ROOT/'frontend'),
            ('master_dependencies',[master,'-m','pip','check'],ROOT),('worker_dependencies',[worker,'-m','pip','check'],ROOT),
            ('master_config',[master,'scripts/launch.py','master','--check'],ROOT),
            ('worker_config',[worker,'scripts/launch.py','worker','--check'],ROOT),
            ('frontend_config',[master,'scripts/launch.py','frontend','--check'],ROOT)]


def main():
    directory=ROOT/'outputs/verification'/str(uuid4())
    directory.mkdir(parents=True,exist_ok=False)
    results=[]
    for name,command,cwd in stages():
        print(f'Running {name}...',flush=True)
        try:
            result=subprocess.run(command,cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300)
            text=result.stdout+result.stderr
            code=result.returncode
        except (OSError,subprocess.TimeoutExpired) as exc:
            text=f'CHECK BLOCKED: {exc}'
            code=1
        (directory/f'{name}.log').write_text(text,encoding='utf-8')
        match=re.search(r'Ran (\d+) tests?',text)
        if name=='frontend':match=re.search(r'Tests\s+(\d+) passed',text)
        count=int(match.group(1)) if match else None
        results.append({'stage':name,'exit_code':code,'test_count':count,'log':f'{name}.log'})
        (directory/'results.json').write_text(json.dumps({'complete':False,'stages':results,'all_passed':False},indent=2),encoding='utf-8')
        print(console_text(text[-2500:]),flush=True)
    report={'complete':True,'finished_at':datetime.now(timezone.utc).isoformat(),'stages':results,
            'all_passed':all(item['exit_code']==0 for item in results)}
    (directory/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(console_text(f'Verification evidence: {directory}'))
    return 0 if report['all_passed'] else 1


if __name__=='__main__':raise SystemExit(main())
