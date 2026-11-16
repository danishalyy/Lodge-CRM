#!/usr/bin/env python3
"""Encrypted, authenticated operator backups and non-overwriting recovery.

Requires Docker Compose and age. No HTTP endpoint calls this program. Secrets are
read from private files, never shell interpolation or command-line key values.
"""
import argparse
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import stat
import fcntl
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MEMBERS = {'database.dump', 'objects.tar', 'configuration.env'}
WRITERS = ('web', 'api', 'worker', 'beat')


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def signing_key(path):
    path = Path(path)
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    try:
        fd = os.open(path, flags)
    except OSError as error:
        raise ValueError('Signing key must be a private regular file (mode 600)') from error
    with os.fdopen(fd, 'rb') as source:
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077 or metadata.st_uid != os.getuid():
            raise ValueError('Signing key must be a private regular file (mode 600)')
        if metadata.st_size != 32:
            raise ValueError('Signing key must contain exactly 32 random bytes')
        key = source.read(33)
        if len(key) != 32:
            raise ValueError('Signing key must contain exactly 32 random bytes')
        return key


def signature(key, payload):
    return hmac.new(key, b'SafariOS recovery manifest v1\0' + payload, hashlib.sha256).hexdigest().encode()


def compose(args):
    command = ['docker', 'compose', '--env-file', str(Path(args.env_file).resolve())]
    for path in args.file or [str(ROOT / 'infra/docker-compose.yml')]:
        command += ['-f', str(Path(path).resolve())]
    if args.project:
        command += ['--project-name', args.project]
    configuration = json.loads(subprocess.check_output(command + ['config', '--format', 'json']))
    return command, configuration


@contextmanager
def quiesce(command):
    running = subprocess.check_output(command + ['ps', '--services', '--status', 'running'], text=True).splitlines()
    selected = [name for name in WRITERS if name in running]
    try:
        if selected:
            run(command + ['stop', *selected])
        yield
    finally:
        if selected:
            run(command + ['start', *selected])


def pack(folder, output, key):
    manifest = {'format': 1, 'files': {name: {'sha256': sha(folder / name), 'size': (folder / name).stat().st_size} for name in sorted(MEMBERS)}}
    data = json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()
    (folder / 'manifest.json').write_bytes(data)
    (folder / 'signature.hmac').write_bytes(signature(key, data))
    with tarfile.open(output, 'w') as archive:
        for name in ['manifest.json', 'signature.hmac', *sorted(MEMBERS)]:
            archive.add(folder / name, arcname=name, recursive=False)


def unpack(archive_path, folder, key):
    allowed = MEMBERS | {'manifest.json', 'signature.hmac'}
    found = {}
    with tarfile.open(archive_path, 'r:') as archive:
        # Inspect only headers first. Authenticate bounded metadata before writing
        # any payload, so an unsigned archive cannot fill the recovery filesystem.
        for member in archive:
            if member.name not in allowed or member.name in found or not member.isfile() or member.size < 0:
                raise ValueError('Unexpected, duplicate or unsafe backup member')
            if member.name in {'manifest.json', 'signature.hmac', 'configuration.env'} and member.size > 1024 * 1024:
                raise ValueError('Oversized backup metadata')
            found[member.name] = member
        if set(found) != allowed:
            raise ValueError('Incomplete backup')
        data = archive.extractfile(found['manifest.json']).read(1024 * 1024 + 1)
        supplied_signature = archive.extractfile(found['signature.hmac']).read(65)
        if not hmac.compare_digest(supplied_signature, signature(key, data)):
            raise ValueError('Backup origin authentication failed')
        manifest = json.loads(data)
        if manifest.get('format') != 1 or set(manifest.get('files', {})) != MEMBERS:
            raise ValueError('Unsupported backup manifest')
        for name, entry in manifest['files'].items():
            if found[name].size != entry['size']:
                raise ValueError('Backup content verification failed')
        for name in sorted(MEMBERS):
            with (folder / name).open('xb') as dest:
                shutil.copyfileobj(archive.extractfile(found[name]), dest, 1024 * 1024)
            if not hmac.compare_digest(sha(folder / name), manifest['files'][name]['sha256']):
                raise ValueError('Backup content verification failed')
    # Validate every private object before any database or object-store write.
    import sys
    sys.path.insert(0, str(ROOT / 'apps/api'))
    from app.ops.object_archive import validate_archive
    with (folder / 'objects.tar').open('rb') as stream:
        validate_archive(stream)


