from importlib.metadata import PackageNotFoundError, version
from os import getenv

__version__ = getenv("OPENKAT_VERSION")
if not __version__:
    try:
        __version__ = version("boefjes")
    except PackageNotFoundError:
        # package is not installed
        __version__ = "0.0.1.dev1"
