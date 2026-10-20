#!/usr/bin/env python3
"""Paired synthetic replay, never live ingestion or repair proof. No networking."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from unittest.mock import patch

from raphael_agent.graph import nodes
from raphael_agent.graph.state import initial_run_state
from raphael_agent.localization.supabase_catalog import SupabaseCatalogError

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'agent/fixtures/localization/supabase_qualification_cases.json'
SCOPE = dict(company_id='synthetic-a', client_id='synthetic-a1', service_name='checkout',
             environment='qualification', operation='POST /orders', repository='fixture/checkout')
GOOD_IMAGE = 'registry.example/checkout@sha256:' + 'b' * 64


def inputs(case):
    """Expand an authored fault scenario; ground truth comes only from the frozen file."""
    target = case['expected_path']
    paths = ['src/http.py', 'src/cache.py', 'src/queue.py', target]
    seed = dict(run_id=case['id'], tenant_id='qualification', company_id=SCOPE['company_id'],
                client_id=SCOPE['client_id'], trigger={'kind': 'fixture'}, commit_sha='c' * 40,
                repository={'owner': 'fixture', 'name': 'checkout'}, target_environment='qualification',
                manifests={'path': 'deploy/app.yaml'},
                changed_diff_hunks=[{'path': p, 'start_line': 10, 'end_line': 20} for p in paths],
                runtime_observation={**SCOPE, 'route': '/orders'})
    observation = seed['runtime_observation']
    if case.get('stack'):
        observation['stack_trace'] = f'File "{target}", line 12, in fault'
    span_path = 'src/http.py' if case['baseline'] == 'misleading' else target
    if case['baseline'] in {'trace', 'misleading'}:
        observation['span_sequence'] = [{'name': 'request'}, {'name': 'changed',
            'code.file.path': span_path, 'code.line.number': 12, 'code.function.name': 'fault'}]
    row = {**SCOPE, 'healthy_trace_id': case['id'], 'verified_healthy': True,
           'is_last_known_good': True, 'source_commit_sha': 'a' * 40,
           'stack_fingerprint': 'healthy', 'normalized_stack_trace': 'healthy',
           'span_sequence': [{'name': 'request'}, {'name': 'healthy'}]}
    if case['baseline'] in {'route', 'misleading-route'}:
        row['route_handler_map'] = {'/orders': {'path': 'src/http.py' if case['baseline'] == 'misleading-route' else target,
                                              'line': 12, 'symbol': 'handler'}}
    if case['kind'] == 'image':
        container = case.get('container', 'api')
        seed['failure_signature'] = {'class': 'bad_image_reference',
            'key': 'bad_image:checkout:registry.example/checkout:does-not-exist',
            'normalized': {'resource_kind': 'Deployment', 'resource_name': 'checkout',
                           'container': container, 'reason': 'ImagePullBackOff',
                           'attributes': {'image': 'registry.example/checkout:does-not-exist',
                                          'image_pull_cause': 'not_found', 'owner_verified': True,
                                          'container_type': 'regular', 'evidence_source': 'mock_fixture'}}}
        row['runtime_identity'] = {'resource_kind': 'Deployment', 'resource_name': 'checkout',
                                   'container_images': {container: GOOD_IMAGE}}
    rows = [row]
    kind = case['baseline']
    if kind == 'wrong-company': row['company_id'] = 'synthetic-b'
    if kind == 'wrong-client': row['client_id'] = 'synthetic-a2'
    if kind == 'unverified': row['verified_healthy'] = False
    if kind == 'missing-commit': row.pop('source_commit_sha')
    if kind == 'wrong-container': row['runtime_identity']['container_images'] = {'other': GOOD_IMAGE}
    if kind == 'conflict':
        other = deepcopy(row)
        other['runtime_identity']['container_images'] = {'api': 'registry.example/checkout:other'}
        rows.append(other)
    if kind == 'none': rows = []
    state = initial_run_state(seed, sandbox_mode='recorded_stub')
    if 'failure_signature' in seed:
        state['failure_signature'] = seed['failure_signature']
        state['sandbox_backend'] = 'mock'  # Fixture gate only; no executor is invoked.
    return state, rows


def evaluate():
    cases = json.loads(FIXTURES.read_text())
    results = []
    env = {'RAPHAEL_HEALTHY_CATALOG_ENABLED': '1', 'RAPHAEL_MODEL_ENABLED': '0',
           'RAPHAEL_LLM_DIAGNOSIS': '0', 'RAPHAEL_LLM_PATCH': '0', 'RAPHAEL_LEARNING': '0',
           'RAPHAEL_COMPANY_ID': SCOPE['company_id'], 'RAPHAEL_CLIENT_ID': SCOPE['client_id']}
    for case in cases:
        state, baselines = inputs(case)
        modes = {}
        for enabled in (False, True):
            class ReplayCatalog:
                def get_client(self, client_id):
                    return {**SCOPE, 'status': 'active'}
                def list_healthy_traces(self, **kwargs):
                    if enabled and case['baseline'] == 'unavailable':
                        raise SupabaseCatalogError('synthetic_catalog_unavailable')
                    return deepcopy(baselines) if enabled else []
            started = time.perf_counter()
            with patch.dict(os.environ, env), patch.object(nodes, 'SupabaseHealthyCatalogStore', ReplayCatalog):
                output = nodes.node_localize(deepcopy(state))
            ranking = list(dict.fromkeys(c['path'] for c in output.get('fault_candidates', [])))
            rank = ranking.index(case['expected_path']) + 1 if case['expected_path'] in ranking else None
            approval = (output.get('localization_result') or {}).get('approved_image_replacement')
            modes['on' if enabled else 'off'] = {
                'ranking': ranking, 'rank': rank, 'rr': 1 / rank if rank else 0,
                'approved_image': approval['image'] if approval else None,
                'baseline_count': output.get('localization_result', {}).get('baseline_count', 0),
                'status': output.get('localization_result', {}).get('status'),
                'milliseconds': round((time.perf_counter() - started) * 1000, 3)}
        results.append({'id': case['id'], 'kind': case['kind'], 'truth': case['expected_path'],
                        'expected_approval': case.get('expected_approval'), **modes})
    summary = {}
    for mode in ('off', 'on'):
        images = [r for r in results if r['kind'] == 'image']
        negatives = [r for r in images if not r['expected_approval']]
        positives = [r for r in images if r['expected_approval']]
        summary[mode] = {
            'cases': len(results), 'top1': sum(r[mode]['rank'] == 1 for r in results),
            'top3': sum(r[mode]['rank'] is not None and r[mode]['rank'] <= 3 for r in results),
            'mrr': round(sum(r[mode]['rr'] for r in results) / len(results), 4),
            'correct_approved_images': sum(r[mode]['approved_image'] == GOOD_IMAGE for r in positives),
            'positive_image_cases': len(positives),
            'correct_refusals': sum(r[mode]['approved_image'] is None for r in negatives),
            'negative_image_cases': len(negatives),
            'unsafe_approvals': sum(r[mode]['approved_image'] is not None for r in negatives),
            'catalog_covered_cases': sum(r[mode]['baseline_count'] > 0 for r in results),
            'catalog_failures': sum(r[mode]['status'] == 'error' for r in results),
            'mean_replay_ms': round(sum(r[mode]['milliseconds'] for r in results) / len(results), 3)}
    wins = [r['id'] for r in results if r['on']['rr'] > r['off']['rr']]
    regressions = [r['id'] for r in results if r['on']['rr'] < r['off']['rr']]
    return {'label': 'SYNTHETIC OFFLINE REPLAY; no database or sandbox requests',
            'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'fixture_sha256': hashlib.sha256(FIXTURES.read_bytes()).hexdigest(),
            'scorer_sha256': hashlib.sha256((ROOT / 'agent/raphael_agent/localization/candidates.py').read_bytes()).hexdigest(),
            'graph_sha256': hashlib.sha256((ROOT / 'agent/raphael_agent/graph/nodes.py').read_bytes()).hexdigest(),
            'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
                'agent/raphael_agent/graph/nodes.py', 'agent/raphael_agent/localization/candidates.py',
                'agent/raphael_agent/localization/anchors.py', 'agent/raphael_agent/localization/supabase_catalog.py',
                'agent/raphael_agent/patch/image_provenance.py', 'agent/raphael_agent/patch/templates.py')},
            'off_definition': 'Same deterministic graph/scorer with no healthy catalog rows; candidate path pool is fixed',
            'sandbox_validated_repairs': {'status': 'NOT RUN', 'attempts': 0, 'successes': None},
            'live_catalog_latency': None, 'summary': summary, 'paired_localization': {
                'wins': wins, 'regressions': regressions, 'ties': len(results) - len(wins) - len(regressions)},
            'cases': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('label', 'summary', 'paired_localization')}, indent=2))


if __name__ == '__main__':
    main()
