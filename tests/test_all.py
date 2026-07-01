from __future__ import annotations

import pathlib
import sys
import unittest


def run_all_tests() -> unittest.result.TestResult:
    tests_dir = pathlib.Path(__file__).parent
    project_root = tests_dir.parent

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    suite = unittest.defaultTestLoader.discover(start_dir=str(tests_dir), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)


if __name__ == "__main__":
    result = run_all_tests()
    raise SystemExit(0 if result.wasSuccessful() else 1)
