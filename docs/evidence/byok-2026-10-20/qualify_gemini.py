import getpass
import json
import os
import platform
import sys
import time
from pathlib import Path

from raphael_agent.byok import client
from raphael_agent.byok.models import BYOKConfig
from raphael_agent.scripts import byok_smoke

key = getpass.getpass('Gemini key (hidden): ')
for name in list(os.environ):
    if name.startswith('RAPHAEL_LLM_') or name in {'OPENAI_API_KEY', 'GEMINI_API_KEY', 'RAPHAEL_OPENAI_API_KEY', 'RAPHAEL_GEMINI_API_KEY'}:
        os.environ.pop(name, None)
os.environ.update(RAPHAEL_LLM_PROVIDER='gemini', RAPHAEL_GEMINI_API_KEY=key,
                  RAPHAEL_LLM_MAX_TOKENS='128', RAPHAEL_LLM_TIMEOUT_SECONDS='30')
client.MAX_MODEL_ATTEMPTS = 1  # Qualification-only cap: never rotate live.
evidence = {'environment': platform.platform(), 'python': platform.python_version(),
            'hostname': 'generativelanguage.googleapis.com', 'completion_cap': 2,
            'per_completion_output_cap': 128, 'events': [], 'cases': []}
original_request = client._request
candidate_set = []
phase = 'automatic_smoke'

def observed(http, config, method, url, deadline, **kwargs):
    if method == 'POST' and sum(e['method'] == 'POST' for e in evidence['events']) >= 2:
        raise client.BYOKError('qualification_request_budget_exceeded')
    if 'generativelanguage.googleapis.com/' not in url:
        raise client.BYOKError('qualification_endpoint_rejected')
    body = kwargs.get('body') or {}
    event = {'phase': phase, 'method': method, 'requested_model': body.get('model')}
    evidence['events'].append(event)
    started = time.monotonic()
    try:
        data = original_request(http, config, method, url, deadline, **kwargs)
        event['status'] = 'PASS'
        if method == 'GET':
            event['catalog_entries'] = len(data.get('models', []))
            event['next_page_present'] = bool(data.get('nextPageToken'))
        else:
            event['returned_model'] = data.get('model')
            event['usage'] = data.get('usage')
            choices = data.get('choices') or [{}]
            event['finish_reason'] = choices[0].get('finish_reason')
        return data
    except client.BYOKError as exc:
        event['status'] = str(exc)
        raise
    finally:
        event['seconds'] = round(time.monotonic() - started, 3)

client._request = observed
original_discover = client.discover_models

def discovery(http, config, deadline):
    models = original_discover(http, config, deadline)
    candidate_set[:] = models
    return models

client.discover_models = discovery
sys.argv = ['byok_smoke', '--live']
rc = byok_smoke.main()
evidence['cases'].append({'case': phase, 'exit': rc})
evidence['candidates'] = sorted(candidate_set)

def save():
    safe = json.dumps(evidence, indent=2)
    assert key not in safe
    Path('/tmp/raphael-gemini-live-evidence.json').write_text(safe + '\n')
    print(safe, flush=True)

save()
if not candidate_set:
    sys.exit(rc)
model = input('Pinned discovered model (blank stops): ').strip()
if not model:
    sys.exit(0)
if model not in candidate_set:
    sys.exit('model_not_in_discovered_candidates')
os.environ.update(RAPHAEL_LLM_MODEL=model, RAPHAEL_LLM_DIAGNOSIS='1', RAPHAEL_LLM_PATCH='1')
phase = 'explicit_patch'
from raphael_agent.patch.llm import try_llm_patch
run = {
    'issue_title': 'Fix one readiness port',
    'issue_body': 'Synthetic fixture only. deploy/probe.yaml is exactly: readinessProbe: {httpGet: {path: /, port: 8081}}. App listens on 8080. Change only 8081 to 8080; return that one-line YAML file with a brief summary.',
    'fix_rules': {'writable_path_prefixes': ['deploy/']},
    'diagnosis': {}, 'evidence': [],
}
result = try_llm_patch(run)
expected = 'readinessProbe: {httpGet: {path: /, port: 8080}}'
passed = (result is not None and result['policy_status'] == 'allowed'
          and len(result['files']) == 1 and result['files'][0]['path'] == 'deploy/probe.yaml'
          and result['files'][0]['action'] == 'modify'
          and result['files'][0]['content'].strip() == expected)
evidence['cases'].append({'case': phase, 'pass': passed, 'proposal': result})
save()
