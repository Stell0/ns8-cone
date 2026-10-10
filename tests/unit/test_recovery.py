"""Transport safety: refuse corrupted and unsafe archives before backend mutations."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'imageroot/pypkg'))
from cone_recovery import manifest, volumes, ensure_owned_volumes

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name);self.directory.chmod(0o700)
        patcher=patch.dict(os.environ,{'AGENT_STATE_DIR':str(self.directory)})
        patcher.start();self.addCleanup(patcher.stop)

    def fixture(self, name='storage/data', kind=tarfile.REGTYPE, link=''):
        for file in ['initialization.json','openfga.pgdump']:
            p=self.directory/file;p.write_bytes(b'{}');p.chmod(0o600)
        archive=self.directory/'terminusdb-storage.tar'
        with tarfile.open(archive,'w') as stream:
            item=tarfile.TarInfo(name);item.type=kind;item.linkname=link
            item.size=0;stream.addfile(item,io.BytesIO())
        archive.chmod(0o600)
        hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.directory.iterdir()}
        p=self.directory/'manifest.json'
        p.write_text(json.dumps({'contract_version':1,'manifest_version':2,'type':'external-full','files':hashes}));p.chmod(0o600)

    def test_valid_artifacts_and_corruption(self):
        self.fixture();self.assertEqual(manifest(self.directory)['manifest_version'],2)
        (self.directory/'openfga.pgdump').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError,'backup_integrity_failure'):manifest(self.directory)

    def test_unsafe_tar_headers_and_artifact_permissions_are_rejected(self):
        for name,kind,link in [('../outside',tarfile.REGTYPE,''),('/absolute',tarfile.REGTYPE,''),('link',tarfile.SYMTYPE,'../outside'),('device',tarfile.CHRTYPE,'')]:
            for p in self.directory.iterdir():p.unlink()
            self.fixture(name,kind,link)
            with self.assertRaisesRegex(ValueError,'unsafe_storage_archive'):manifest(self.directory)
        for p in self.directory.iterdir():p.unlink()
        self.fixture();(self.directory/'openfga.pgdump').chmod(0o644)
        with self.assertRaisesRegex(ValueError,'unsafe_recovery_file'):manifest(self.directory)

    def test_volume_configuration_cannot_reference_host_paths(self):
        p=self.directory/'private';p.mkdir(mode=0o700)
        f=p/'volumes.env';f.write_text('CONE_POSTGRES_VOLUME=cone-pgdata\nCONE_TERMINUS_VOLUME=cone-terminus-data\n')
        self.assertEqual(volumes()['CONE_POSTGRES_VOLUME'],'cone-pgdata')
        f.write_text('CONE_POSTGRES_VOLUME=/host/path\nCONE_TERMINUS_VOLUME=cone-terminus-data\n')
        with self.assertRaisesRegex(ValueError,'invalid_backend_volume'):volumes()

    def test_completed_import_cannot_recreate_a_missing_volume(self):
        for role,step in [('CONE_POSTGRES_VOLUME','postgres'),('CONE_TERMINUS_VOLUME','terminus')]:
            guard={'new_volumes':{role:'owned-restore-volume'},'steps':[step]}
            with patch('cone_recovery.subprocess.run',return_value=subprocess.CompletedProcess([],1)), patch('cone_recovery.run') as mutation:
                with self.assertRaisesRegex(ValueError,'owned_recovery_volume_missing'):
                    ensure_owned_volumes(guard,'a'*64)
                mutation.assert_not_called()

    def test_unowned_existing_recovery_volume_is_refused(self):
        guard={'new_volumes':{'CONE_TERMINUS_VOLUME':'owned-restore-volume'},'steps':[]}
        reply=subprocess.CompletedProcess([],0,stdout=b'[{"Labels":{"c1.recovery":"other"}}]')
        with patch('cone_recovery.subprocess.run',return_value=reply), patch('cone_recovery.run') as mutation:
            with self.assertRaisesRegex(ValueError,'ambiguous_recovery_volume'):
                ensure_owned_volumes(guard,'a'*64)
            mutation.assert_not_called()
