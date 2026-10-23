"""Parser subprocess: bounded memory/CPU, no document text on diagnostic output."""

import sys, json, resource

resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
from .extraction import extract, MAX_BYTES

try:
    chunks = extract(sys.stdin.buffer.read(MAX_BYTES + 1), sys.argv[1])
    sys.stdout.write(json.dumps(chunks))
except Exception:
    raise SystemExit(1)
