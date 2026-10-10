#!/usr/bin/env python3
"""Real HTTPS OIDC/API acceptance checks; credentials stay in protected files.

Run inside the released C1 image with the module's trusted server configuration.
This performs Authorization Code + S256 exchanges, never a password-grant login.
It uses public C1 HTTP interfaces and contains no private C1 imports.
"""
import argparse
import base64
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import parse_qs, quote, urljoin, urlsplit
import uuid

import httpx


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.forms = []
        self.current = None
        self.links = {}
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == 'form':
            self.current = {'action': attrs.get('action', ''), 'inputs': {}, 'id': attrs.get('id')}
            self.forms.append(self.current)
        elif tag == 'input' and self.current is not None and attrs.get('name'):
            self.current['inputs'][attrs['name']] = attrs.get('value', '')
        elif tag == 'a' and attrs.get('id'):
            self.links[attrs['id']] = attrs.get('href', '')

    def handle_endtag(self, tag):
        if tag == 'form':
            self.current = None


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def request(client, method, path, expected=200, **kwargs):
    response = client.request(method, path, **kwargs)
    require(response.status_code == expected,
            method + ' ' + urlsplit(path).path + ': HTTP ' + str(response.status_code) + ', expected ' + str(expected))
    return response


class Live:
    def __init__(self):
        self.origin = os.environ['C1_EXPLORER_ORIGIN']
        self.issuer = os.environ['C1_ISSUER']
        self.client_id = os.environ['C1_EXPLORER_CLIENT_ID']
        self.client_secret = os.environ['C1_EXPLORER_CLIENT_SECRET']
        credential_path = Path(os.environ['CONE_TEST_CREDENTIALS_FILE'])
        require(credential_path.stat().st_mode & 0o077 == 0, 'Unsafe credential-file mode')
        self.credentials = json.loads(credential_path.read_text())
        self.results = {}
        self.base = httpx.Client(base_url=self.origin, trust_env=False, timeout=90)
        metadata = request(self.base, 'GET', self.issuer + '/.well-known/openid-configuration').json()
        require(metadata['issuer'] == self.issuer, 'Discovery issuer mismatch')
        self.metadata = metadata
        self.results['exact_issuer_tls_discovery'] = 'PASS'

    def code(self, user, wrong_verifier=False):
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(24)
        callback = self.origin + '/explorer/callback'
        with httpx.Client(trust_env=False, timeout=60, follow_redirects=False) as client:
            response = client.get(self.metadata['authorization_endpoint'], params={
                'client_id': self.client_id, 'redirect_uri': callback,
                'response_type': 'code', 'scope': 'openid', 'state': state,
                'nonce': nonce, 'code_challenge': challenge, 'code_challenge_method': 'S256'})
            for _ in range(12):
                location = response.headers.get('location', '')
                if location:
                    destination = urljoin(str(response.url), location)
                    params = parse_qs(urlsplit(destination).query)
                    if destination.startswith(callback + '?') and 'code' in params:
                        require(params.get('state') == [state], 'Authorization state mismatch')
                        issued = client.post(self.metadata['token_endpoint'],
                            auth=(self.client_id, self.client_secret), data={
                                'grant_type': 'authorization_code', 'code': params['code'][0],
                                'redirect_uri': callback,
                                'code_verifier': secrets.token_urlsafe(48) if wrong_verifier else verifier})
                        require(issued.status_code == (400 if wrong_verifier else 200), 'Code exchange rejected or invalid PKCE accepted')
                        return issued.json()
                    require(urlsplit(destination).netloc == urlsplit(self.issuer).netloc,
                            'Untrusted provider redirect')
                    response = client.get(destination)
                else:
                    page = Page(response.text)
                    forms = [f for f in page.forms if 'username' in f['inputs']]
                    require(len(forms) == 1, 'Provider did not expose the expected login form')
                    form = forms[0]
                    action = urljoin(str(response.url), form['action'])
                    require(action.startswith(self.issuer + '/'), 'Untrusted login form')
                    fields = {**form['inputs'], 'username': user, 'password': self.credentials[user]}
                    fields.pop('credentialId', None)
                    response = client.post(action, data=fields)
        raise RuntimeError('Provider redirect limit exceeded')

    def auth(self):
        self.tokens = {user: self.code(user) for user in ('foo1', 'foo2')}
        self.headers = {user: {'Authorization': 'Bearer ' + pair['access_token']}
                        for user, pair in self.tokens.items()}
        self.identities = {}
        for user in self.tokens:
            who = request(self.base, 'GET', '/v1/whoami', headers=self.headers[user]).json()
            require(who['kind'] == 'human', 'Wrong principal classification')
            require(len(who['subject']) == 36 and all(c in '0123456789abcdef-' for c in who['subject']), 'Expected UUID subject in this fixture')
            who['principal'] = 'user:' + who['issuer_alias'] + '.' + who['subject']
            self.identities[user] = who
            request(self.base, 'GET', '/v1/whoami', expected=401,
                    headers={'Authorization': 'Bearer ' + self.tokens[user]['id_token']})
        self.results['two_real_user_code_pkce_logins'] = 'PASS'
        self.results['id_tokens_rejected_by_api'] = 'PASS'
        request(self.base, 'GET', '/v1/whoami', expected=401)
        request(self.base, 'GET', '/v1/whoami', expected=401,
                headers={'Authorization': 'Bearer invalid.invalid.invalid'})
        request(self.base, 'GET', '/v1/whoami', expected=401,
                headers={'X-Forwarded-User': 'foo1', 'X-Remote-User': 'foo1'})
        self.results['missing_invalid_forwarded_identity_rejected'] = 'PASS'
        require('access_token' not in self.code('foo2', wrong_verifier=True), 'Invalid PKCE accepted')
        self.results['invalid_pkce_rejected'] = 'PASS'
        for grant in ('password', 'client_credentials'):
            response = self.base.post(self.metadata['token_endpoint'],
                auth=(self.client_id, self.client_secret), data={
                    'grant_type': grant, 'username': 'foo2', 'password': self.credentials['foo2']})
            require(response.status_code in (400, 401) and 'access_token' not in response.json(),
                    'Unsupported grant accepted')
        self.results['unsupported_grants_rejected'] = 'PASS'
        for user, pair in self.tokens.items():
            if 'refresh_token' in pair:
                response = request(self.base, 'POST', self.metadata['token_endpoint'],
                    auth=(self.client_id, self.client_secret), data={
                        'grant_type': 'refresh_token', 'refresh_token': pair['refresh_token']}).json()
                request(self.base, 'GET', '/v1/whoami',
                        headers={'Authorization': 'Bearer ' + response['access_token']})
        self.results['provider_refresh'] = 'PASS'
        request(self.base, 'POST', '/v1/access-scopes', expected=403,
                headers=self.headers['foo2'], json={'label': 'Denied user scope'})
        request(self.base, 'POST', '/v1/instance/grants', expected=403,
                headers=self.headers['foo2'], json={'member': self.identities['foo2']['principal'], 'role': 'access_admin'})
        self.results['normal_user_denied_administration'] = 'PASS'

    def enroll(self):
        # A wrong first login must not consume the exact approved identity.
        with httpx.Client(base_url=self.origin, trust_env=False, timeout=90,
                          follow_redirects=False) as client:
            for user in ('foo2', 'foo1'):
                client.cookies.clear()
                response = client.get('/explorer/login')
                for _ in range(15):
                    location = response.headers.get('location', '')
                    if location:
                        target = urljoin(str(response.url), location)
                        require(urlsplit(target).netloc in {urlsplit(self.origin).netloc, urlsplit(self.issuer).netloc}, 'Untrusted enrollment redirect')
                        response = client.get(target)
                    else:
                        page = Page(response.text)
                        if urlsplit(str(response.url)).path == '/explorer/callback':
                            if user == 'foo2':
                                require(response.status_code == 400, 'Wrong identity accepted for enrollment')
                                self.results['wrong_first_login_rejected'] = 'PASS'
                                break
                            require(response.status_code == 200 and 'continue' in page.links, 'Approved enrollment callback failed')
                            response = request(client, 'GET', page.links['continue'])
                            form = next(f for f in Page(response.text).forms if f['action'] == '/explorer/enroll')
                            request(client, 'POST', '/explorer/enroll', expected=303,
                                    data=form['inputs'], headers={'Origin': self.origin})
                            request(self.base, 'GET', '/v1/readyz')
                            self.results['explicit_foo1_enrollment'] = 'PASS'
                            return
                        forms = [f for f in page.forms if 'username' in f['inputs']]
                        require(len(forms) == 1, 'Enrollment login form unavailable')
                        form = forms[0]
                        action = urljoin(str(response.url), form['action'])
                        require(action.startswith(self.issuer + '/'), 'Untrusted enrollment form')
                        fields = {**form['inputs'], 'username': user, 'password': self.credentials[user]}
                        fields.pop('credentialId', None)
                        response = client.post(action, data=fields)
                else:
                    raise RuntimeError('Enrollment redirect limit exceeded')
        raise RuntimeError('Approved enrollment did not complete')

    def explorer(self, user):
        with httpx.Client(base_url=self.origin, trust_env=False, timeout=90,
                          follow_redirects=False) as client:
            response = client.get('/explorer/login')
            for _ in range(15):
                location = response.headers.get('location', '')
                if location:
                    target = urljoin(str(response.url), location)
                    require(urlsplit(target).netloc in {urlsplit(self.origin).netloc, urlsplit(self.issuer).netloc}, 'Untrusted Explorer redirect')
                    response = client.get(target)
                else:
                    page = Page(response.text)
                    if 'continue' in page.links:
                        require(response.status_code == 200, 'Explorer callback failed')
                        break
                    forms = [f for f in page.forms if 'username' in f['inputs']]
                    require(len(forms) == 1, 'Explorer login did not complete')
                    form = forms[0]
                    fields = {**form['inputs'], 'username': user, 'password': self.credentials[user]}
                    fields.pop('credentialId', None)
                    action = urljoin(str(response.url), form['action'])
                    require(action.startswith(self.issuer + '/'), 'Untrusted Explorer login form')
                    response = client.post(action, data=fields)
            else:
                raise RuntimeError('Explorer redirect limit exceeded')
            for path in ['/explorer/', '/explorer/documents', '/explorer/context',
                         '/explorer/software', '/explorer/scopes', '/explorer/operations']:
                r = request(client, 'GET', path)
                require('Bad Gateway' not in r.text, 'Explorer gateway error')
                require(r.headers.get('content-security-policy'), 'Missing browser security headers')
            request(client, 'POST', '/explorer/scopes/create', expected=403,
                    data={'label': 'Missing CSRF'}, headers={'Origin': self.origin})
            self.results[user + '_explorer_pages_security_csrf'] = 'PASS'
            page = Page(request(client, 'GET', '/explorer/').text)
            form = next(f for f in page.forms if f['action'] == '/explorer/logout')
            request(client, 'POST', '/explorer/logout', expected=200, data=form['inputs'], headers={'Origin': self.origin})
            request(client, 'GET', '/explorer/', expected=303)
            self.results[user + '_local_logout'] = 'PASS'

    def api(self, user, method, path, expected=200, **kwargs):
        token = self.tokens[user]['access_token']
        payload = json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '=='))
        import time
        if payload['exp'] - time.time() < 90:
            refreshed = request(self.base, 'POST', self.metadata['token_endpoint'],
                auth=(self.client_id, self.client_secret), data={
                    'grant_type': 'refresh_token', 'refresh_token': self.tokens[user]['refresh_token']}).json()
            self.tokens[user].update(refreshed)
            self.headers[user]['Authorization'] = 'Bearer ' + refreshed['access_token']
        return request(self.base, method, path, expected=expected, headers=self.headers[user], **kwargs)

    def change(self, operations, label, author="foo1", reviewer="foo2"):
        base = self.api(author, 'GET', '/v1/instance').json()['knowledge_revision']
        self.api(author, 'GET', '/v1/whoami')
        response = request(self.base, 'POST', '/v1/changesets', expected=201,
            headers={**self.headers[author], 'Idempotency-Key': uuid.uuid4().hex},
            json={'base_revision': base, 'rationale': label, 'operations': operations})
        change = response.json()['id']
        result = self.api(author, 'POST', '/v1/changesets/' + change + '/submit')
        if result.json()['state'] == 'submitted':
            result = self.api(author, 'POST', '/v1/changesets/' + change + '/validate')
        if result.json()['state'] != 'validated':
            report = self.api(author, 'GET', '/v1/changesets/' + change + '/validation').json()
            raise RuntimeError('ChangeSet validation: ' + ','.join(d['code'] for d in report.get('diagnostics', [])))
        if os.environ.get('C1_INDEPENDENT_REVIEW') == 'true':
            self.api(author, 'POST', '/v1/changesets/' + change + '/approve', expected=403)
            self.results['independent_review_self_approval_denied'] = 'PASS'
        self.api(reviewer, 'POST', '/v1/changesets/' + change + '/approve')
        self.api(author, 'GET', '/v1/whoami')  # refresh if needed before idempotent apply
        key = uuid.uuid4().hex
        headers = {**self.headers[author], 'Idempotency-Key': key}
        applied = request(self.base, 'POST', '/v1/changesets/' + change + '/apply', headers=headers)
        require(applied.json()['state'] == 'applied', 'ChangeSet apply did not complete')
        repeated = request(self.base, 'POST', '/v1/changesets/' + change + '/apply', headers=headers)
        require({k:v for k,v in repeated.json().items() if k != 'replayed'} ==
                {k:v for k,v in applied.json().items() if k != 'replayed'},
                'Idempotent apply changed its receipt')
        require(applied.json()['author'] == self.identities[author]['principal'], 'ChangeSet attribution mismatch')
        return change

    def workflow(self):
        scope = self.api('foo1', 'POST', '/v1/access-scopes', expected=201,
                         json={'label': 'NS8 acceptance ' + uuid.uuid4().hex[:10]}).json()['id']
        for user, roles in [('foo1', ('reader','creator','contributor','reviewer')),
                            ('foo2', ('reader','reviewer'))]:
            for role in roles:
                self.api('foo1', 'POST', '/v1/access-scopes/' + scope + '/members',
                         json={'member': self.identities[user]['principal'], 'role': role})
        self.results['administrator_scope_and_least_privilege_grants'] = 'PASS'
        entity = os.environ['C1_INSTANCE_IRI_BASE'] + 'entity/' + str(uuid.uuid4())
        label = 'NS8 reviewed synthetic entity'
        record = {'id': entity, 'types': ['urn:c1:ns:core#Entity'], 'properties': {
            'http://www.w3.org/2004/02/skos/core#prefLabel': [
                {'lexical':label, 'datatype':'http://www.w3.org/1999/02/22-rdf-syntax-ns#langString','language':'en'}],
            'urn:c1:ns:core#lifecycle': [{'lexical':'active','datatype':'http://www.w3.org/2001/XMLSchema#string'}]}}
        path = '/v1/resources/' + quote(entity, safe='')
        self.api('foo2', 'GET', path, expected=404)
        self.change([{'kind':'create','record':record,'scope_id':scope}], 'Real external OIDC acceptance create')
        self.api('foo2', 'GET', path)
        context_request = {'profile':'graph-context','profile_version':'1','anchor':{'id':entity}}
        context = self.api('foo2', 'POST', '/v1/context', json=context_request).json()
        require(label in context['markdown'], 'Authorized context missing the entity')
        self.results['reviewed_changeset_create_read_context'] = 'PASS'
        base = self.api('foo1','GET','/v1/instance').json()['knowledge_revision']
        refused_record = {**record, 'id':os.environ['C1_INSTANCE_IRI_BASE'] + 'entity/' + str(uuid.uuid4())}
        denied_draft = request(self.base,'POST','/v1/changesets',expected=201,
                headers={**self.headers['foo2'],'Idempotency-Key':uuid.uuid4().hex},
                json={'base_revision':base,'rationale':'Denied creation','operations':[{'kind':'create','record':refused_record,'scope_id':scope}]}).json()['id']
        self.api('foo2','POST','/v1/changesets/'+denied_draft+'/submit',expected=403)
        self.api('foo2','GET','/v1/resources/'+quote(refused_record['id'],safe=''),expected=404)
        self.results['read_only_user_denied_creation'] = 'PASS'
        for role in ('creator','contributor'):
            self.api('foo1','POST','/v1/access-scopes/'+scope+'/members',json={'member':self.identities['foo2']['principal'],'role':role})
        record['properties']['http://www.w3.org/2004/02/skos/core#prefLabel'][0]['lexical'] = label + ' corrected'
        self.change([{'kind':'replace','resource_id':entity,'record':record,'reason':'Synthetic reviewed correction'}], 'Real external OIDC acceptance modify', author='foo2', reviewer='foo1')
        require('corrected' in self.api('foo2','GET',path).text, 'Reviewed modification missing')
        self.results['normal_user_reviewed_modify_attribution_idempotent_apply'] = 'PASS'
        revoke = '/v1/access-scopes/' + scope + '/members/' + quote(self.identities['foo2']['principal'],safe='')
        self.api('foo1','DELETE',revoke,params={'role':'reader'})
        # Keep the exact existing token: revocation is effective on the next request.
        request(self.base,'GET',path,expected=404,headers=self.headers['foo2'])
        hidden = request(self.base,'POST','/v1/context',expected=404,headers=self.headers['foo2'],json=context_request)
        require(label not in hidden.text and entity not in hidden.text, 'Revoked content leaked into context')
        self.results['revocation_next_request_and_context_no_leak'] = 'PASS'
        self.api('foo1','POST','/v1/access-scopes/'+scope+'/members',json={'member':self.identities['foo2']['principal'],'role':'reader'})
        self.api('foo2','GET',path)
        # foo2 remains a normal account: scope-level review is not administration.
        self.api('foo2','POST','/v1/access-scopes',expected=403,json={'label':'Denied after grant'})
        self.results['normal_user_stays_non_administrator'] = 'PASS'
        self.fixture = {'scope':scope,'entity':entity,'changeset_label':label}

    def run(self, mode):
        if mode == 'enroll':
            self.enroll()
            return {'results': self.results}
        self.auth()
        if mode != 'workflow':
            self.explorer('foo1')
            self.explorer('foo2')
        if mode in ('full','workflow'):
            self.workflow()
        return {'results': self.results, 'principals': self.identities, 'fixture': getattr(self, 'fixture', {})}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['enroll', 'auth', 'workflow', 'full'], default='auth')
    args = parser.parse_args()
    try:
        suite = Live()
        print(json.dumps(suite.run(args.mode), sort_keys=True))
        return 0
    except Exception as error:
        # URLs/cookies/token responses may contain credentials: never print them.
        print(json.dumps({'result': 'FAIL', 'error_type': type(error).__name__,
                          'error': str(error) if isinstance(error, RuntimeError) else 'HTTP or parsing failure'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
