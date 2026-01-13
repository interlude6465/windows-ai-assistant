"""
Module entry point for running spectral as `python -m spectral`
"""

import sys

from spectral.cli import main

if __name__ == "__main__":
    sys.exit(main())
