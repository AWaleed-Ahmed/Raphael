"""Qualification commands must be harmless until explicitly authorized."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from unittest.mock import Mock


def harness():
    path = Path(__file__).resolve().parents[1] / 'scripts/qualify_supabase_localization.py'
    spec = spec_from_file_location('qualification_harness', path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_command_without_authorization_never_constructs_store(monkeypatch, capsys):
    module = harness()
    store = Mock(side_effect=AssertionError('network attempted'))
    monkeypatch.setattr(module, 'SupabaseHealthyCatalogStore', store)
    monkeypatch.setattr(sys, 'argv', ['qualify', '--run-id', '00000000-0000-4000-8000-000000000001'])
    assert module.main() == 2
    store.assert_not_called()
    assert 'no requests made' in capsys.readouterr().out


def test_cleanup_is_limited_to_exact_planned_run_and_metadata():
    module = harness()
    report = {'run_id': '00000000-0000-4000-8000-000000000001'}
    store = Mock()
    module.cleanup(store, report)
    assert store._request.call_count == 3
    for call in store._request.call_args_list:
        method, query = call.args
        assert method == 'DELETE'
        assert 'client_id=eq.qualification-00000000000040008000000000000001-' in query
        assert 'company_id=eq.' in query
        assert 'metadata-%3E%3Equalification_run=eq.' in query
        assert 'raphael_clients?' in query


def test_cleanup_manifest_mismatch_never_contacts_database(monkeypatch, tmp_path):
    import json
    module = harness()
    store = Mock(side_effect=AssertionError('network attempted'))
    monkeypatch.setattr(module, 'SupabaseHealthyCatalogStore', store)
    monkeypatch.setenv('SUPABASE_URL', 'https://project.example')
    manifest = tmp_path / 'retained.json'
    manifest.write_text(json.dumps({'run_id': 'other', 'project_host': 'project.example'}))
    monkeypatch.setattr(sys, 'argv', ['qualify', '--run-id', '00000000-0000-4000-8000-000000000001',
        '--live', '--project-host', 'project.example', '--output', str(tmp_path / 'report.json'), '--cleanup', str(manifest)])
    assert module.main() == 1
    store.assert_not_called()


def test_paired_replay_obeys_current_image_evidence_gate():
    path = Path(__file__).resolve().parents[1] / 'scripts/evaluate_supabase_localization.py'
    spec = spec_from_file_location('qualification_replay', path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    from raphael_agent.image_pull import image_pull_repair_allowed
    case = {'id': 'image-positive', 'kind': 'image', 'baseline': 'valid',
            'expected_path': 'deploy/app.yaml', 'expected_approval': True}
    state, _ = module.inputs(case)
    signature = state['failure_signature']
    assert state['sandbox_backend'] == 'mock'
    assert signature['normalized']['attributes']['evidence_source'] == 'mock_fixture'
    assert image_pull_repair_allowed(signature, 'mock')
    assert not image_pull_repair_allowed(signature, 'kubernetes')
    report = module.evaluate()
    assert report['summary']['on']['correct_approved_images'] == 2
    assert report['summary']['on']['correct_refusals'] == 6
    assert report['summary']['on']['unsafe_approvals'] == 0


def test_fixture_exercise_uses_mock_gate_without_executor(monkeypatch):
    module = harness()
    from raphael_agent.graph import nodes
    from raphael_agent.localization.supabase_catalog import SupabaseCatalogError

    class FixtureStore:
        def __init__(self):
            self.clients = {}
            self.rows = {}
        def _request(self, method, path, body, prefer):
            assert method == 'POST' and path == 'raphael_clients'
            self.clients[body['client_id']] = {**body, 'status': 'active'}
        def get_client(self, client_id):
            return self.clients[client_id]
        def record_healthy_trace(self, row):
            if row['healthy_trace_id'] not in self.rows and any(
                r['client_id'] == row['client_id'] for r in self.rows.values()
            ):
                raise SupabaseCatalogError('supabase_http_409')
            self.rows[row['healthy_trace_id']] = row
            return row
        def list_healthy_traces(self, **scope):
            return [r for r in self.rows.values() if all(r[k] == v for k, v in scope.items())]

    store = FixtureStore()
    monkeypatch.setattr(nodes, 'SupabaseHealthyCatalogStore', lambda: store)
    monkeypatch.delenv('SUPABASE_PUBLISHABLE_KEY', raising=False)
    monkeypatch.delenv('SUPABASE_ANON_KEY', raising=False)
    report = {'run_id': '00000000-0000-4000-8000-000000000001', 'trace_ids': [], 'checks': {}}
    baseline = {'service_name': 'payments', 'environment': 'qualification', 'operation': 'deploy',
        'repository': 'fixture/payments', 'trace_id': 'synthetic-observation', 'source_commit_sha': 'a' * 40,
        'runtime_identity': {'resource_kind': 'Deployment', 'resource_name': 'payments',
            'namespace': 'qualification', 'cluster': 'fixture',
            'container_images': {'api': 'registry.example/payments@sha256:' + 'b' * 64}}}
    module.exercise(store, report, baseline)
    assert len(report['trace_ids']) == 3
    assert 'graph_image_selection' in report['checks']
    assert 'spoofed_scope_repository_refusal' in report['checks']
