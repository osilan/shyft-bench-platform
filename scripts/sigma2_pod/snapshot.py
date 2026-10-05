# Read-only: checksums of the pod's benchmark code, the top-level settings of its
# run files (parsed, never imported), and the Shyft version.
import ast
import operator

code_dir = ARGS["code_dir"]
files = {}
for name in ARGS["files"]:
    path = os.path.join(code_dir, name)
    files[name] = {"sha256": sha256_file(path), "bytes": os.path.getsize(path)} if os.path.isfile(path) else None

ARITH = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
         ast.FloorDiv: operator.floordiv, ast.Div: operator.truediv}


def value(node, source):
    """A literal, simple arithmetic on numbers (3600 * 24), a call with one string
    argument (time("1999-09-01T06:00:00Z")), or else the source text."""
    try:
        return ast.literal_eval(node)
    except Exception:
        pass
    if isinstance(node, ast.BinOp) and type(node.op) in ARITH:
        left, right = value(node.left, source), value(node.right, source)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return ARITH[type(node.op)](left, right)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and len(node.args) == 1
            and not node.keywords and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
        return {"call": node.func.id, "arg": node.args[0].value}
    return {"unparsed": ast.get_source_segment(source, node)}


# The last top-level assignment wins, as when the file runs.
config = {}
for name in ARGS["config_files"]:
    path = os.path.join(code_dir, name)
    if not os.path.isfile(path):
        config[name] = None
        continue
    source = open(path, encoding="utf-8").read()
    settings = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            settings[node.targets[0].id] = value(node.value, source)
    config[name] = settings

try:
    import shyft.time_series as sts
    shyft_version = getattr(sts, "__version__", None)
except Exception as exc:
    shyft_version = None
emit({"code_dir": code_dir, "files": files, "config_files": ARGS["config_files"],
      "config": config, "shyft_version": shyft_version})
