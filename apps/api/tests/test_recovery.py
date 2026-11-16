"""Recovery rejects unauthenticated/path-unsafe data before target writes."""
import importlib.util
from io import BytesIO
from pathlib import Path
import tarfile
import pytest
from app.ops.object_archive import export_objects, restore_objects, safe_key, validate_archive

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('safarios_recovery', ROOT / 'scripts/recovery.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class Storage:
    def __init__(self, objects=None):
        self.objects = objects or {}
    def get_paginator(self, name):
        return self
    def paginate(self, **kwargs):
        yield {'Contents': [{'Key': key} for key in self.objects]}
    def get_object(self, Bucket, Key):
        return {'Body': BytesIO(self.objects[Key]), 'ContentLength': len(self.objects[Key]), 'ContentType': 'image/png'}
    def list_objects_v2(self, **kwargs):
        return {'Contents': list(self.objects)}
    def upload_fileobj(self, body, bucket, key, ExtraArgs):
        self.objects[key] = body.read()


def test_object_archive_roundtrip_streams_private_objects_without_filesystem_extraction():
    source = Storage({'tenant/one.png': b'private-photo', 'tenant/two.txt': b'notes'})
    stream = BytesIO()
    assert export_objects(source, 'bucket', stream) == 2
    stream.seek(0)
    assert validate_archive(stream) == 2
    stream.seek(0)
    target = Storage()
    assert restore_objects(target, 'bucket', stream) == 2
    assert target.objects == source.objects
    stream.seek(0)
    with pytest.raises(ValueError, match='empty target'):
        restore_objects(target, 'bucket', stream)


@pytest.mark.parametrize('key', ['../secret', '/absolute', 'safe/../../secret', 'safe\\secret', 'safe//secret', './safe', ''])
def test_unsafe_object_paths_are_rejected(key):
    with pytest.raises(ValueError):
        safe_key(key)


def fixture_backup(tmp_path):
    original = tmp_path / 'source'; original.mkdir()
    (original / 'database.dump').write_bytes(b'private database')
    (original / 'configuration.env').write_bytes(b'MFA_ENCRYPTION_KEY=private\n')
    with (original / 'objects.tar').open('wb') as output:
        export_objects(Storage({'lodge/photo.png': b'photo'}), 'bucket', output)
    archive = tmp_path / 'backup.tar'
    key = b'k' * 32
    recovery.pack(original, archive, key)
    return original, archive, key


def test_manifest_authentication_and_all_file_checksums_are_required(tmp_path):
    original, archive, key = fixture_backup(tmp_path)
    target = tmp_path / 'restore';target.mkdir()
    recovery.unpack(archive, target, key)
    assert (target / 'database.dump').read_bytes() == b'private database'
    wrong = tmp_path / 'wrong-key';wrong.mkdir()
    with pytest.raises(ValueError, match='authentication'):
        recovery.unpack(archive, wrong, b'x' * 32)
    assert list(wrong.iterdir()) == []  # Reject unsigned payloads before writing.
    # Knowing the public encryption recipient must not let an attacker substitute
    # a new manifest/database without the separate operator authentication key.
    (original / 'database.dump').write_bytes(b'attacker database')
    poisoned = tmp_path / 'poisoned.tar'
    with tarfile.open(poisoned, 'w') as tar:
        for name in recovery.MEMBERS | {'manifest.json', 'signature.hmac'}:
            tar.add(original / name, arcname=name)
    damaged = tmp_path / 'damaged';damaged.mkdir()
    with pytest.raises(ValueError, match='verification'):
        recovery.unpack(poisoned, damaged, key)


def test_backup_cannot_escape_private_temporary_directory(tmp_path):
    archive = tmp_path / 'escape.tar'
    with tarfile.open(archive, 'w') as tar:
        item = tarfile.TarInfo('../outside');item.size=1
        tar.addfile(item, BytesIO(b'x'))
    target = tmp_path / 'target';target.mkdir()
    with pytest.raises(ValueError, match='unsafe'):
        recovery.unpack(archive, target, b'k' * 32)
    assert not (tmp_path / 'outside').exists()


def test_signing_key_must_be_private_regular_file(tmp_path):
    key = tmp_path / 'key';key.write_bytes(b'k' * 32);key.chmod(0o600)
    assert recovery.signing_key(key) == b'k' * 32
    key.chmod(0o644)
    with pytest.raises(ValueError, match='private regular'):
        recovery.signing_key(key)
    key.chmod(0o600)
    link=tmp_path/'link';link.symlink_to(key)
    with pytest.raises(ValueError):
        recovery.signing_key(link)
