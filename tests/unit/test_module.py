"""Local safety checks; these do not establish interoperability."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import jsonschema

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'imageroot/pypkg'))
import cone_state
import cone_runtime

class ModuleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'AGENT_STATE_DIR': str(self.state), 'AGENT_INSTALL_DIR': str(ROOT / 'imageroot')})
        self.env.start(); self.addCleanup(self.env.stop)

    def run_step(self, action, step, request=None):
        output = io.StringIO()
        with patch('sys.stdin', io.StringIO(json.dumps(request))), contextlib.redirect_stdout(output):
            runpy.run_path(str(ROOT / 'imageroot/actions' / action / step), run_name='__main__')
        return json.loads(output.getvalue()) if output.getvalue() else None

    def initialize(self):
        self.run_step('create-module', '10prepare_private', {})

    def test_create_retry_preserves_identity_and_credentials(self):
        self.initialize()
        private = self.state / 'private'
        before = {p.name: p.read_bytes() for p in private.iterdir() if p.name != '.lock'}
        self.initialize()
        self.assertEqual(before, {p.name: p.read_bytes() for p in private.iterdir() if p.name != '.lock'})
        self.assertEqual(private.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in private.iterdir()))

    def test_two_instances_do_not_share_identity_or_credentials(self):
        self.initialize()
        first = cone_state.read_json(self.state / 'private/identity.json')
        secret = cone_state.read_json(self.state / 'private/credentials.json')
        with tempfile.TemporaryDirectory() as other, patch.dict(os.environ, {'AGENT_STATE_DIR': other}):
            self.initialize()
            self.assertNotEqual(first['instance_id'], cone_state.read_json(Path(other) / 'private/identity.json')['instance_id'])
            self.assertNotEqual(first['audience'], cone_state.read_json(Path(other) / 'private/identity.json')['audience'])
            self.assertNotEqual(secret, cone_state.read_json(Path(other) / 'private/credentials.json'))

    def test_environment_cannot_inject_an_entry(self):
        for value in ('a\nEVIL=true', 'a\rb', 'a\0b'):
            with self.assertRaises(ValueError): cone_state.env_text({'C1_ISSUER': value})
        self.assertEqual(cone_state.env_text({'A': '$() # x="y"'}), 'A=$() # x="y"\n')

    def test_output_never_contains_private_credentials(self):
        self.initialize()
        output = self.run_step('get-configuration', '20read')
        secrets = cone_state.read_json(self.state / 'private/credentials.json')
        for value in secrets.values(): self.assertNotIn(value, json.dumps(output))
        self.assertFalse(output['configured'])
        self.assertEqual(output['administration_url'], '')
        self.assertNotIn('issuer_ca_pem', output['settings'])
        schema = json.loads((ROOT / 'imageroot/actions/get-configuration/validate-output.json').read_text())
        jsonschema.validate(output, schema)
        status = self.run_step('get-integration-status', '20read')
        status_schema = json.loads((ROOT / 'imageroot/actions/get-integration-status/validate-output.json').read_text())
        jsonschema.validate(status, status_schema)
        self.assertFalse(status['authentication_ready'])
        self.assertFalse(status['bootstrap_ready'])

    def test_schema_rejects_injection_unknown_keys_and_invalid_bounds(self):
        schema = json.loads((ROOT / 'imageroot/actions/configure-module/validate-input.json').read_text())
        valid = {**cone_state.DEFAULTS, 'host': 'app.example.org', 'idp_provider': 'idp1', 'user_domain': 'users.example.org'}
        jsonschema.validate(valid, schema)
        for key,value in [('host','app.example.org\nC1_ENABLE_PROBE_ROUTES=true'), ('backend_timeout_s',0), ('query_candidate_limit',5001), ('session_idle_s',True), ('C1_CRASH_AFTER','commit')]:
            with self.subTest(key=key), self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate({**valid,key:value},schema)
        self.assertEqual(cone_state.validate_settings({**valid,'session_max_s':60}), ('session_max_s','session_max_before_idle'))

    def test_atomic_write_failure_preserves_previous_file(self):
        path = self.state / 'config'
        cone_state.atomic_write(path, 'working')
        with patch('cone_state.os.replace', side_effect=OSError('failure')):
            with self.assertRaises(OSError): cone_state.atomic_write(path, 'candidate')
        self.assertEqual(path.read_text(), 'working')
        self.assertFalse(list(self.state.glob('.pending-*')))

    def test_pinned_release_guard_cannot_be_overridden_by_receipt(self):
        self.initialize()
        cone_state.write_json(self.state / 'private/bootstrap-receipt.json', {'ready':True})
        result = subprocess.run([sys.executable, str(ROOT / 'imageroot/bin/check-production-contract')], env={**os.environ,'PYTHONPATH':str(ROOT/'imageroot/pypkg')}, capture_output=True, text=True)
        self.assertEqual(result.returncode,4)
        self.assertIn('Qualified C1 image is missing',result.stderr)
        self.assertEqual(result.stdout,'')

    def test_draft_retry_preserves_credentials_and_never_calls_registration(self):
        self.initialize()
        private = self.state / "private"
        before = (private / "credentials.json").read_bytes()
        settings = {**cone_state.DEFAULTS, "host": "app.example.org", "idp_provider": "idp1", "user_domain": "users.example.org"}
        provider = {"module_uuid": "provider-1", "issuer_url_prefix": "https://sso.example.org/realms/"}
        sdk = types.ModuleType("agent")
        sdk.redis_connect = lambda **kw: object()
        sdk.list_service_providers = lambda *args: [provider]
        def assert_exp(condition, message):
            if not condition: raise RuntimeError(message)
        sdk.assert_exp = assert_exp
        with patch.dict(sys.modules, {"agent": sdk}):
            result = self.run_step("configure-module", "20save_draft", settings)
            first = (private / "c1.env.pending").read_bytes()
            self.run_step("configure-module", "20save_draft", settings)
            self.assertEqual(first, (private / "c1.env.pending").read_bytes())
            self.assertIsNone(result)
            with self.assertRaisesRegex(RuntimeError, "migration"):
                self.run_step("configure-module", "20save_draft", {**settings, "user_domain": "other.example.org"})
            self.assertEqual(first, (private / "c1.env.pending").read_bytes())
        self.assertEqual(before, (private / "credentials.json").read_bytes())
        self.assertFalse((private / "c1.env").exists())
        self.assertNotIn("C1_FGA_STORE=", first.decode())
        self.assertNotIn("C1_EXPLORER_CLIENT_SECRET=", first.decode())

    def test_configuration_pipeline_emits_one_valid_json_result(self):
        self.initialize()
        settings = {**cone_state.DEFAULTS, "host": "app.example.org", "idp_provider": "idp1", "user_domain": "users.example.org"}
        sdk = types.ModuleType("agent")
        sdk.redis_connect = lambda **kw: object()
        sdk.list_service_providers = lambda *args: [{"module_uuid": "provider-1", "issuer_url_prefix": "https://sso.example.org/realms/"}]
        def assert_exp(condition, message):
            if not condition: raise RuntimeError(message)
        sdk.assert_exp = assert_exp
        output = io.StringIO()
        with patch.dict(sys.modules, {"agent": sdk}), patch("sys.stdin", io.StringIO(json.dumps(settings))), contextlib.redirect_stdout(output), patch("cone_runtime.reconcile", return_value={"configured": True, "state": "ready", "blockers": []}):
            for step in ["20save_draft", "80reconcile"]:
                runpy.run_path(str(ROOT / "imageroot/actions/configure-module" / step), run_name="__main__")
        value = json.loads(output.getvalue())
        schema = json.loads((ROOT / "imageroot/actions/configure-module/validate-output.json").read_text())
        jsonschema.validate(value, schema)
        self.assertTrue(value["configured"])
        before = (self.state / "private/deployment.json").read_bytes()
        for marker in ["restoring.json", "backup-operation.json"]:
            path = self.state / "private" / marker
            path.write_text("{}")
            with patch.dict(sys.modules, {"agent": sdk}):
                with self.assertRaisesRegex(RuntimeError, "maintenance"):
                    self.run_step("configure-module", "20save_draft", settings)
            self.assertEqual(before, (self.state / "private/deployment.json").read_bytes())
            path.unlink()

    def test_provider_event_only_records_the_selected_provider(self):
        self.initialize()
        private = self.state / "private"
        cone_state.write_json(private / "deployment.json", {"provider_uuid": "selected"})
        step = ROOT / "imageroot/events/service-oidc-changed/10guard"
        with patch("sys.stdin", io.StringIO('{"module_uuid":"other"}')):
            with self.assertRaises(SystemExit) as error: runpy.run_path(str(step), run_name="__main__")
        self.assertEqual(error.exception.code, 0)
        self.assertFalse((private / "reconciliation.json").exists())
        for _ in range(2):
            with patch("sys.stdin", io.StringIO('{"module_uuid":"selected"}')):
                runpy.run_path(str(step), run_name="__main__")
        self.assertEqual(cone_state.read_json(private / "reconciliation.json"), {"state": "blocked", "reason": "provider_changed"})

    def test_changed_runtime_image_is_rejected(self):
        info = {'Id': 'sha256:' + '0' * 64, 'Config': {'Labels': {}}}
        with patch.dict(os.environ, {'CONE_C1_IMAGE': 'example.invalid/c1:pinned'}), patch('cone_runtime.run', return_value=json.dumps([info])):
            with self.assertRaisesRegex(RuntimeError, 'digest'):
                cone_runtime.image()
        lock = cone_state.contracts()
        info['Id'] = lock['images']['c1']['config_digest']
        with patch.dict(os.environ, {'CONE_C1_IMAGE': 'example.invalid/c1:pinned'}), patch('cone_runtime.run', return_value=json.dumps([info])):
            with self.assertRaisesRegex(RuntimeError, 'revision'):
                cone_runtime.image()

    def test_receipt_and_initialization_cannot_report_live_readiness(self):
        self.initialize()
        private = self.state / 'private'
        cone_state.write_json(private / 'deployment.json', {'settings': {'host': 'app.example.org'}})
        cone_state.write_json(private / 'application/initialization.json', {'state': 'approved', 'fga_model': 'model'})
        cone_state.write_json(private / 'bootstrap-receipt.json', {'ready': True})
        with patch('cone_runtime.ready', return_value=False):
            status = cone_runtime.status()
        self.assertFalse(status['configured'])
        self.assertTrue(status['bootstrap_ready'])
        self.assertEqual(status['administration_url'], 'https://app.example.org/explorer/login')
        cone_state.write_json(private / 'restoring.json', {'guard': True})
        with patch('cone_runtime.ready', return_value=True):
            status = cone_runtime.status()
        self.assertFalse(status['configured'])
        self.assertFalse(status['authentication_ready'])
        self.assertEqual(status['administration_url'], '')

    def test_command_errors_do_not_expose_provider_secrets(self):
        failure = subprocess.CompletedProcess(['provider'], 1, b'client_secret=private', b'access_token=private')
        with patch('cone_runtime.subprocess.run', return_value=failure):
            with self.assertRaisesRegex(RuntimeError, r'Operation failed: provider \(exit 1\)') as error:
                cone_runtime.run(['provider'])
        self.assertNotIn('private', str(error.exception))

    def test_readiness_probe_uses_bounded_timeout_and_no_proxy(self):
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value.status = 200
        opener = MagicMock()
        opener.open.return_value = response
        with patch.dict(os.environ, {'TCP_PORT': '20038'}), patch('cone_runtime.urllib.request.build_opener', return_value=opener):
            self.assertTrue(cone_runtime.ready())
        opener.open.assert_called_once_with('http://127.0.0.1:20038/v1/readyz', timeout=15)

    def test_native_restore_fails_before_overwriting_state(self):
        result = subprocess.run(['bash', str(ROOT / 'imageroot/actions/restore-module/00contract_guard')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 4)
        self.assertIn('not qualified', result.stderr)
        self.assertEqual(result.stdout, '')

    def test_registration_retry_is_bounded_and_refusals_are_final(self):
        from unittest.mock import MagicMock
        sdk = MagicMock()
        request = {'domain': 'users.example.org', 'rotate_secret': False}
        sdk.tasks.run.side_effect = [
            {'exit_code': 1}, {'exit_code': 0, 'output': {'client_id': 'cone1'}}]
        with patch('cone_runtime.time.sleep'):
            result = cone_runtime.register_client(sdk, 'idp1', request)
        self.assertEqual(result['output']['client_id'], 'cone1')
        self.assertEqual(sdk.tasks.run.call_count, 2)
        self.assertTrue(all(call.kwargs['data'] is request for call in sdk.tasks.run.call_args_list))
        sdk.tasks.run.reset_mock()
        sdk.tasks.run.side_effect = [{'exit_code': 3}]
        with self.assertRaises(RuntimeError):
            cone_runtime.register_client(sdk, 'idp1', request)
        self.assertEqual(sdk.tasks.run.call_count, 1)
        sdk.tasks.run.reset_mock()
        sdk.tasks.run.side_effect = [{'exit_code': 4}] * 3
        with patch('cone_runtime.time.sleep'), self.assertRaises(RuntimeError):
            cone_runtime.register_client(sdk, 'idp1', request)
        self.assertEqual(sdk.tasks.run.call_count, 3)

    def test_packaged_lock_matches_repository(self):
        self.assertEqual((ROOT / 'integration-lock.json').read_bytes(), (ROOT / 'imageroot/etc/integration-lock.json').read_bytes())
        lock = json.loads((ROOT / 'integration-lock.json').read_text())
        for name in ('postgres','terminusdb','openfga'):
            self.assertRegex(lock['images'][name]['reference'], r'@sha256:[a-f0-9]{64}$')

if __name__ == '__main__': unittest.main()
