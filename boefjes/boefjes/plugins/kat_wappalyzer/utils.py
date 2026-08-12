from cpe import CPE


# replaces the version in an CPE 2.3 formatted string
def replace_cpe_version(cpe: str, version: str) -> str:
    cpe = CPE(cpe).as_fs()

    split = cpe.split(":")
    split[4] = version

    return ":".join(split)