def backup(args, folder, key):
    command, cfg = compose(args)
    if Path(args.archive).exists():
        raise ValueError('Refusing to replace an existing backup')
    pg = cfg['services']['postgres']['environment']
    with quiesce(command):
        with (folder / 'database.dump').open('wb') as output:
            run(command + ['exec', '-T', 'postgres', 'pg_dump', '-Fc', '--no-owner', '--no-privileges', '-U', pg['POSTGRES_USER'], '-d', pg['POSTGRES_DB']], stdout=output)
        with (folder / 'objects.tar').open('wb') as output:
            run(command + ['run', '--rm', '--no-deps', '-T', 'api', 'python', '-m', 'app.ops.object_archive', 'export'], stdout=output)
        shutil.copyfile(args.env_file, folder / 'configuration.env')
        pack(folder, folder / 'backup.tar', key)
    # Recipient is public. Authentication uses a separate signing key, so knowing
    # the public age recipient cannot forge a trusted database recovery archive.
    with Path(args.archive).open('xb') as output, (folder / 'backup.tar').open('rb') as source:
        try:
            run([args.age, '--encrypt', '--recipient', args.recipient], stdin=source, stdout=output)
        except BaseException:
            Path(args.archive).unlink(missing_ok=True)
            raise
    print('Encrypted and authenticated backup completed. Store it off this server.')


def recover(args, folder, key):
    with (folder / 'backup.tar').open('wb') as output:
        run([args.age, '--decrypt', '--identity', args.identity, args.archive], stdout=output)
    unpack(folder / 'backup.tar', folder, key)
    if args.export_config:
        with Path(args.export_config).open('xb') as output:
            output.write((folder / 'configuration.env').read_bytes())
    if not args.restore:
        print('Backup authentication, file checksums and object archive validation passed. No target was changed.')
        return
    command, cfg = compose(args)
    if args.confirm_project != cfg['name']:
        raise ValueError('Explicit target project confirmation is required')
    pg = cfg['services']['postgres']['environment']
    query = "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','f')"
    count = subprocess.check_output(command + ['exec', '-T', 'postgres', 'psql', '-U', pg['POSTGRES_USER'], '-d', pg['POSTGRES_DB'], '-tAc', query], text=True).strip()
    if count != '0':
        raise ValueError('Restore requires an empty target database; no tables were overwritten')
    running = subprocess.check_output(command + ['ps', '--services', '--status', 'running'], text=True).splitlines()
    if any(name in running for name in WRITERS):
        raise ValueError('Target application services must be stopped before recovery')
    run(command + ['run', '--rm', '--no-deps', '-T', 'api', 'python', '-m', 'app.ops.object_archive', 'check-empty'])
    with (folder / 'database.dump').open('rb') as source:
        run(command + ['exec', '-T', 'postgres', 'pg_restore', '--exit-on-error', '--single-transaction', '--no-owner', '--no-privileges', '-U', pg['POSTGRES_USER'], '-d', pg['POSTGRES_DB']], stdin=source)
    with (folder / 'objects.tar').open('rb') as source:
        run(command + ['run', '--rm', '--no-deps', '-T', 'api', 'python', '-m', 'app.ops.object_archive', 'restore'], stdin=source)
    run(command + ['run', '--rm', '--no-deps', '-T', 'migrate'])
    run(command + ['run', '--rm', '--no-deps', '-T', 'db-grants'])
    run(command + ['run', '--rm', '--no-deps', '-T', 'migrate', 'python', '-m', 'app.ops.post_restore'])
    print('Recovery completed into the empty target. Verify keys/configuration and run acceptance before starting application services.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup', 'recover'])
    parser.add_argument('--archive', required=True)
    parser.add_argument('--signing-key-file', required=True)
    parser.add_argument('--age', default='age')
    parser.add_argument('--env-file', default=str(ROOT / 'infra/.env'))
    parser.add_argument('--file', action='append')
    parser.add_argument('--project')
    parser.add_argument('--recipient')
    parser.add_argument('--identity')
    parser.add_argument('--export-config')
    parser.add_argument('--restore', action='store_true')
    parser.add_argument('--confirm-project')
    args = parser.parse_args()
    if args.action == 'backup' and not args.recipient:
        parser.error('backup requires --recipient')
    if args.action == 'recover' and not args.identity:
        parser.error('recover requires --identity')
    os.umask(0o077)
    key = signing_key(args.signing_key_file)
    try:
        lockdir = Path(tempfile.gettempdir()) / ('safarios-operator-' + str(os.getuid()))
        lockdir.mkdir(mode=0o700, exist_ok=True)
        if lockdir.is_symlink() or lockdir.stat().st_uid != os.getuid() or lockdir.stat().st_mode & 0o077:
            raise ValueError('Unsafe operator lock directory')
        lock = (lockdir / 'recovery.lock').open('a+b')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with tempfile.TemporaryDirectory(prefix='safarios-recovery-') as directory:
            folder = Path(directory)
            (backup if args.action == 'backup' else recover)(args, folder, key)
    except (ValueError, OSError, subprocess.CalledProcessError, tarfile.TarError):
        # Third-party output can contain sensitive connection values. Preserve
        # the protected operator log separately rather than echoing config here.
        parser.exit(1, 'Recovery operation failed; services were not silently overwritten. Check the protected operator logs and target state.\n')


if __name__ == '__main__':
    main()
