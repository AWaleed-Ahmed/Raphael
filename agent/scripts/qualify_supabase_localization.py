#!/usr/bin/env python3
"""Disposable live catalog qualification. Direct REST seeding is NOT production ingestion.

No migration or executor is invoked. --live authorizes writes only to --project-host.
An operator-observed healthy baseline JSON is required; credentials are env-only.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import quote, urlencode, urlsplit
from uuid import UUID, uuid5
from unittest.mock import patch

from raphael_agent.graph.nodes import node_localize
from raphael_agent.graph.state import initial_run_state
from raphael_agent.localization.supabase_catalog import SupabaseCatalogError, SupabaseHealthyCatalogStore
from raphael_agent.patch.image_provenance import image_repository


def plan(run_id):
    run = UUID(run_id)
    return [{'company_id': str(uuid5(run, 'company-' + name[0])),
             'client_id': f'qualification-{run.hex}-{name}', 'client_name': 'Qualification ' + name,
             'metadata': {'qualification_run': str(run)}} for name in ('a1', 'a2', 'b1')]


def cleanup(store, report):
    for client in plan(report['run_id']):
        query = urlencode({'client_id': 'eq.' + client['client_id'],
                           'company_id': 'eq.' + client['company_id'],
                           'metadata->>qualification_run': 'eq.' + report['run_id']})
        store._request('DELETE', 'raphael_clients?' + query)
    report['cleanup'] = 'PASS (exact run-owned clients; trace FK cascades)'


def observed_baseline(path):
    data = json.loads(path.read_text())
    required = ('service_name', 'environment', 'operation', 'repository', 'trace_id')
    if not all(isinstance(data.get(k), str) and data[k] and data[k] != 'unknown' for k in required):
        raise ValueError('observed_baseline_identity_missing')
    if not re.fullmatch('[0-9a-fA-F]{40}', str(data.get('source_commit_sha', ''))):
        raise ValueError('observed_full_commit_required')
    identity = data.get('runtime_identity') or {}
    if identity.get('resource_kind') != 'Deployment' or not all(identity.get(k) for k in ('resource_name', 'namespace', 'cluster')):
        raise ValueError('observed_workload_identity_missing')
    images = identity.get('container_images') or {}
    if not isinstance(images, dict) or not images or not all(
        isinstance(v, str) and re.fullmatch(r'.+@sha256:[0-9a-fA-F]{64}', v) for v in images.values()
    ):
        raise ValueError('observed_container_digest_required')
    health = data.get('health_observation') or {}
    if health.get('ready') is not True or not health.get('observed_at') or not health.get('evidence_path'):
        raise ValueError('independent_health_evidence_required')
    return data


def exercise(store, report, baseline):
    clients = plan(report['run_id'])
    rows = []
    for index, client in enumerate(clients):
        store._request('POST', 'raphael_clients', client, 'return=representation')
        # Fixture copies intentionally overlap all non-tenant scope. These are
        # direct backend writes, never claims of actual deployments per tenant.
        row = {**{k: baseline[k] for k in ('service_name', 'environment', 'operation', 'repository', 'trace_id', 'source_commit_sha', 'runtime_identity')},
               'company_id': client['company_id'], 'client_id': client['client_id'],
               'healthy_trace_id': str(uuid5(UUID(report['run_id']), 'trace-' + str(index))),
               'normalized_stack_trace': 'qualification-observed-baseline',
               'stack_fingerprint': 'qualification-overlap', 'code_id': 'qualification-overlap',
               'trace_provider': 'qualification-direct-seed', 'verified_healthy': True, 'is_last_known_good': True,
               'metadata': {'qualification_run': report['run_id'], 'evidence_kind': 'direct_fixture_seed'}}
        report['trace_ids'].append(row['healthy_trace_id'])
        rows.append(store.record_healthy_trace(row))
        assert store.record_healthy_trace(row)['healthy_trace_id'] == row['healthy_trace_id'], 'upsert_not_idempotent'
    first = rows[0]
    query = {k: first[k] for k in ('company_id', 'client_id', 'service_name', 'environment', 'operation')}
    assert [r['healthy_trace_id'] for r in store.list_healthy_traces(**query)] == [first['healthy_trace_id']]
    report['checks']['idempotent_scoped_retrieval'] = 'PASS (LIVE; direct fixture seed)'
    for field, wrong in [('company_id', clients[2]['company_id']), ('client_id', clients[1]['client_id']),
                         ('service_name', 'qualification-wrong'), ('environment', 'qualification-wrong'),
                         ('operation', 'qualification-wrong')]:
        actual = store.list_healthy_traces(**{**query, field: wrong})
        # A2 is a valid separate client: retrieval may return its OWN trace, not A1.
        assert first['healthy_trace_id'] not in [r['healthy_trace_id'] for r in actual], 'cross_scope_row'
    report['checks']['adapter_wrong_scope'] = 'PASS (LIVE service-role application filtering; NOT RLS)'
    conflict = {**first, 'healthy_trace_id': str(uuid5(UUID(report['run_id']), 'conflict')),
                'stack_fingerprint': 'qualification-conflict'}
    try:
        store.record_healthy_trace(conflict)
    except SupabaseCatalogError as exc:
        assert str(exc) == 'supabase_http_409', 'unexpected_conflict_error'
    else:
        report['trace_ids'].append(conflict['healthy_trace_id'])
        raise AssertionError('conflicting_last_known_good_accepted')
    report['checks']['conflicting_last_known_good'] = 'PASS (LIVE database refusal)'

    container, image = next(iter(first['runtime_identity']['container_images'].items()))
    signature = {'class': 'bad_image_reference',
                 'key': 'bad_image:' + first['runtime_identity']['resource_name'] + ':' + image_repository(image) + ':does-not-exist',
                 'normalized': {**{k: first['runtime_identity'][k] for k in ('resource_kind', 'resource_name', 'namespace', 'cluster')},
                                'container': container, 'attributes': {'image': image_repository(image) + ':does-not-exist',
                                    'image_pull_cause': 'not_found', 'owner_verified': True,
                                    'container_type': 'regular', 'evidence_source': 'mock_fixture'}}}
    owner, name = first['repository'].split('/', 1)
    state = initial_run_state({'run_id': report['run_id'], 'tenant_id': 'qualification',
        'company_id': first['company_id'], 'client_id': first['client_id'], 'trigger': {'kind': 'fixture'},
        'repository': {'owner': owner, 'name': name}, 'commit_sha': first['source_commit_sha'],
        'target_environment': first['environment'], 'runtime_observation': query}, sandbox_mode='recorded_stub')
    state['failure_signature'] = signature
    state['sandbox_backend'] = 'mock'  # Synthetic gate evidence; no executor is invoked.
    env = {'RAPHAEL_COMPANY_ID': first['company_id'], 'RAPHAEL_CLIENT_ID': first['client_id'],
           'RAPHAEL_HEALTHY_CATALOG_ENABLED': '1', 'RAPHAEL_MODEL_ENABLED': '0',
           'RAPHAEL_LLM_DIAGNOSIS': '0', 'RAPHAEL_LLM_PATCH': '0', 'RAPHAEL_LEARNING': '0'}
    with patch.dict(os.environ, env):
        result = node_localize(state)
        assert result['localization_result']['approved_image_replacement']['image'] == image, 'graph_image_selection_failed'
        for field, wrong in [('company_id', clients[2]['company_id']), ('client_id', clients[1]['client_id'])]:
            refused = node_localize({**state, field: wrong})
            assert refused['localization_result']['reason'] == 'catalog_scope_rejected'
        wrong_repo = node_localize({**state, 'repository': {'owner': 'qualification', 'name': 'wrong'}})
        assert 'approved_image_replacement' not in wrong_repo['localization_result']
    report['checks']['graph_image_selection'] = 'PASS (LIVE database read; synthetic signature; NO sandbox)'
    report['checks']['spoofed_scope_repository_refusal'] = 'PASS (LIVE-configured graph)'

    public = os.environ.get('SUPABASE_PUBLISHABLE_KEY') or os.environ.get('SUPABASE_ANON_KEY')
    if not public:
        report['checks']['rls'] = 'BLOCKED: publishable/anon key and real scoped JWT identities required'
        return
    from raphael_agent.localization import supabase_catalog
    for label, token, expected in [('anonymous', None, []),
            ('unauthorized', 'invalid.synthetic.signature', []),
            ('unscoped', os.environ.get('SUPABASE_TEST_JWT_UNSCOPED'), []),
            ('mismatched', os.environ.get('SUPABASE_TEST_JWT_MISMATCHED'), []),
            *[(n, os.environ.get('SUPABASE_TEST_JWT_' + n.upper()), [r['healthy_trace_id']])
              for n, r in zip(('a1', 'a2', 'b1'), rows)]]:
        if label != 'anonymous' and not token:
            report['checks']['rls_' + label] = 'BLOCKED: scoped JWT not configured'
            continue
        headers = {'apikey': public, 'Content-Type': 'application/json'}
        if token: headers['Authorization'] = 'Bearer ' + token
        with patch.object(supabase_catalog, 'backend_headers', lambda key: headers):
            try:
                result = store._request('GET', 'raphael_healthy_traces?' + urlencode({'metadata->>qualification_run': 'eq.' + report['run_id']}))
            except SupabaseCatalogError as exc:
                assert label in {'anonymous', 'unauthorized'} and str(exc) in {'supabase_http_401', 'supabase_http_403'}, 'rls_read_failed'
                result = []
            assert sorted(r['healthy_trace_id'] for r in result) == sorted(expected), 'rls_scope_leak_or_missing_identity'
            try:
                store._request('POST', 'raphael_healthy_traces', first)
            except SupabaseCatalogError as exc:
                assert str(exc) in {'supabase_http_401', 'supabase_http_403'}, 'unexpected_write_refusal'
            else:
                raise AssertionError('unauthorized_write_allowed')
        report['checks']['rls_' + label] = 'PASS (LIVE read/write controls)'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True, help='Unique UUID; choose before preparing scoped JWT identities')
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--project-host', help='Explicitly authorized disposable project hostname')
    parser.add_argument('--observed-baseline', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--retain', action='store_true', help='Explicitly retain only this run for a subsequent disposable executor check')
    parser.add_argument('--cleanup', type=Path, help='Retry exact-row cleanup using a retained manifest')
    args = parser.parse_args()
    clients = plan(args.run_id)
    if args.plan:
        print(json.dumps(clients, indent=2)); return 0
    if not args.live or not args.project_host or not args.output:
        print('BLOCKED: --live, --project-host and --output are required; no requests made')
        return 2
    url = os.environ.get('SUPABASE_URL', '')
    if urlsplit(url).hostname != args.project_host:
        print('BLOCKED: SUPABASE_URL does not match the authorized project host; no requests made'); return 2
    if not args.cleanup and (not args.observed_baseline or not args.observed_baseline.is_file()):
        print('BLOCKED: --observed-baseline must name an independently observed healthy deployment record; no requests made'); return 2
    report = {'run_id': str(UUID(args.run_id)), 'project_host': args.project_host, 'clients': clients,
              'trace_ids': [], 'intended_trace_ids': [str(uuid5(UUID(args.run_id), 'trace-' + str(i))) for i in range(3)], 'checks': {}, 'production_ingestion': 'DEFERRED: no supported automatic writer',
              'sandbox_validation': 'NOT RUN: no sandbox created by this harness'}
    store = None
    failed = False
    started = time.monotonic()
    try:
        baseline = None if args.cleanup else observed_baseline(args.observed_baseline)
        if args.cleanup:
            retained = json.loads(args.cleanup.read_text())
            assert retained['run_id'] == report['run_id'] and retained['project_host'] == args.project_host
        store = SupabaseHealthyCatalogStore()
        original_request = store._request
        report['requests'] = {}
        def counted(method, *args, **kwargs):
            report['requests'][method] = report['requests'].get(method, 0) + 1
            return original_request(method, *args, **kwargs)
        store._request = counted
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Persist intended IDs before the first write, including ambiguous timeouts.
        if not args.cleanup:
            args.output.write_text(json.dumps(report, indent=2) + '\n')
            exercise(store, report, baseline)
    except Exception as exc:
        report['failure_type'] = type(exc).__name__
        if isinstance(exc, SupabaseCatalogError):
            report['failure_code'] = str(exc)  # Adapter emits sanitized codes, never provider bodies.
        failed = True
    finally:
        if store is not None and args.retain and not failed and not args.cleanup:
            report['cleanup'] = 'RETAINED by explicit --retain; use --cleanup with this manifest'
        elif store is not None:
            try: cleanup(store, report)
            except Exception:
                report['cleanup'] = 'FAILED: retain manifest and rerun --cleanup; no broad deletes'
                failed = True
        report['overall'] = 'DEFERRED: fixture checks do not establish ingestion or sandbox repair'
        report['seconds'] = round(time.monotonic() - started, 3)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 1 if failed else (2 if any('BLOCKED' in v for v in report['checks'].values()) else 0)


if __name__ == '__main__':
    sys.exit(main())
