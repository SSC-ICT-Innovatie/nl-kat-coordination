#!/usr/bin/env python


# This script fixes the filename attribute in a coverage.xml file for SonarCloud coverage analysis
# These filenames should be relative to the base dir and not the coverage source directory


import argparse
import xml.etree.ElementTree as etree
from pathlib import Path


def path_prefixer(file: Path, prefix: Path) -> None:
    xml = file.read_text()
    root = etree.fromstring(xml)  # noqa: S314

    for element in root.findall(".//*[@filename]"):
        filename = element.get("filename")
        if filename is not None:
            element.set("filename", prefix.joinpath(filename).as_posix())

    file.write_text(etree.tostring(root).decode())


def main():
    parser = argparse.ArgumentParser(description="Prefix paths in coverage.xml files")
    parser.add_argument("file", type=Path, help="Path to the coverage.xml file.")
    parser.add_argument("prefix", type=Path, help="Path to prefix the filenames with.")
    args = parser.parse_args()

    path_prefixer(Path(args.file), Path(args.prefix))


if __name__ == "__main__":
    main()
