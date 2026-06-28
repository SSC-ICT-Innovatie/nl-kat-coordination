from setuptools import find_packages, setup

setup(
    name="mula",
    author="Stichting Librekat",
    url="https://openkat.nl/",
    packages=find_packages(exclude="tests"),
    include_package_data=True,
)
