from setuptools import find_packages, setup

from boefjes.version import __version__

setup(
    name="boefjes",
    version=__version__,
    author="Stichting Librekat",
    url="https://openkat.nl/",
    packages=find_packages(exclude="tests"),
    include_package_data=True,
)
