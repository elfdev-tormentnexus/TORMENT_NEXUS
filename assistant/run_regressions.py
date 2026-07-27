"""Run the regression suite under both normal and embedded Python."""

import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# The Windows embeddable interpreter reads its import path exclusively from
# python314._pth.  It does not add the script or working directory, so test
# discovery needs the same explicit project bootstrap as main.py.
sys.path.insert(0, PROJECT_ROOT)


def main():
    suite = unittest.defaultTestLoader.discover(
        os.path.join(PROJECT_ROOT, "tests"),
        pattern="test_*.py",
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
