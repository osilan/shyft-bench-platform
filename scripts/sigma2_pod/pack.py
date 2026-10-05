# Streams a finished output directory to stdout as an uncompressed tar, sorted, so
# the transfer needs nothing but python in the pod. Read-only.
import tarfile

src = ARGS["output_dir"]
if not os.path.isdir(src):
    fail("output directory not found", path=src)
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|", format=tarfile.PAX_FORMAT) as tar:
    for dirpath, dirs, names in os.walk(src):
        dirs.sort()
        for name in sorted(names):
            full = os.path.join(dirpath, name)
            tar.add(full, arcname=os.path.relpath(full, src), recursive=False)
