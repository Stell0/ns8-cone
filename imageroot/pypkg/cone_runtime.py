# SPDX-License-Identifier: GPL-3.0-or-later
"""NS8 supervisor adapter for released public C1 operations. No private C1 imports."""
import json
import os
import re
import subprocess
import time
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path

from cone_state import contracts, private_dir, read_json, atomic_write, env_text, write_json

UNITS = ['cone.service', 'cone-postgres.service', 'cone-terminusdb.service',
         'cone-openfga-migrate.service', 'cone-openfga.service']


def run(argv, **kwargs):
    result = subprocess.run(argv, capture_output=True, timeout=360, **kwargs)
    if result.returncode:
        # Provider secrets or tokens must never be included in action errors.
        try:
            category = json.loads(result.stdout).get('error', '')
            if re.fullmatch('[a-z0-9_]{1,100}', category):
                raise RuntimeError('C1 refused operation: ' + category)
        except (ValueError, AttributeError):
            pass
        raise RuntimeError('Operation failed: ' + argv[0] + ' (exit ' + str(result.returncode) + ')')
    return result.stdout


def image():
    reference = os.environ.get('CONE_C1_IMAGE', '')
    if not reference:
        raise RuntimeError('Qualified C1 image is missing; external initialization unavailable')
    info = json.loads(run(['podman', 'image', 'inspect', reference]))[0]
    if info['Id'].removeprefix('sha256:') != contracts()['images']['c1']['config_digest'].removeprefix('sha256:'):
        raise RuntimeError('C1 image configuration digest does not match the released artifact')
    if info['Config'].get('Labels', {}).get('org.opencontainers.image.revision') != contracts()['repositories']['c1']['revision']:
        raise RuntimeError('C1 image revision does not match the pinned release')
    return reference


def container_args(env_name='c1.env'):
    private = private_dir()
    application = private / 'application'
    application.mkdir(mode=0o700, exist_ok=True)
    args = ['podman', 'run', '--rm', '--read-only', '--user', '10001:10001',
            '--cap-drop=ALL', '--security-opt=no-new-privileges', '--pod=cone',
            '--tmpfs=/tmp', '--env-file=' + str(private / env_name),
            '--volume=' + str(application) + ':/var/lib/c1/private:z']
    if (private / 'issuer-ca.pem').exists():
        args += ['--volume=' + str(private / 'issuer-ca.pem') + ':/etc/c1-certs/issuer-ca.pem:ro,z']
    return args


def operator(*arguments, env_name='c1.env'):
    output = run(container_args(env_name) + ['--entrypoint=/opt/c1/bin/c1-admin',
                  image(), 'application', *arguments])
    return json.loads(output)


def ready():
    port = os.environ.get('TCP_PORT', '')
    if not port.isdigit():
        return False
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open('http://127.0.0.1:' + port + '/v1/readyz', timeout=15) as response:
            return response.status == 200
    except Exception:
        return False


def status():
    private = private_dir()
    deployment = read_json(private / 'deployment.json', {})
    state = read_json(private / 'application/initialization.json', {})
    live = ready()
    result = {'configured': live, 'authentication_ready': live, 'bootstrap_ready': bool(state.get('fga_model')),
              'state': 'ready' if live else state.get('state', 'blocked'),
              'blockers': [] if live else ([
                  'Live application readiness is unavailable'
              ] if state.get('state') == 'complete' else [
                  'Enrollment or live application consistency is pending'
              ]),
              'versions': {'c1': contracts()['repositories']['c1']['version'],
                           'c1_revision': contracts()['repositories']['c1']['revision']},
              'idp_provider': deployment.get('settings', {}).get('idp_provider', ''),
              'user_domain': deployment.get('settings', {}).get('user_domain', ''),
              'administration_url': ('https://' + deployment['settings']['host'] +
                                     ('/explorer/' if live else '/explorer/login')) if state else ''}
    if (private / 'restoring.json').exists():
        result.update(configured=False, authentication_ready=False, state='recovery_guarded',
                      blockers=['Explicit namespace continuity and recovery release are required'],
                      administration_url='')
    return result


def register_client(agent, provider, request):
    # The native registration contract preserves the secret and owned mappers.
    # Domain-change federation can race registration in development IdP builds;
    # retry only backend/unavailable exits, never validation/ownership refusals.
    for attempt in range(3):
        response = agent.tasks.run('module/' + provider, action='register-client', data=request)
        if response['exit_code'] == 0:
            return response
        if response['exit_code'] not in (1, 4) or attempt == 2:
            raise RuntimeError('Identity provider rejected client registration')
        time.sleep(attempt + 1)
    raise RuntimeError('Identity provider registration unavailable')


