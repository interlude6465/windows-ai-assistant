"""Module entry point for running learn as `python -m spectral.learn`"""

import sys

from spectral.learn_cli import main

if __name__ == "__main__":
    sys.exit(main())
