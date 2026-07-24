"""Architecture tests for core package placement and lazy database loading."""

from __future__ import annotations

import ast
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from warframe_damage_calculator.core.data import Data
from warframe_damage_calculator.core.dist import Dist
from warframe_damage_calculator.core.dist_data import DistData
from warframe_damage_calculator.loader.loader import LazyWarframeDatabase, WarframeDatabase
from warframe_damage_calculator.loader.paths import load_bundled_database


class CoreLocationTests(unittest.TestCase):
    def test_core_exports_data_and_dist(self):
        self.assertIs(Data, importlib.import_module("warframe_damage_calculator.core.data").Data)
        self.assertIs(Dist, importlib.import_module("warframe_damage_calculator.core.dist").Dist)
        self.assertTrue(issubclass(DistData, Data))

    def test_core_does_not_import_higher_layers(self):
        core_root = Path(__file__).resolve().parents[1] / "warframe_damage_calculator" / "core"
        forbidden = {"models", "fields", "calculators", "formatters", "loader"}
        for path in core_root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level >= 2 and node.module:
                    top = node.module.split(".")[0]
                    if top in forbidden:
                        self.fail(f"{path.name} relative-imports higher layer {node.module!r}")
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("warframe_damage_calculator."):
                    parts = node.module.split(".")
                    if len(parts) > 1 and parts[1] in forbidden:
                        self.fail(f"{path.name} imports higher layer via {node.module}")


class LazyDatabaseTests(unittest.TestCase):
    def test_importing_arsenal_does_not_load_database(self):
        with patch("warframe_damage_calculator.loader.paths.load_bundled_database") as load_bundled:
            load_bundled.side_effect = AssertionError("bundled database loaded during import")
            module = importlib.reload(importlib.import_module("warframe_damage_calculator.loader.loader"))
            self.assertIsInstance(module.arsenal, module.LazyWarframeDatabase)
            load_bundled.assert_not_called()

    def test_first_get_loads_once_and_reuses(self):
        calls: list[int] = []

        def factory() -> WarframeDatabase:
            calls.append(1)
            return WarframeDatabase({"weapons": {}, "upgrades": {}, "schema_version": 3})

        lazy = LazyWarframeDatabase(factory)
        self.assertEqual(calls, [])
        self.assertIsNone(lazy.get("missing"))
        self.assertEqual(calls, [1])
        self.assertEqual(lazy.database["schema_version"], 3)
        self.assertEqual(calls, [1])

    def test_bundled_resource_loads_from_temp_cwd(self):
        with tempfile.TemporaryDirectory() as folder:
            previous = Path.cwd()
            try:
                import os
                os.chdir(folder)
                payload = load_bundled_database()
            finally:
                os.chdir(previous)
        self.assertIn("weapons", payload)
        self.assertIn("upgrades", payload)
        self.assertGreater(len(payload["weapons"]), 0)


class CustomDatabasePathTests(unittest.TestCase):
    def test_from_file_reads_explicit_path(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "database.json"
            path.write_text('{"weapons": {}, "upgrades": {}, "schema_version": 99}', encoding="utf-8")
            database = WarframeDatabase.from_file(path)
        self.assertEqual(database.database["schema_version"], 99)


if __name__ == "__main__":
    unittest.main()
