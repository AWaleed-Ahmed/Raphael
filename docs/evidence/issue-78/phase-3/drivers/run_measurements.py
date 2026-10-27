"""Disposable local cgroup orchestration; no production services are touched."""
import hashlib,json,subprocess,time,uuid
from pathlib import Path
base=Path('/tmp/phase3');output=base/'measurements';output.mkdir()
records=[]
def unit(mode,tag,*,enabled=True,extra=(),memory='2G',timeout=180):
 name='raphael-phase3-'+uuid.uuid4().hex[:10]
 target=output/(tag+'.json') if mode!='load' else output/tag
 command=['systemd-run','--user','--unit='+name,'--wait','--pipe','--collect','-p','CPUQuota=200%','-p','MemoryMax='+memory,'-p','MemorySwapMax=0','-p','RuntimeMaxSec='+str(timeout),'-p','WorkingDirectory='+str(base),'/usr/bin/taskset','-c','2,3',str(base/'runtime-v2/bin/python'),str(base/'worker.py'),mode,'--jobs',str(base/'jobs.json'),'--model-root',str(base/'models'),'--output',str(target)]
 if enabled:command+=['--enabled']
 command+=list(extra)
 start=time.perf_counter();r=subprocess.run(command,capture_output=True,text=True,timeout=timeout+30)
 (output/(tag+'.log')).write_text(r.stdout+r.stderr)
 record={'control_id':tag,'mode':mode,'model_enabled':enabled,'unit':name,'argv':command,'exit_code':r.returncode,'elapsed_seconds':time.perf_counter()-start,'output':str(target.relative_to(base))}
 records.append(record);(output/'index.json').write_text(json.dumps(records,sort_keys=True,indent=2)+'\n')
 if r.returncode:raise RuntimeError('measurement unit failed: '+tag)
 return record
for i in range(30):
 for enabled in ((False,True) if i%2==0 else (True,False)):
  unit('probe',f'cold-{i:02d}-{int(enabled)}',enabled=enabled)
 if i%5==4:print('cold pairs completed',i+1,flush=True)
for enabled in (False,True):unit('warm','warm-'+str(int(enabled)),enabled=enabled,extra=('--repeats','1000'))
for c in (1,4,8,16):
 unit('load','saturation-'+str(c),extra=('--warmup','5','--duration','60','--concurrency',str(c),'--period','0.05'))
 print('saturation completed',c,flush=True)
unit('load','burst-2x',extra=('--warmup','5','--duration','60','--concurrency','8','--period','1'))
print('completed cold, warm, saturation and burst measurements',flush=True)
