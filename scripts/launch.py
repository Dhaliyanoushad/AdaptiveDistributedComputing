"""Safe component launcher: inert .env parsing, explicit arguments, no shell eval."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path, inherited: dict) -> dict:
    environment = dict(inherited)
    if not path.exists():
        return environment
    for number,line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
        line=line.strip()
        if not line or line.startswith('#'):continue
        key,separator,value=line.partition('=')
        if not separator or not re.fullmatch(r'[A-Z][A-Z0-9_]*',key):
            raise ValueError(f'Invalid configuration key on line {number}')
        value=value.strip()
        if value.startswith(('"',"'")):
            if len(value)<2 or value[-1]!=value[0]:raise ValueError(f'Unclosed quote on line {number}')
            value=value[1:-1]
        # Values are data: no evaluation, interpolation, command substitution or shell calls.
        environment.setdefault(key,value)
    return environment


def network_settings(environment, component):
    prefix='MASTER' if component=='master' else 'FRONTEND'
    host=environment.get(prefix+'_HOST','127.0.0.1')
    if host!='localhost':ipaddress.ip_address(host)
    port=int(environment.get(prefix+'_PORT','8000' if component=='master' else '5173'))
    if not 1<=port<=65535:raise ValueError('Port must be 1-65535')
    return host,str(port)


def validate_url(value):
    parsed=urlsplit(value)
    parsed.port
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Master URL must be HTTP(S) without credentials/query/fragment')


def command_for(component, environment):
    if component=='master':
        host,port=network_settings(environment,component)
        return [str(ROOT/'master/.venv/Scripts/python.exe'),'-m','uvicorn','master.main:app','--host',host,'--port',port],ROOT
    if component=='worker':
        validate_url(environment.get('MASTER_URL','http://127.0.0.1:8000'))
        return [str(ROOT/'worker/.venv/Scripts/python.exe'),'worker/worker.py'],ROOT
    host,port=network_settings(environment,component)
    validate_url(environment.get('VITE_MASTER_URL','http://127.0.0.1:8000'))
    return ['cmd.exe','/d','/c','npm.cmd','run','dev','--','--host',host,'--port',port,'--strictPort'],ROOT/'frontend'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component',choices=['master','worker','frontend'])
    parser.add_argument('--env-file',type=Path)
    parser.add_argument('--check',action='store_true',help='Validate files/configuration and print command without starting a service')
    args=parser.parse_args()
    try:
        if args.env_file and not args.env_file.is_file():raise ValueError('Explicit environment file does not exist')
        path=args.env_file or ROOT/args.component/'.env'
        environment=load_env(path,os.environ)
        command,cwd=command_for(args.component,environment)
        needed=ROOT/'frontend/node_modules/vite/bin/vite.js' if args.component=='frontend' else Path(command[0])
        if not needed.is_file():raise ValueError('Component dependencies are missing; run scripts/setup.cmd')
        if args.check:
            print(json.dumps({'component':args.component,'command':command,'cwd':str(cwd),'status':'configuration checked; service not started'}))
            return 0
        return subprocess.call(command,cwd=cwd,env=environment)
    except KeyboardInterrupt:return 130
    except (ValueError,OSError) as exc:
        print(f'Startup failed: {exc}',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
