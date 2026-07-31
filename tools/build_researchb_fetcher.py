"""Compatibility import for the Research C fetcher builder.

The public release tool moved to ``build_researchc_fetcher.py``. This module
keeps older automation imports working; new release documentation uses the
Research C name.
"""

from build_researchc_fetcher import *  # noqa: F401,F403
from build_researchc_fetcher import main


if __name__ == "__main__":
    raise SystemExit(main())
