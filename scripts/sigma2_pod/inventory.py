# Read-only listing of one DTSS container directory and whether the server knows it.
# The DTSS container name and its directory in the store need not match
# (e.g. container "se" may live in directory "se-bench").
container = ARGS["container"]
root = os.path.join(ARGS["store_root"], ARGS.get("directory") or container)
if not os.path.isdir(root):
    fail("container directory not found", path=root)

files, total, newest = 0, 0, 0.0
for dirpath, _dirs, names in os.walk(root):
    for name in names:
        st = os.stat(os.path.join(dirpath, name))
        files += 1
        total += st.st_size
        newest = max(newest, st.st_mtime)

top_level = sorted(os.listdir(ARGS["store_root"]))
result = {"path": root, "container": container, "files": files, "bytes": total,
          "newest_modified": iso(newest) if files else None,
          "store_top_level": top_level}
try:
    sts, client = dts_client(ARGS["dtss"])
    names = sorted(str(c) for c in client.get_container_names())
    client.close()
    result["registered"] = container in names
    result["server_containers"] = names
except Exception as exc:
    result["registered"] = None
    result["registration_error"] = f"{type(exc).__name__}: {exc}"
emit(result)
