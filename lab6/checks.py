import json,os,pathlib,shlex,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parent
E=ROOT/'evidence';E.mkdir(exist_ok=True)
M=ROOT/'manifests'
def run(*args,ok=True,show=True,env=None):
    p=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env)
    if show:
        print('$ '+shlex.join(args),flush=True)
        print(p.stdout.strip(),flush=True)
    if ok and p.returncode:raise RuntimeError(f'command exited {p.returncode}')
    return p

def k(*args,**kw):return run('kubectl',*args,**kw)
def apply(name):k('apply','-f',str(M/(name+'.yaml')))
def pod_ip(name,ns='demo'):return k('get','pod',name,'-n',ns,'-o','jsonpath={.status.podIP}',show=False).stdout.strip()
def expect(name,cmd,code=0,text=None):
    for _ in range(12):
        p=run(*cmd,ok=False,show=False)
        if p.returncode==code and (text is None or text in p.stdout):break
        time.sleep(2)
    print('$ '+shlex.join(cmd),flush=True);print(p.stdout.strip(),flush=True)
    good=p.returncode==code and (text is None or text in p.stdout)
    print(f'{name}: '+('PASS' if good else 'FAIL')+f' (exit={p.returncode})',flush=True)
    assert good,name
    return p.stdout

def curl(pod='web',ns='demo',path='/users/42',method='GET',host='api',port=5000):
    return ['kubectl','exec','-n',ns,pod,'--','curl','-sS','--connect-timeout','2','--max-time','3','-o','/dev/null','-w','HTTP %{http_code}\\n','-X',method,f'http://{host}:{port}{path}']
def db(pod='api',host='db'):
    return ['kubectl','exec','-n','demo',pod,'--','env','PGCONNECT_TIMEOUT=3','psql','-h',host,'-U','postgres','-Atc','SELECT 1;']
def dns(tcp=False):return ['kubectl','exec','-n','demo','web','--','dig','+short','+time=2','+tries=1']+(['+tcp'] if tcp else [])+['kubernetes.default.svc.cluster.local']

def baseline():
    apply('apps');apply('probe-apps')
    for ns in ['demo','other','outside-target']:k('wait','--for=condition=Ready','pod','--all','-n',ns,'--timeout=180s')
    k('get','pods','-n','demo','--show-labels')
    expect('before policies: web -> api',curl(),text='HTTP 200')
    expect('before policies: POST accepted by application',curl(method='POST'),text='HTTP 200')
    expect('before policies: web -> db',db('web'),text='1')

def deny():
    apply('deny-all');time.sleep(5)
    expect('deny-all: web -> api IP blocked',curl(host=pod_ip('api')),code=28,text='HTTP 000')
    expect('deny-all: api -> db IP blocked',db(host=pod_ip('db')),code=2,text='timeout')

def allow():
    for name in ['allow-web-api','allow-api-db','allow-egress','allow-dns']:apply(name)
    time.sleep(5)
    expect('L4 web -> api:5000 allowed',curl(),text='HTTP 200')
    expect('L4 api -> db:5432 allowed',db(),text='1')
    expect('L4 web -> db:5432 blocked',db('web'),code=2,text='timeout')
    expect('DNS UDP allowed',dns(),text='10.')
    expect('DNS TCP allowed',dns(True),text='10.')

def l7():
    k('delete','networkpolicy','allow-web-api','-n','demo');apply('l7-api');time.sleep(5)
    expect('L7 GET /users/42 allowed',curl(),text='HTTP 200')
    expect('L7 GET /users/alice allowed',curl(path='/users/alice'),text='HTTP 200')
    expect('L7 GET /admin denied',curl(path='/admin'),text='HTTP 403')
    expect('L7 GET /users denied',curl(path='/users'),text='HTTP 403')
    expect('L7 POST /users/42 denied',curl(method='POST'),text='HTTP 403')
    expect('database access preserved',db(),text='1')

