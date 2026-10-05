# What the pod can do: python, modules, Shyft build, DTSS reachability, disk.
import importlib
import platform
import shutil

result = {"python": platform.python_version(), "modules": {}}
for name in ("shyft.time_series", "shyft.hydrology", "numpy", "xarray", "netCDF4", "scipy"):
    try:
        mod = importlib.import_module(name)
        result["modules"][name] = getattr(mod, "__version__", "present")
    except Exception as exc:  # report, do not fail: the caller decides
        result["modules"][name] = None
        result.setdefault("import_errors", {})[name] = type(exc).__name__

stacks = {}
for stack in ARGS.get("stacks", []):
    try:
        importlib.import_module("shyft.hydrology." + stack)
        stacks[stack] = True
    except Exception:
        stacks[stack] = False
result["stacks"] = stacks

try:
    sts, client = dts_client(ARGS["dtss"])
    result["dtss"] = {"address": ARGS["dtss"], "reachable": True,
                      "server_version": str(client.get_server_version()),
                      "containers": sorted(str(c) for c in client.get_container_names())}
    client.close()
except Exception as exc:
    result["dtss"] = {"address": ARGS["dtss"], "reachable": False, "error": f"{type(exc).__name__}: {exc}"}

probe_dir = ARGS["output_root"]
while probe_dir and not os.path.exists(probe_dir):
    probe_dir = os.path.dirname(probe_dir)
usage = shutil.disk_usage(probe_dir or "/")
result["disk"] = {"path": probe_dir, "free_bytes": usage.free, "total_bytes": usage.total}
emit(result)
