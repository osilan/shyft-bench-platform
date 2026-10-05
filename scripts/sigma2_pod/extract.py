# Writes NetCDF for the requested complete series into a NEW output directory
# (never the store), one file per (model, pcorr) group, then checksums.
# Refuses to touch an existing directory, so a run's output is immutable.
import numpy as np

out_dir = ARGS["output_dir"]
if os.path.exists(out_dir):
    fail("output directory already exists; extraction output is immutable", path=out_dir)
try:
    import xarray as xr
except Exception as exc:
    fail(f"xarray is not available in the pod: {type(exc).__name__}")

sts, client = dts_client(ARGS["dtss"])
container = ARGS["container"]
os.makedirs(out_dir)
written = []
try:
    for group in ARGS["groups"]:
        times = None
        stations, goals, variants = group["stations"], group["goals"], group["variants"]
        data = None
        for item in group["series"]:
            url = sts.shyft_url(container, item["name"])
            period = sts.UtcPeriod(int(item["t0"]), int(item["t1"]))
            ts = client.evaluate(sts.TsVector([sts.TimeSeries(url)]), utcperiod=period, clip_result=period)[0]
            values = np.asarray(ts.values, dtype="float64")
            if times is None:
                times = np.array([int(ts.time_axis.time(i)) for i in range(ts.time_axis.size())], dtype="int64")
                data = np.full((len(stations), len(goals), len(variants), len(times)), np.nan)
            if len(values) != len(times):
                fail("series length differs within a group", name=item["name"], expected=len(times), got=len(values))
            data[stations.index(item["station"]), goals.index(item["goal"]), variants.index(item["variant"]), :] = values
        ds = xr.Dataset(
            {"discharge": (("station", "goal", "variant", "time"), data,
                           {"units": "m3 s-1", "long_name": "simulated discharge"})},
            coords={"station": stations, "goal": goals, "variant": variants,
                    "time": ("time", times.astype("datetime64[s]"))},
            attrs=dict(sorted(group["attrs"].items())))
        path = os.path.join(out_dir, group["file"])
        ds.to_netcdf(path)
        digest = hashlib.sha256()
        # content hash: the data and its scientific metadata, not who collected it when,
        # so two collections of the same data compare equal
        stable = {k: v for k, v in group["attrs"].items() if k not in ("run_id", "tool_commit")}
        digest.update(json.dumps({"stations": stations, "goals": goals, "variants": variants,
                                  "attrs": stable}, sort_keys=True).encode())
        digest.update(times.tobytes())
        digest.update(np.ascontiguousarray(data).tobytes())
        written.append({"file": group["file"], "sha256": sha256_file(path),
                        "content_sha256": digest.hexdigest(), "bytes": os.path.getsize(path),
                        "series": len(group["series"])})
finally:
    client.close()

with open(os.path.join(out_dir, "checksums.json"), "w") as fh:
    json.dump({"files": written}, fh, sort_keys=True, indent=1)
emit({"output_dir": out_dir, "files": written})