def reconcile():
    import agent
    private = private_dir()
    deployment = read_json(private / 'deployment.json')
    if not deployment:
        raise RuntimeError('Save deployment settings first')
    settings = deployment['settings']
    if (private / 'restoring.json').exists():
        raise RuntimeError('Recovery must be verified and explicitly released before configuration')
    image()
    providers = agent.list_service_providers(agent.redis_connect(use_replica=True), 'oidc', 'http',
                                            {'module_id': settings['idp_provider']})
    if len(providers) != 1 or providers[0]['module_uuid'] != deployment['provider_uuid']:
        raise RuntimeError('Provider namespace changed or unavailable')
    # Pasta copies the host address into the guest; same-node HTTPS must use
    # the host gateway while retaining the original TLS/issuer hostname.
    alias = '--add-host=' + urlsplit(deployment['issuer']).hostname + ':host-gateway' if str(providers[0]['node']) == os.environ['NODE_ID'] else ''
    if os.environ.get('CONE_IDP_HOST_ALIAS', '') != alias:
        agent.set_env('CONE_IDP_HOST_ALIAS', alias)
        run(['systemctl', '--user', 'stop', 'cone-app.service', 'cone.service'])
    bound = agent.get_bound_domain_list(agent.redis_connect(use_replica=True))
    if bound != [settings['user_domain']]:
        agent.bind_user_domains([settings['user_domain']], check=True)
    registration_request = {
        'domain': settings['user_domain'], 'redirect_uris': ['https://' + settings['host'] + '/explorer/callback'],
        'post_logout_redirect_uris': ['https://' + settings['host'] + '/explorer/signed-out'],
        'web_origins': ['https://' + settings['host']],
        'audience': [read_json(private / 'identity.json')['audience']],
        'access_token_claims': {'c1_principal_kind': 'human'}}
    response = register_client(agent, settings['idp_provider'], registration_request)
    registration = response['output']
    if registration['issuer'] != deployment['issuer']:
        raise RuntimeError('Registered issuer does not match the retained namespace')
    previous = read_json(private / 'registration.json')
    if previous and any(previous.get(k) != registration.get(k) for k in ('issuer', 'client_id', 'realm')):
        raise RuntimeError('Identity registration changed; migration is required')
    write_json(private / 'registration.json', registration)
    values = {}
    for line in (private / 'c1.env.pending').read_text().splitlines():
        key, value = line.split('=', 1); values[key] = value
    values.update(C1_IDENTITY_MODE='external', C1_OIDC_CONFIG_VERSION='1', C1_OIDC_TOKEN_PROFILE='c1-v1',
                  C1_INITIALIZATION_FILE='/var/lib/c1/private/initialization.json',
                  C1_LOCK_PATH='/var/lib/c1/private/writer.lock',
                  C1_EXPLORER_CLIENT_ID=registration['client_id'],
                  C1_EXPLORER_CLIENT_SECRET=registration['client_secret'],
                  C1_EXPLORER_LOGOUT_MODE='rp-initiated', C1_EXPLORER_SCOPES='openid',
                  C1_OPERATOR_TIMEOUT_S='300')
    existing = read_json(private / 'application/initialization.json', {})
    for key, state_key in [('C1_FGA_STORE','fga_store'), ('C1_FGA_MODEL','fga_model')]:
        if state_key in existing: values[key] = existing[state_key]
    atomic_write(private / 'c1.env', env_text(values))
    # Stopped dependency units can already be unloaded; reset-failed then
    # returns 1 even though the following ordered start is valid.
    subprocess.run(['systemctl', '--user', 'reset-failed', *UNITS],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    run(['systemctl', '--user', 'start', *UNITS])
    run(['systemctl', '--user', 'stop', 'cone-app.service'])
    contract = operator('contract')
    if contract.get('qualification_release') != 'v' + contracts()['repositories']['c1']['version'] or 'c1-v1' not in contract.get('qualified_token_profiles', []):
        raise RuntimeError('Released C1 contract is not compatible')
    operator('oidc-check')
    initialized = operator('initialize', '--namespace-id', 'ns8:' + deployment['provider_uuid'] + ':' + settings['user_domain'])
    values.update(C1_FGA_STORE=initialized['fga_store'], C1_FGA_MODEL=initialized['fga_model'])
    atomic_write(private / 'c1.env', env_text(values))
    run(['systemctl', '--user', 'enable', 'cone.service', 'cone-app.service'])
    run(['systemctl', '--user', 'reset-failed', 'cone-app.service'])
    run(['systemctl', '--user', 'start', 'cone-app.service'])
    # Setup is guarded inside C1; ordinary operations remain unavailable until confirmation.
    agent.set_route({'instance': os.environ['MODULE_ID'], 'host': settings['host'],
                     'url': 'http://127.0.0.1:' + os.environ['TCP_PORT'],
                     'lets_encrypt': settings['lets_encrypt'], 'http2https': True,
                     'skip_cert_verify': False})
    deployment['state'] = 'initialized'
    write_json(private / 'deployment.json', deployment)
    return status()
