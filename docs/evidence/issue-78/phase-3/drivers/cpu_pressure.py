import json,subprocess,time
from pathlib import Path
from qualify_model_runtime import configure,execute,memory_sample
configure(True);root=Path('/tmp/phase3');cases=json.loads((root/'fault-cases.json').read_text())['faults'];jobs=[{'id':c['id'],'capability':'failure_classifier','state':c['state']} for c in cases]
baseline={j['id']:execute(j,root/'models')['output_sha256'] for j in jobs};children=[]
try:
 for _ in range(2):children.append(subprocess.Popen(['/tmp/phase3/runtime-v2/bin/python','-c','import time; deadline=time.monotonic()+20\nwhile time.monotonic()<deadline: pass']))
 time.sleep(.2)
 rows=[execute(j,root/'models') for j in jobs for _ in range(10)]
 assert all(r['output_sha256']==baseline[r['job_id']] and r['unavailable_reason'] is None for r in rows)
 Path('/tmp/phase3/cpu-pressure.json').write_text(json.dumps({'control':'two_owned_cpu_burners_inside_2cpu_cgroup','calls':rows,'resources':memory_sample(),'serial_output_mismatches':0},indent=2,sort_keys=True)+'\n')
finally:
 for child in children:
  child.terminate();child.wait(timeout=5)