def isolation():
    # Temporary diagnostic allow policies prove explicit deny takes priority.
    temporary={'apiVersion':'cilium.io/v2','kind':'CiliumNetworkPolicy','metadata':{'name':'temporary-other-allow','namespace':'demo'},'spec':{'endpointSelector':{'matchLabels':{'app':'api'}},'ingress':[{'fromEndpoints':[{'matchLabels':{'k8s:io.kubernetes.pod.namespace':'other','app':'web'}}],'toPorts':[{'ports':[{'port':'5000','protocol':'TCP'}],'rules':{'http':[{'method':'GET','path':'^/users/.*$'}]}}]}]}}
    egress={'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':{'name':'temporary-other-egress','namespace':'demo'},'spec':{'podSelector':{'matchLabels':{'app':'api'}},'policyTypes':['Egress'],'egress':[{'to':[{'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':'outside-target'}}}],'ports':[{'port':5000,'protocol':'TCP'}]}]}}
    temp=E/'temporary.json';temp.write_text(json.dumps({'apiVersion':'v1','kind':'List','items':[temporary,egress]}));k('apply','-f',str(temp));time.sleep(5)
    expect('before isolation: other/web -> demo/api',curl(ns='other',host='api.demo.svc.cluster.local'),text='HTTP 200')
    target=pod_ip('echo','outside-target')
    expect('before isolation: demo/api -> outside-target',curl(pod='api',host=target),text='HTTP 200')
    apply('isolate-demo');time.sleep(5)
    expect('after isolation: other/web -> demo/api blocked',curl(ns='other',host='api.demo.svc.cluster.local'),code=28,text='HTTP 000')
    expect('after isolation: demo/api -> outside-target blocked',curl(pod='api',host=target),code=28,text='HTTP 000')
    expect('same namespace web -> api preserved',curl(),text='HTTP 200')
    expect('DNS exception preserved',dns(),text='10.')
    k('delete','-f',str(temp))

def external():
    node=k('get','node','-o','json',show=False);obj=json.loads(node.stdout)['items'][0]
    node_ip=next(a['address'] for a in obj['status']['addresses'] if a['type']=='InternalIP')
    cidr=k('get','ciliumnode','-o','jsonpath={.items[0].spec.ipam.podCIDRs[0]}',show=False).stdout.strip()
    if not cidr:cidr=obj['spec']['podCIDR']
    target=pod_ip('echo','outside-target')
    run('docker','run','-d','--name','lab6-external','--network','minikube','--cap-add','NET_ADMIN','--entrypoint','sh','lab6-demo:local','-c',f'ip route add {cidr} via {node_ip}; sleep infinity')
    cmd=['docker','exec','lab6-external','curl','-sS','--connect-timeout','2','--max-time','3','-o','/dev/null','-w','HTTP %{http_code}\\n',f'http://{target}:5000/users/42']
    expect('external source before cluster policy',cmd,text='HTTP 200')
    apply('external-lockdown');time.sleep(5)
    expect('external source after cluster policy blocked',cmd,code=28,text='HTTP 000')
    expect('cluster traffic still allowed',curl(),text='HTTP 200')
    k('get','ciliumclusterwidenetworkpolicy','external-lockdown')

def observe():
    expect('Hubble Relay ready',['hubble','status'],text='Flows:')
    expect('generate allowed HTTP flow',curl(),text='HTTP 200')
    expect('generate L7 denied HTTP flow',curl(path='/admin'),text='HTTP 403')
    expect('generate denied DB flow',db('web'),code=2,text='timeout')
    time.sleep(3)
    out=run('hubble','observe','--from-namespace','demo','--protocol','http','--last','20','--output','json').stdout
    (E/'http-flows.jsonl').write_text(out)
    assert '403' in out and '200' in out,'HTTP allow/deny evidence missing'
    run('hubble','observe','--from-namespace','demo','--protocol','http','--last','10')
    run('hubble','observe','--from-namespace','demo','--verdict','DROPPED','--last','5')
    print('Hubble recorded allowed and denied traffic: PASS')

if __name__=='__main__':
    assert sys.argv[1] in ['baseline','deny','allow','l7','isolation','external','observe']
    globals()[sys.argv[1]]()
