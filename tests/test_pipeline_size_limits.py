import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import canon, export  # noqa: E402


SPEC = {
    "id": "size-limit-test",
    "view": "test",
    "forcing": "test",
    "direction": "forward",
    "pcorr": False,
    "optimizer": "test",
}


class SizeLimitsTest(unittest.TestCase):
    def make_dist(self, dist: Path, svg: bytes = b"", csv: bytes = b"") -> None:
        entry = export.index_entry(SPEC)
        (dist / "figures").mkdir(parents=True, exist_ok=True)
        (dist / "tables").mkdir(exist_ok=True)
        (dist / entry["svg"]).write_bytes(svg)
        (dist / entry["csv"]).write_bytes(csv)
        artifacts = [
            {"path": entry["svg"], "sha256": export.sha256(svg)},
            {"path": entry["csv"], "sha256": export.sha256(csv)},
        ]
        (dist / "figure-index.json").write_bytes(export.dumps({"figures": [entry]}))
        (dist / "manifest.json").write_bytes(export.dumps({"artifacts": artifacts}))
        (dist / "canon.json").write_bytes(b"")
        (dist / "catalogue.json").write_bytes(b"")

    def check(self, dist: Path, limits: dict) -> list[str]:
        with (patch.object(canon, "load", return_value={"sizeLimits": limits}),
              patch.object(canon, "declared_figures", return_value=[SPEC])):
            return export.check_dist(dist, "test")

    def limits(self, svg: int = 100, csv: int = 100, export_bytes: int = 10000) -> dict:
        return {"svgBytes": svg, "csvBytes": csv, "exportBytes": export_bytes}

    def test_svg_size_limit_accepts_exact_limit_and_rejects_one_byte_over(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp)
            self.make_dist(dist, svg=b"1234")
            self.assertEqual(self.check(dist, self.limits(svg=4)), [])

            self.make_dist(dist, svg=b"12345")
            problems = self.check(dist, self.limits(svg=4))
            self.assertTrue(any("figures/size-limit-test.svg" in problem
                                and "5 bytes" in problem and "4 bytes" in problem
                                for problem in problems))

    def test_csv_size_limit_accepts_exact_limit_and_rejects_one_byte_over(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp)
            self.make_dist(dist, csv=b"1234")
            self.assertEqual(self.check(dist, self.limits(csv=4)), [])

            self.make_dist(dist, csv=b"12345")
            problems = self.check(dist, self.limits(csv=4))
            self.assertTrue(any("tables/size-limit-test.csv" in problem
                                and "5 bytes" in problem and "4 bytes" in problem
                                for problem in problems))

    def test_export_size_limit_accepts_exact_limit_and_rejects_one_byte_over(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp)
            self.make_dist(dist, svg=b"s", csv=b"c")
            total_size = sum(path.stat().st_size for path in dist.rglob("*") if path.is_file())
            self.assertEqual(self.check(dist, self.limits(export_bytes=total_size)), [])

            problems = self.check(dist, self.limits(export_bytes=total_size - 1))
            self.assertTrue(any("export:" in problem and f"{total_size} bytes" in problem
                                and f"{total_size - 1} bytes" in problem
                                for problem in problems))


if __name__ == "__main__":
    unittest.main()
