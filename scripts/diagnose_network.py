"""Read-only bounded socket diagnostics; never changes security configuration."""
import json
import socket
import subprocess
import sys


def probe(name, action):
    try:
        value=action()
        return {'probe':name,'status':'passed','detail':value}
    except OSError as exc:
        return {'probe':name,'status':'failed','winerror':getattr(exc,'winerror',None),'errno':exc.errno,'detail':str(exc)}


def bind(port):
    with socket.socket() as server:
        server.settimeout(1)
        server.bind(('127.0.0.1',port));server.listen(1)
        return f'Loopback bind/listen succeeded on port {server.getsockname()[1]}'


def handshake():
    with socket.socket() as server:
        server.settimeout(1);server.bind(('127.0.0.1',0));server.listen(1)
        with socket.socket() as client:
            client.settimeout(1);client.connect(server.getsockname())
            connection,_=server.accept()
            connection.close()
        return 'Ephemeral loopback connection succeeded'


def child_probe(name,code):
    try:
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=4)
        return {'probe':name,'status':'passed' if result.returncode==0 else 'failed','detail':(result.stdout+result.stderr)[-2000:]}
    except subprocess.TimeoutExpired:
        return {'probe':name,'status':'blocked','detail':'Child probe exceeded 4 seconds; stopped owned child only'}


if __name__=='__main__':
    results=[probe('bind_ephemeral',lambda:bind(0)),probe('bind_8000',lambda:bind(8000)),
             probe('bind_5173',lambda:bind(5173)),probe('ephemeral_loopback_connect',handshake),
             child_probe('socketpair','import socket; a,b=socket.socketpair(); a.close(); b.close(); print("socketpair succeeded")'),
             child_probe('npm_registry_dns','import socket; print(socket.getaddrinfo("registry.npmjs.org",443))')]
    print(json.dumps(results,indent=2))
