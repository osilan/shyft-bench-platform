# Read-only: series names straight from a store directory (the DTSS file backend keeps
# one file per series, named by its path), for directories not registered with the DTSS.
import re

root = os.path.join(ARGS["store_root"], ARGS["directory"])
if not os.path.isdir(root):
    fail("directory not found", path=root)
pattern = re.compile(ARGS["pattern"])
names = []
for dirpath, dirs, files in os.walk(root):
    dirs.sort()
    for name in files:
        rel = os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/")
        if pattern.fullmatch(rel):
            names.append(rel)
emit({"directory": root, "simulated": [{"name": n} for n in sorted(names)], "observed": []})
