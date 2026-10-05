"""Tests for scripts/sigma2.py and scripts/sigma2_guard.py without Sigma2.

tests/fake_kubectl.py stands in for kubectl: it runs the real pod scripts locally
against a stub Shyft (tests/fake_pod). Extraction tests need numpy and xarray
(requirements.txt) and are skipped without them.
"""
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAY = 86400
T0 = 315532800  # 1980-01-01T00:00:00Z
N = 30          # days in a complete simulation series
CAL_OFFSET = 10  # reverse run: calibration starts 10 days after the simulation

try:
    import numpy  # noqa: F401
    import xarray  # noqa: F401
    HAVE_XARRAY = True
except ImportError:
    HAVE_XARRAY = False


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def series(n=N, offset=0.0, start=T0):
    return {"start": start, "values": [round(1.0 + offset + 0.1 * i, 3) for i in range(n)]}


def cal_series(n=N - CAL_OFFSET, start=T0 + CAL_OFFSET * DAY):
    return series(n=n, start=start)


class Sigma2Tool(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.tool = load("sigma2_under_test", ROOT / "scripts" / "sigma2.py")
        store = self.tmp / "store" / "se-bench"
        store.mkdir(parents=True)
        for i in range(3):
            (store / f"part{i}.db").write_bytes(b"x" * (10 + i))
        (self.tmp / "store" / "catchments").mkdir()
        code = self.tmp / "code"
        code.mkdir()
        # The legacy run files, as on the pod: the last assignment is the active one.
        (code / "fill_benchmark_data.py").write_text(
            "DT = 3600 * 24\nN_CAL = 20\nN_SIM = 30\n"
            "T0_CAL = time(\"1980-01-01T00:00:00Z\")\n"
            "# reverse run\nT0_CAL = time(\"1980-01-11T00:00:00Z\")\nT0_SIM = time(\"1980-01-01T00:00:00Z\")\n")
        (code / "run_benchmark_experiment.py").write_text(
            "MODEL_CONFIG = RPMSTK_CONFIG\nSIM_ONLY = False\nCATCHMENTS = None\nbatch15 = []\nCATCHMENTS = batch15\n")
        self.cfg = {
            "context": "nird-lmd", "namespace": "shyft-ns11121k", "target": "deploy/shyftservices",
            "container": None, "python": "python3", "dtss": "shyftdtss:22010",
            "store_root": str(self.tmp / "store"), "pod_code_dir": str(code),
            "pod_code_files": ["run_benchmark_experiment.py", "fill_benchmark_data.py", "batch_utils.py"],
            "pod_config_files": ["fill_benchmark_data.py", "run_benchmark_experiment.py"],
            "pod_output_root": str(self.tmp / "podout"), "results_root": "runs"}
        (self.tmp / "config").mkdir()
        (self.tmp / "config" / "sigma2.json").write_text(json.dumps(self.cfg))
        self.tool.ROOT = self.tmp
        self.tool.CONFIG = self.tmp / "config" / "sigma2.json"
        self.tool.KUBECTL = str(ROOT / "tests" / "fake_kubectl.py")

        # A reverse run as the legacy runner stores it: a numbered prefix, no "_rev",
        # and per run key a whole-period "sim" and a later-starting "cal" series.
        sim, n = {}, 0

        def put(stage, goal, pc, v, st, data):
            nonlocal n
            n += 1
            sim[f"{100 + n}_1_1.discharge-rpmstk-{stage}-{goal}-bobyqa{pc}-v{v:02d}-{st}"] = data

        for pc in ("", "-pcorr"):
            for goal in ("kge", "nse"):
                for v in (0, 1):
                    for st in ("100.1.0", "200.2.0", "300.3.0"):
                        if (goal, pc, v, st) != ("kge", "", 0, "200.2.0"):           # missing
                            put("sim", goal, pc, v, st, series(offset=v, n=N - 5 if (goal, pc, v, st) ==
                                                                ("nse", "-pcorr", 1, "300.3.0") else N))  # partial
                        if (goal, pc, v, st) == ("nse", "", 0, "300.3.0"):
                            put("cal", goal, pc, v, st, cal_series(n=N - CAL_OFFSET - 5))  # partial calibration
                        elif (goal, pc, v, st) != ("kge", "-pcorr", 1, "100.1.0"):    # no calibration
                            put("cal", goal, pc, v, st, cal_series())
        put("sim", "kge", "", 7, "100.1.0", series())                                   # not expected
        put("cal", "kge", "", 7, "100.1.0", cal_series())
        put("sim", "lnse", "", 0, "100.1.0", series())                                  # forward run: ignored
        put("cal", "lnse", "", 0, "100.1.0", cal_series(start=T0))
        sim["discharge-rpmstk-old-name-100.1.0"] = series()                             # unparsed
        obs = {f"catchment/{st}.discharge.observed.nve": series() for st in ("100.1.0", "200.2.0", "300.3.0")}
        self.dtss = {"address": "shyftdtss:22010", "registered": ["se-bench"],
                     "series": {"se-bench": {**sim, **obs}}}
        self.write_dtss()
        self.kube_state = self.tmp / "kube.json"
        self.kube_state.write_text(json.dumps({}))
        os.environ.update(FAKE_DTSS=str(self.tmp / "dtss.json"), FAKE_KUBE=str(self.kube_state),
                          FAKE_POD_PYTHON=sys.executable)

    def write_dtss(self):
        (self.tmp / "dtss.json").write_text(json.dumps(self.dtss))

    def run_tool(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = self.tool.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def runs(self, run_id="20261005-1200-collect"):
        return self.tmp / "runs" / run_id

    def kubectl_calls(self):
        path = self.kube_state.with_suffix(".calls")
        return [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []

    def prepare(self, run_id="20261005-1200-collect"):
        self.assertEqual(self.run_tool("snapshot", "--run", run_id, "--experiment", "legacy-rpmstk-reverse",
                                       "--container", "se-bench")[0], 0)
        proposal = json.loads((self.runs(run_id) / "expected.proposed.json").read_text())
        expected = {k: v for k, v in proposal.items() if not k.startswith("_")}
        # the founder confirms: two goals and variants 0-1 were planned, on the observed stations
        expected.update(goals=["kge", "nse"], variants=[0, 1], stations="observed")
        (self.runs(run_id) / "expected.json").write_text(json.dumps(expected))
        self.assertEqual(self.run_tool("complete", "--run", run_id)[0], 0)

    # ── access ────────────────────────────────────────────────────────────────

    def test_preflight_reports_pod_and_stacks(self):
        code, out, _ = self.run_tool("preflight", "--run", "20261005-1200-collect", "--stacks", "r_pm_st_k", "r_pm_fsm2_k")
        report = json.loads((self.runs() / "preflight.json").read_text())
        self.assertEqual(report["pod"]["stacks"], {"r_pm_st_k": True, "r_pm_fsm2_k": False})
        self.assertTrue(report["pod"]["dtss"]["reachable"])
        self.assertEqual(report["pod"]["dtss"]["containers"], ["se-bench"])
        self.assertEqual(code, 0 if HAVE_XARRAY else 1)

    def test_expired_login_stops_with_instructions_and_exit_4(self):
        self.kube_state.write_text(json.dumps({"expired": True}))
        code, _, err = self.run_tool("inventory", "--run", "20261005-1200-collect", "--container", "se-bench")
        self.assertEqual(code, 4)
        self.assertIn("kubectl config use-context nird-lmd", err)
        self.assertIn("in your own terminal", err.lower())

    def test_context_and_namespace_are_pinned_and_verbs_are_read_or_exec(self):
        self.run_tool("preflight")
        self.prepare()
        calls = [c for c in self.kubectl_calls() if c[:2] != ["config", "current-context"]]
        self.assertTrue(calls)
        for c in calls:
            self.assertEqual(c[:4], ["--context", "nird-lmd", "--namespace", "shyft-ns11121k"])
            self.assertIn(c[4], ("auth", "get", "exec"))

    # ── collection steps ──────────────────────────────────────────────────────

    def test_inventory_counts_files_and_checks_registration(self):
        code, _, _ = self.run_tool("inventory", "--run", "20261005-1200-collect", "--container", "se-bench")
        inv = json.loads((self.runs() / "inventory.json").read_text())
        self.assertEqual(code, 0)
        self.assertEqual((inv["files"], inv["bytes"], inv["registered"]), (3, 33, True))
        self.assertEqual(inv["store_top_level"], ["catchments", "se-bench"])
        self.dtss["registered"] = []
        self.write_dtss()
        code, out, _ = self.run_tool("inventory", "--run", "20261005-1201-collect", "--container", "se-bench")
        self.assertEqual(code, 1)
        self.assertIn("not registered", out)

    def test_inventory_handles_a_container_whose_directory_has_another_name(self):
        (self.tmp / "store" / "se-bench").rename(self.tmp / "store" / "bench-dir")
        self.dtss["registered"] = ["se"]
        self.write_dtss()
        code, out, _ = self.run_tool("inventory", "--run", "20261005-1200-collect",
                                     "--container", "se", "--directory", "bench-dir")
        inv = json.loads((self.runs() / "inventory.json").read_text())
        self.assertEqual(code, 0, out)
        self.assertEqual((inv["container"], inv["files"], inv["registered"]), ("se", 3, True))
        self.assertTrue(inv["path"].endswith("/bench-dir"))

    def test_snapshot_hashes_pod_code_and_parses_the_run_files_without_importing(self):
        self.run_tool("snapshot", "--run", "20261005-1200-collect", "--experiment", "legacy-rpmstk-reverse",
                      "--container", "se-bench")
        snap = json.loads((self.runs() / "snapshot.json").read_text())
        runner = Path(self.cfg["pod_code_dir"]) / "run_benchmark_experiment.py"
        self.assertEqual(snap["files"]["run_benchmark_experiment.py"]["sha256"],
                         hashlib.sha256(runner.read_bytes()).hexdigest())
        self.assertIsNone(snap["files"]["batch_utils.py"])
        fill = snap["config"]["fill_benchmark_data.py"]
        self.assertEqual(fill["DT"], 86400)                                       # 3600 * 24
        self.assertEqual(fill["T0_CAL"], {"call": "time", "arg": "1980-01-11T00:00:00Z"})  # last one wins
        self.assertEqual(snap["config"]["run_benchmark_experiment.py"]["CATCHMENTS"], {"unparsed": "batch15"})
        self.assertEqual(snap["shyft_version"], "35.0.1-fake")

    def test_proposal_takes_direction_and_periods_from_the_run_files(self):
        self.run_tool("snapshot", "--run", "20261005-1200-collect", "--experiment", "legacy-rpmstk-reverse",
                      "--container", "se-bench")
        proposal = json.loads((self.runs() / "expected.proposed.json").read_text())
        self.assertEqual(proposal["models"], ["rpmstk"])                          # MODEL_CONFIG = RPMSTK_CONFIG
        self.assertTrue(proposal["reverse"])                                      # T0_CAL after T0_SIM
        self.assertEqual(proposal["calibration"], {"start": "1980-01-11T00:00:00Z", "end": "1980-01-31T00:00:00Z"})
        self.assertEqual(proposal["simulation"], {"start": "1980-01-01T00:00:00Z", "end": "1980-01-31T00:00:00Z"})
        self.assertEqual((proposal["goals"], proposal["pcorr"], proposal["variants"]),
                         (["kge", "lnse", "nse"], [False, True], [0, 1, 7]))     # from the names present
        self.assertEqual(proposal["stations"]["CATCHMENTS"], "batch15")
        self.assertEqual(proposal["stations"]["present"], 3)

    def test_the_real_reverse_settings_give_the_real_periods(self):
        settings = {"DT": 86400, "N_CAL": 7792, "N_SIM": 15098,
                    "T0_CAL": {"call": "time", "arg": "1999-09-01T06:00:00Z"},
                    "T0_SIM": {"call": "time", "arg": "1979-09-01T06:00:00Z"}}
        self.assertEqual(self.tool.legacy_periods(settings), {
            "calibration": {"start": "1999-09-01T06:00:00Z", "end": "2020-12-31T06:00:00Z"},
            "simulation": {"start": "1979-09-01T06:00:00Z", "end": "2021-01-01T06:00:00Z"}})
        self.assertEqual(self.tool.legacy_model({"unparsed": "RPMSTK_CONFIG"}), "rpmstk")
        self.assertEqual(self.tool.legacy_model({"call": "ptfsm2k_config", "arg": "default"}), "ptfsm2k")

    def test_complete_refuses_stations_the_founder_has_not_confirmed(self):
        self.run_tool("snapshot", "--run", "20261005-1200-collect", "--experiment", "legacy-rpmstk-reverse",
                      "--container", "se-bench")
        proposal = json.loads((self.runs() / "expected.proposed.json").read_text())
        (self.runs() / "expected.json").write_text(json.dumps(proposal))
        code, _, err = self.run_tool("complete", "--run", "20261005-1200-collect")
        self.assertEqual(code, 1)
        self.assertIn("stations must be a list", err)

    def test_complete_requires_the_founders_expected_set(self):
        self.run_tool("snapshot", "--run", "20261005-1200-collect", "--experiment", "legacy-rpmstk-reverse",
                      "--container", "se-bench")
        code, _, err = self.run_tool("complete", "--run", "20261005-1200-collect")
        self.assertEqual(code, 1)
        self.assertIn("expected.json is missing", err)

    def test_complete_classifies_every_run_key(self):
        self.prepare()
        report = json.loads((self.runs() / "completeness.json").read_text())
        self.assertEqual(report["totals"], {"expected": 24, "complete": 22, "partial": 1, "duplicate": 0, "missing": 1})
        partial = [r for r in report["rows"] if r["status"] == "partial"][0]
        self.assertEqual((partial["goal"], partial["pcorr"], partial["variant"], partial["station"]),
                         ("nse", True, 1, "300.3.0"))
        self.assertEqual(len(report["unexpected"]), 1)
        self.assertIn("discharge-rpmstk-sim-kge-bobyqa-v07-100.1.0", report["unexpected"][0])
        self.assertTrue(report["reverse"])
        self.assertEqual(report["other_direction"]["count"], 1)                   # the forward lnse key
        self.assertIn("-sim-lnse-", report["other_direction"]["examples"][0])
        self.assertEqual(report["unparsed"], ["discharge-rpmstk-old-name-100.1.0"])
        self.assertEqual(report["reference_period"]["source"], "expected.json")
        self.assertEqual(report["calibration_totals"], {"complete": 22, "partial": 1, "duplicate": 0, "missing": 1})
        self.assertEqual(report["direction_unverified"], 1)                       # sim with no calibration
        complete = [r for r in report["rows"] if r["status"] == "complete"][0]
        self.assertEqual(complete["series"]["direction"], "reverse")
        md = (self.runs() / "completeness.md").read_text()
        self.assertIn("Partial series (for the founder's decision)", md)

    def test_names_samples_series_from_the_dtss_or_the_store_folder(self):
        code, out, _ = self.run_tool("names", "--run", "20261005-1200-collect", "--container", "se-bench")
        report = json.loads((self.runs() / "names.json").read_text())
        self.assertEqual(code, 0)
        self.assertEqual((report["count"], report["parsed"], report["simulation"], report["calibration"],
                          report["rev_suffix"]), (51, 50, 25, 25, 0))
        self.assertTrue(report["shapes"][0]["shape"].startswith("9_9_9.discharge-rpmstk-"))
        folder = self.tmp / "store" / "se-bench-rev0"
        (folder / "sub").mkdir(parents=True)
        (folder / "sub" / "bench.discharge-rpmstk-sim-kge-bobyqa-v00-100.1.0_rev").write_bytes(b"")
        (folder / "forcing-temperature-1").write_bytes(b"")
        code, out, _ = self.run_tool("names", "--run", "20261005-1201-collect", "--directory", "se-bench-rev0")
        report = json.loads((self.runs("20261005-1201-collect") / "names.json").read_text())
        self.assertEqual(code, 0, out)
        self.assertEqual(report["sample"], ["sub/bench.discharge-rpmstk-sim-kge-bobyqa-v00-100.1.0_rev"])
        self.assertEqual(report["rev_suffix"], 1)
        self.assertIn("store folder 'se-bench-rev0'", out)
        self.assertEqual(self.run_tool("names", "--run", "20261005-1202-collect")[0], 1)

    def test_parser_accepts_both_orders_a_prefix_both_stages_and_the_rev_suffix(self):
        parse = self.tool.parse_simulated
        self.assertEqual(parse("discharge-rpmstk-sim-kge_lkge-bobyqa-pcorr-v03-178.1.0"),
                         (("rpmstk", "kge_lkge", True, 3, "178.1.0"), "bobyqa", False, "sim"))
        self.assertEqual(parse("112_115_1.discharge-rpmstk-cal-kge-bobyqa-pcorr-v00-12.171.0"),
                         (("rpmstk", "kge", True, 0, "12.171.0"), "bobyqa", False, "cal"))
        self.assertEqual(parse("x/y.discharge-rpmstk-sim-nse-bobyqa-178.1.0-v04_rev"),
                         (("rpmstk", "nse", False, 4, "178.1.0"), "bobyqa", True, "sim"))
        self.assertIsNone(parse("discharge-rpmstk-old-name-100.1.0"))

    def test_direction_comes_from_the_periods(self):
        d = self.tool.direction
        sim = {"start": "1979-09-01T06:00:00Z"}
        self.assertEqual(d(sim, False, [{"start": "1999-09-01T06:00:00Z"}]), "reverse")
        self.assertEqual(d(sim, False, [{"start": "1979-09-01T06:00:00Z"}]), "forward")
        self.assertIsNone(d(sim, False, []))
        self.assertEqual(d(sim, True, []), "reverse")

    def test_complete_is_deterministic(self):
        self.prepare("20261005-1200-collect")
        self.prepare("20261005-1300-collect")
        a = (self.runs("20261005-1200-collect") / "completeness.json").read_bytes()
        b = (self.runs("20261005-1300-collect") / "completeness.json").read_bytes()
        self.assertEqual(a, b)

    def test_extract_without_confirm_writes_nothing_in_the_pod(self):
        self.prepare()
        code, out, _ = self.run_tool("extract", "--run", "20261005-1200-collect")
        self.assertEqual(code, 0)
        self.assertIn("rerun with --confirm", out)
        self.assertFalse((self.tmp / "podout").exists())

    def test_manifest_records_every_step_with_pod_script_checksums(self):
        self.prepare()
        manifest = json.loads((self.runs() / "manifest.json").read_text())
        self.assertEqual([s["step"] for s in manifest["steps"]], ["snapshot", "complete"])
        exec_calls = [c for s in manifest["steps"] for c in s["kubectl"] if "pod_script" in c]
        source = (ROOT / "scripts/sigma2_pod/_common.py").read_text() + "\n" + \
                 (ROOT / "scripts/sigma2_pod/series.py").read_text()
        self.assertIn({"name": "series", "sha256": hashlib.sha256(source.encode()).hexdigest()},
                      [c["pod_script"] for c in exec_calls])

    @unittest.skipUnless(HAVE_XARRAY, "needs numpy and xarray (requirements.txt)")
    def test_extract_and_fetch_bring_verified_netcdf_home(self):
        self.prepare()
        self.assertEqual(self.run_tool("extract", "--run", "20261005-1200-collect", "--confirm")[0], 0)
        code, out, _ = self.run_tool("fetch", "--run", "20261005-1200-collect")
        self.assertEqual(code, 0, out)
        data = self.runs() / "data"
        self.assertEqual(sorted(p.name for p in data.iterdir()),
                         ["checksums.json", "legacy-rpmstk-reverse_rpmstk_bc.nc", "legacy-rpmstk-reverse_rpmstk_bc_pcorr.nc"])
        import xarray as xr
        ds = xr.open_dataset(data / "legacy-rpmstk-reverse_rpmstk_bc.nc")
        self.assertEqual(ds.attrs["experiment_id"], "legacy-rpmstk-reverse")
        self.assertEqual(ds.attrs["shyft_version"], "35.0.1-fake")
        self.assertEqual(ds["discharge"].attrs["units"], "m3 s-1")
        self.assertEqual(int(ds["discharge"].notnull().sum()), 11 * N)  # 12 keys minus the missing one
        ds.close()
        self.assertTrue(json.loads((self.runs() / "verify.json").read_text())["ok"])
        # immutable: a second extract or fetch into the same run refuses
        code, _, err = self.run_tool("extract", "--run", "20261005-1200-collect", "--confirm")
        self.assertEqual(code, 3)
        self.assertIn("output directory already exists; extraction output is immutable", err)
        self.assertEqual(self.run_tool("fetch", "--run", "20261005-1200-collect")[0], 1)

    @unittest.skipUnless(HAVE_XARRAY, "needs numpy and xarray (requirements.txt)")
    def test_fetch_detects_a_file_changed_after_extraction(self):
        self.prepare()
        self.run_tool("extract", "--run", "20261005-1200-collect", "--confirm")
        pod_file = self.tmp / "podout" / "20261005-1200-collect" / "legacy-rpmstk-reverse_rpmstk_bc.nc"
        pod_file.write_bytes(pod_file.read_bytes() + b"tampered")
        code, _, err = self.run_tool("fetch", "--run", "20261005-1200-collect")
        self.assertEqual(code, 5)
        self.assertIn("checksum verification failed", err)

    @unittest.skipUnless(HAVE_XARRAY, "needs numpy and xarray (requirements.txt)")
    def test_two_collections_of_the_same_data_have_the_same_content_hash(self):
        for run_id in ("20261005-1200-collect", "20261005-1300-collect"):
            self.prepare(run_id)
            self.run_tool("extract", "--run", run_id, "--confirm")
        a = json.loads((self.runs("20261005-1200-collect") / "extract.json").read_text())["files"]
        b = json.loads((self.runs("20261005-1300-collect") / "extract.json").read_text())["files"]
        self.assertEqual([f["content_sha256"] for f in a], [f["content_sha256"] for f in b])


class Sigma2Guard(unittest.TestCase):
    def decide(self, tool_input, tool_name="run_in_terminal"):
        proc = subprocess.run([sys.executable, str(ROOT / "scripts/sigma2_guard.py")],
                              input=json.dumps({"tool_name": tool_name, "tool_input": tool_input}),
                              capture_output=True, text=True)
        out = json.loads(proc.stdout)
        return out.get("hookSpecificOutput", {}).get("permissionDecision", "allow")

    def test_raw_kubectl_is_denied(self):
        self.assertEqual(self.decide({"command": "kubectl exec deploy/shyftservices -- ls"}), "deny")
        self.assertEqual(self.decide({"command": "ls && kubectl cp a b"}), "deny")

    def test_the_tool_is_allowed(self):
        self.assertEqual(self.decide({"command": "python3 scripts/sigma2.py inventory --run 20261005-1200-x --container se-bench"}), "allow")

    def test_credentials_and_binary_swap_are_denied(self):
        self.assertEqual(self.decide({"command": "nird-toolkit-auth-helper login"}), "deny")
        self.assertEqual(self.decide({"filePath": "/Users/x/.kube/config"}, "read_file"), "deny")
        self.assertEqual(self.decide({"command": "BENCH_SIGMA2_KUBECTL=/tmp/k python3 scripts/sigma2.py preflight"}), "deny")

    def test_writing_code_that_calls_kubectl_is_denied_outside_the_tool(self):
        self.assertEqual(self.decide({"filePath": "scripts/quick.py", "content": "subprocess.run(['kubectl','cp'])"},
                                     "create_file"), "deny")
        self.assertEqual(self.decide({"filePath": "scripts/sigma2.py", "content": "KUBECTL = 'kubectl'"},
                                     "replace_string_in_file"), "allow")
        self.assertEqual(self.decide({"filePath": "README.md", "content": "the tool wraps kubectl"},
                                     "replace_string_in_file"), "allow")


if __name__ == "__main__":
    unittest.main()
