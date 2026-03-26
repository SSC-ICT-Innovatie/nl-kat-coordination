from setuptools import find_packages, setup

from octopoes.version import __version__

setup(
    name="octopoes",
    version=__version__,
    author="MinVWS",
    url="https://openkat.nl/",
    license="EUPL-1.2",
    packages=find_packages(exclude="tests"),
    package_data={"octopoes": ["data/logging.yml"]},
    include_package_data=True,
)
