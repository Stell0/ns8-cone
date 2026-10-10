# SPDX-License-Identifier: GPL-3.0-or-later
"""Protected supervisor transport for same-instance application recovery.

Only public C1 commands validate/release application state. This module manages
fresh backend volumes and keeps the old generation available to the operator.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tarfile
import uuid

from cone_runtime import UNITS, image, operator, run
from cone_state import atomic_write, env_text, private_dir, read_json, write_json

ARTIFACTS = {'initialization.json', 'openfga.pgdump', 'terminusdb-storage.tar'}


def volumes():
    values = dict(line.split('=', 1) for line in
                  (private_dir() / 'volumes.env').read_text().splitlines())
    for key, prefix in [('CONE_POSTGRES_VOLUME', 'cone-pgdata'),
                        ('CONE_TERMINUS_VOLUME', 'cone-terminus-data')]:
        if not re.fullmatch(re.escape(prefix) + r'(?:-restore-[a-f0-9]{32})?', values.get(key, '')):
            raise ValueError('invalid_backend_volume')
    if len(values) != 2:
        raise ValueError('invalid_backend_volume')
    return values


def protected(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise ValueError('unsafe_recovery_file')
    return path


def sha256(path):
    protected(path)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def manifest(directory):
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise ValueError('unsafe_recovery_directory')
    if {p.name for p in directory.iterdir()} != ARTIFACTS | {'manifest.json'}:
        raise ValueError('incomplete_backup_directory')
    value = json.loads(protected(directory / 'manifest.json').read_text())
    if value.get('contract_version') != 1 or value.get('manifest_version') != 2 or value.get('type') != 'external-full' or set(value.get('files', {})) != ARTIFACTS:
        raise ValueError('incompatible_backup_manifest')
    if any(sha256(directory / name) != digest for name, digest in value['files'].items()):
        raise ValueError('backup_integrity_failure')
    # The initial qualified transport accepts regular files/directories only.
    # Reject links/devices/traversal before invoking tar in a fresh volume.
    with tarfile.open(directory / 'terminusdb-storage.tar', 'r:') as archive:
        for index, item in enumerate(archive):
            path = PurePosixPath(item.name)
            if index > 1_000_000 or path.is_absolute() or '..' in path.parts or not (item.isfile() or item.isdir()):
                raise ValueError('unsafe_storage_archive')
    return value


def ensure_owned_volumes(guard, digest):
    for role, reference in guard['new_volumes'].items():
        step = {'CONE_POSTGRES_VOLUME':'postgres', 'CONE_TERMINUS_VOLUME':'terminus'}[role]
        info = subprocess.run(['podman','volume','inspect',reference],capture_output=True,timeout=30)
        if info.returncode:
            if step in guard['steps']:
                raise ValueError('owned_recovery_volume_missing')
            run(['podman','volume','create','--label=c1.recovery='+digest,reference])
        else:
            metadata = json.loads(info.stdout)[0]
            if metadata.get('Labels', {}).get('c1.recovery') != digest:
                raise ValueError('ambiguous_recovery_volume')


def restore(directory, operator_name):
    private = private_dir()
    if (private / 'backup-operation.json').exists():
        raise ValueError('backup_cleanup_required')
    value = manifest(directory)
    existing = read_json(private / 'application/initialization.json', {})
    candidate = read_json(directory / 'initialization.json')
    if not candidate or candidate.get('identity') != value['identity']:
        raise ValueError('restored_identity_mismatch')
    if existing and existing.get('identity') != value['identity']:
        raise ValueError('same_instance_recovery_required')
    env = dict(line.split('=', 1) for line in (private / 'c1.env').read_text().splitlines())
    if env.get('C1_EXPLORER_CLIENT_ID') != os.environ['MODULE_ID']:
        raise ValueError('client_ownership_migration_required')
    identity = value['identity']
    if any(env.get(setting) != identity.get(field) for setting, field in [
        ('C1_INSTANCE_ID','instance_id'), ('C1_INSTANCE_IRI_BASE','instance_base'),
        ('C1_ISSUER_ALIAS','issuer_alias'), ('C1_ISSUER','issuer'),
        ('C1_AUDIENCE','audience'), ('C1_EXPLORER_CLIENT_ID','explorer_client_id')]):
        raise ValueError('restored_identity_mismatch')
    image()
    digest = sha256(directory / 'manifest.json')
    guard = read_json(private / 'restoring.json')
    if guard and guard['manifest_sha256'] != digest:
        raise ValueError('different_recovery_in_progress')
    if guard is None:
        generation = uuid.uuid4().hex
        guard = {'contract_version':1, 'manifest_sha256':digest,
                 'snapshot_created_at':value['created_at'], 'operator':operator_name,
                 'directory':str(directory), 'old_volumes':volumes(),
                 'new_volumes':{'CONE_POSTGRES_VOLUME':'cone-pgdata-restore-'+generation,
                                'CONE_TERMINUS_VOLUME':'cone-terminus-data-restore-'+generation},
                 'steps':[]}
        write_json(private / 'restoring.json', guard)  # Intent before durable resource mutation.
    run(['systemctl','--user','stop','cone-app.service', *reversed(UNITS)])
    ensure_owned_volumes(guard, digest)
    term = guard['new_volumes']['CONE_TERMINUS_VOLUME']
    if 'terminus' not in guard['steps']:
        # Repeating a tar import in this owned, unpublished generation is safe.
        with (directory / 'terminusdb-storage.tar').open('rb') as data:
            result = subprocess.run(['podman','run','--rm','-i','--network=none',
                # The cone pod shares this mapping across every backend.
                # Match it even though this import runs outside the pod.
                '--userns=keep-id:uid=10001,gid=10001','--user=0',
                '--volume='+term+':/target:z','--entrypoint=/bin/tar',image(),
                '-xf','-','-C','/target'],stdin=data,capture_output=True,timeout=180)
        if result.returncode:
            raise RuntimeError('storage_import_failed')
        guard['steps'].append('terminus'); write_json(private/'restoring.json',guard)
    atomic_write(private/'volumes.env',env_text(guard['new_volumes']))
    subprocess.run(['systemctl','--user','reset-failed',*UNITS],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
    run(['systemctl','--user','daemon-reload'])
    run(['systemctl','--user','start','cone.service','cone-postgres.service'])
    if 'postgres' not in guard['steps']:
        with (directory/'openfga.pgdump').open('rb') as data:
            result = subprocess.run(['podman','exec','-i','--user=postgres','cone-postgres',
                'pg_restore','-U','openfga','-d','openfga','--clean','--if-exists','--no-owner'],
                stdin=data,capture_output=True,timeout=180)
        if result.returncode:
            raise RuntimeError('authorization_import_failed')
        guard['steps'].append('postgres'); write_json(private/'restoring.json',guard)
    run(['systemctl','--user','start','cone-terminusdb.service','cone-openfga-migrate.service','cone-openfga.service'])
    application = private/'application'
    # Preserve the operator archive in the protected application mount so that
    # C1 can verify every checksum and establish its own manifest-bound guard.
    stage = application/('recovery-snapshot-'+digest)
    if not stage.exists():
        shutil.copytree(directory,stage); stage.chmod(0o700)
    for name in ARTIFACTS | {'manifest.json'}:
        (stage/name).chmod(0o600)
    atomic_write(application/'initialization.json',(stage/'initialization.json').read_text())
    result = operator('restore-validate','--directory','/var/lib/c1/private/'+stage.name,
                      '--operator',operator_name)
    guard['steps'].append('validated'); write_json(private/'restoring.json',guard)
    return {'contract_version':1,'state':'recovery_guarded','validation':result,
            'retained_original_volumes':True,'snapshot_created_at':value['created_at']}


def proof_files(evidence, token):
    application = private_dir()/'application'
    for source,name in [(evidence,'recovery-proof.json'),(token,'recovery-token')]:
        protected(source)
        atomic_write(application/name,source.read_text())
    return ('--namespace-evidence','/var/lib/c1/private/recovery-proof.json',
            '--continuity-token-file','/var/lib/c1/private/recovery-token')


def verify(evidence, token):
    if not (private_dir()/'restoring.json').exists():
        raise ValueError('recovery_not_pending')
    return operator('dr-verify',*proof_files(evidence,token))


def release(evidence, token, accepted, reason, operator_name):
    private=private_dir(); guard=read_json(private/'restoring.json')
    if not guard or accepted != guard['snapshot_created_at']:
        raise ValueError('explicit_snapshot_acceptance_required')
    result=operator('dr-release',*proof_files(evidence,token),'--accept-security-as-of',accepted,
                    '--reason',reason,'--operator',operator_name)
    # C1 has verified and released its journal guard. Remove the supervisor
    # marker only after success, then start the ordinary guarded service.
    write_json(private/'last-recovery.json',guard)
    (private/'restoring.json').unlink()
    run(['systemctl','--user','start','cone-app.service'])
    for name in ('recovery-proof.json','recovery-token'):
        (private/'application'/name).unlink(missing_ok=True)
    return {'contract_version':1,'state':'released','result':result,'retained_original_volumes':True}
