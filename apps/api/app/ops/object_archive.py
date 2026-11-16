"""Stream private object storage backups without extracting paths to disk."""
import argparse
import sys
import tarfile
from pathlib import PurePosixPath


def safe_key(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or '\\' in name or any(x in {'', '.', '..'} for x in name.split('/')):
        raise ValueError('Unsafe object key in backup')
    return name


def export_objects(client, bucket, output):
    count = 0
    with tarfile.open(fileobj=output, mode='w|') as archive:
        for page in client.get_paginator('list_objects_v2').paginate(Bucket=bucket):
            for item in page.get('Contents', []):
                key = safe_key(item['Key'])
                response = client.get_object(Bucket=bucket, Key=key)
                try:
                    entry = tarfile.TarInfo(key)
                    entry.size = response['ContentLength']
                    entry.mode = 0o600
                    entry.pax_headers = {'safarios.content-type': response.get('ContentType', 'application/octet-stream')}
                    archive.addfile(entry, response['Body'])
                finally:
                    response['Body'].close()
                count += 1
    return count


def validate_archive(stream):
    seen = set()
    with tarfile.open(fileobj=stream, mode='r|') as archive:
        for entry in archive:
            key = safe_key(entry.name)
            if not entry.isfile() or key in seen:
                raise ValueError('Duplicate or non-regular object in backup')
            seen.add(key)
            content_type = entry.pax_headers.get('safarios.content-type', 'application/octet-stream')
            if len(content_type) > 255 or '\r' in content_type or '\n' in content_type:
                raise ValueError('Invalid object metadata')
            body = archive.extractfile(entry)
            remaining = entry.size
            while remaining:
                part = body.read(min(1024 * 1024, remaining))
                if not part:
                    raise ValueError('Truncated object in backup')
                remaining -= len(part)
    return len(seen)


class Unseekable:
    def __init__(self, source):
        self.source = source

    def read(self, size=-1):
        return self.source.read(size)


def restore_objects(client, bucket, stream):
    # The operator wrapper authenticates the complete archive before this call.
    # The target bucket must be fresh; never overwrite customer objects.
    if client.list_objects_v2(Bucket=bucket, MaxKeys=1).get('Contents'):
        raise ValueError('Restore requires an empty target bucket')
    seen = set()
    with tarfile.open(fileobj=stream, mode='r|') as archive:
        for entry in archive:
            key = safe_key(entry.name)
            if not entry.isfile() or key in seen:
                raise ValueError('Duplicate or non-regular object in backup')
            seen.add(key)
            client.upload_fileobj(Unseekable(archive.extractfile(entry)), bucket, key,
                                  ExtraArgs={'ContentType': entry.pax_headers.get('safarios.content-type', 'application/octet-stream')})
    return len(seen)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['export', 'restore', 'check-empty', 'validate'])
    args = parser.parse_args()
    if args.action == 'validate':
        validate_archive(sys.stdin.buffer)
        return
    import boto3
    from ..config import settings
    client = boto3.client('s3', endpoint_url=settings.object_storage_endpoint,
                          aws_access_key_id=settings.object_storage_access_key,
                          aws_secret_access_key=settings.object_storage_secret_key,
                          region_name=settings.object_storage_region)
    bucket = settings.object_storage_bucket
    if args.action == 'export':
        export_objects(client, bucket, sys.stdout.buffer)
    elif args.action == 'restore':
        restore_objects(client, bucket, sys.stdin.buffer)
    elif client.list_objects_v2(Bucket=bucket, MaxKeys=1).get('Contents'):
        raise ValueError('Restore requires an empty target bucket')


if __name__ == '__main__':
    main()
