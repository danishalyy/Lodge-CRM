"""Small, non-sensitive readiness result for deployment monitoring."""
from sqlalchemy import text


def readiness(db, broker, storage, bucket):
    checks = {}
    try:
        db.execute(text('SELECT 1'))
        checks['database'] = 'ok'
    except Exception:
        checks['database'] = 'unavailable'
    try:
        broker.ping()
        checks['redis'] = 'ok'
        checks['worker_scheduler'] = 'ok' if broker.get('safarios:worker-heartbeat') else 'unavailable'
    except Exception:
        checks['redis'] = 'unavailable'
        checks['worker_scheduler'] = 'unavailable'
    try:
        storage.head_bucket(Bucket=bucket)
        checks['storage'] = 'ok'
    except Exception:
        checks['storage'] = 'unavailable'
    healthy = all(value == 'ok' for value in checks.values())
    return {'status': 'ready' if healthy else 'not_ready', 'checks': checks}, 200 if healthy else 503
