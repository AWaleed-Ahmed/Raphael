"""Kill and exhaust only disposable phase-3 units, then verify real runtime recovery."""
import json,subprocess,time,uuid
from pathlib import Path
base=Path('/tmp/phase3');out=base/'resource-controls';out.mkdir()
cases=json.loads((base/'fault-cases.json').read_text())['faults'];records=[]
for case in cases:
 casefile=out/(case['id']+'-jobs.json');casefile.write_text(json.dumps({'jobs':[{'id':case['id'],'capability':'failure_classifier','state':case['state']}]})+'\n')
 for mode in ('oom','hold'):
  name='raphael-phase3-control-'+uuid.uuid4().hex[:10];marker=out/(case['id']+'-'+mode+'.json')
  command=['systemd-run','--user','--unit='+name,'--wait','--pipe','--collect','-p','CPUQuota=200%','-p','MemoryMax='+('128M' if mode=='oom' else '2G'),'-p','MemorySwapMax=0','-p','RuntimeMaxSec=30','-p','OOMPolicy=stop','-p','WorkingDirectory='+str(base),'/usr/bin/taskset','-c','2,3',str(base/'runtime-v2/bin/python'),str(base/'worker.py'),mode,'--jobs',str(casefile),'--model-root',str(base/'models'),'--output',str(marker),'--enabled']
  start=time.perf_counter();process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:
   if mode=='hold':
    deadline=time.monotonic()+15
    while not marker.exists() and process.poll() is None and time.monotonic()<deadline:time.sleep(.05)
    assert marker.exists(),'worker did not reach owned inference state'
    subprocess.run(['systemctl','--user','kill','--kill-whom=all','--signal=SIGKILL',name],check=True,capture_output=True)
   stdout,stderr=process.communicate(timeout=30)
   (out/(case['id']+'-'+mode+'.log')).write_text(stdout+stderr)
   assert process.returncode!=0
   assert marker.exists()
   begun=json.loads(marker.read_text());assert begun['status']=='started_not_completed'
   if mode=='oom':assert 'oom-kill' in stdout+stderr
   assert all(c['unavailable_reason'] is None for c in begun['calls'])
  finally:
   if process.poll() is None:
    subprocess.run(['systemctl','--user','stop',name],capture_output=True)
    process.communicate(timeout=10)
  healthy=out/(case['id']+'-'+mode+'-restart.json');restart_command=command.copy();restart_command[2]='--unit='+name+'-recovery';restart_command[restart_command.index('MemoryMax=128M') if 'MemoryMax=128M' in restart_command else restart_command.index('MemoryMax=2G')]='MemoryMax=2G';restart_command[restart_command.index(mode)]='probe';restart_command[restart_command.index(str(marker))]=str(healthy)
  restart=time.perf_counter();result=subprocess.run(restart_command,capture_output=True,text=True,timeout=60);recovery=time.perf_counter()-restart
  assert result.returncode==0 and all(c['unavailable_reason'] is None for c in json.loads(healthy.read_text())['calls'])
  records.append({'case_id':case['id'],'control':mode,'unit':name,'victim_exit_code':process.returncode,'false_completed_results':0,'started_marker':True,'recovery_seconds':recovery,'recovery_passed':recovery<=60,'victim_elapsed_seconds':restart-start,'memory_limit_bytes':134217728 if mode=='oom' else 2147483648})
  (out/'summary.json').write_text(json.dumps({'scope':'owned_inference_processes_only; not downstream journal or sandbox recovery','controls':records},sort_keys=True,indent=2)+'\n')
  print(case['id'],mode,'recovered',round(recovery,3),flush=True)
