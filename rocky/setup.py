from setuptools import find_packages, setup

from rocky.version import __version__

setup(
    name="rocky",
    version=__version__,
    author="Stichting Librekat",
    url="https://openkat.nl/",
    packages=find_packages(exclude="tests"),
    scripts=["manage.py"],
    include_package_data=True,
)
