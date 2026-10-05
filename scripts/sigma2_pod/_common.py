# Prelude sent ahead of every pod script (scripts/sigma2.py concatenates them and
# pipes the result to the pod's python on stdin, so nothing is copied into the pod).
# Arguments arrive as one JSON document in argv[1]; the result leaves as one JSON
# document on stdout. Python standard library plus Shyft only.
import datetime as _dt
import hashlib
import json
import os
import sys

ARGS = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}


def emit(obj):
    sys.stdout.write(json.dumps(obj, sort_keys=True, indent=1) + "\n")
    sys.stdout.flush()


def fail(message, **extra):
    emit(dict(extra, error=message))
    sys.exit(3)


def iso(seconds):
    return _dt.datetime.fromtimestamp(int(seconds), tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def dts_client(address):
    import shyft.time_series as sts
    return sts, sts.DtsClient(address, 10000)
