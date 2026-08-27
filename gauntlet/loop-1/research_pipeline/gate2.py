#!/usr/bin/env python3
"""Deprecated compatibility alias for :mod:`automated_challenge`.

This machine process is not DAMM human gate G2. New callers must invoke
``automated_challenge.py``. The legacy entry point preserves old checkpoint/output
names only so historical commands can be resumed without rewriting their artifacts.
"""

import sys

from automated_challenge import *  # noqa: F401,F403
from automated_challenge import main as _automated_challenge_main


def main():
    print(
        "warning: gate2.py is deprecated; this is an automated challenge, not human G2",
        file=sys.stderr,
    )
    return _automated_challenge_main([*sys.argv[1:], "--legacy-g2-output-names"])


if __name__ == "__main__":
    sys.exit(main())
