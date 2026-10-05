"""Minimal stand-in for shyft.time_series, enough for the pod scripts. Daily
series; data comes from the JSON file named by FAKE_DTSS."""
import json
import os
import re

__version__ = "35.0.1-fake"
DAY = 86400


def _db():
    return json.load(open(os.environ["FAKE_DTSS"]))


def shyft_url(container, path):
    return f"shyft://{container}/{path}"


def _split(url):
    rest = url[len("shyft://"):]
    container, _, path = rest.partition("/")
    return container, path


class UtcPeriod:
    def __init__(self, start, end):
        self.start, self.end = int(start), int(end)


class _Info:
    def __init__(self, name, start, end):
        self.name, self.data_period = name, UtcPeriod(start, end)


class _Axis:
    def __init__(self, t0, n):
        self.t0, self.n = t0, n

    def size(self):
        return self.n

    def time(self, i):
        return self.t0 + i * DAY


class TimeSeries:
    def __init__(self, url):
        self.url = url


class _Result:
    def __init__(self, t0, values):
        self.values, self.time_axis = values, _Axis(t0, len(values))


TsVector = list


class DtsClient:
    def __init__(self, address, timeout_ms):
        db = _db()
        if address != db["address"]:
            raise RuntimeError(f"cannot connect to {address}")
        self.db = db

    def get_server_version(self):
        return "fake-dtss"

    def get_container_names(self):
        return list(self.db["registered"])

    def find(self, url):
        container, pattern = _split(url)
        pattern = pattern.replace("\\/", "/")
        rows = self.db["series"].get(container, {})
        return [_Info(n, r["start"], r["start"] + DAY * len(r["values"]))
                for n, r in sorted(rows.items()) if re.fullmatch(pattern, n)]

    def evaluate(self, tsv, utcperiod, clip_result=None):
        out = []
        for ts in tsv:
            container, name = _split(ts.url)
            r = self.db["series"][container][name]
            first = max(0, (utcperiod.start - r["start"]) // DAY)
            last = min(len(r["values"]), (utcperiod.end - r["start"]) // DAY)
            out.append(_Result(r["start"] + first * DAY, r["values"][first:last]))
        return out

    def close(self):
        pass
