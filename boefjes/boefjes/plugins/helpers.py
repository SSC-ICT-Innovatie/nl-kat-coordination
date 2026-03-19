def cpe_to_name_version(cpe: str) -> tuple[str | None, str | None]:
    """Fetch the software name and version from a CPE string."""
    cpe_split = cpe.split(":")
    cpe_split_len = len(cpe_split)
    name = None if cpe_split_len < 4 else cpe_split[3]
    version = None if cpe_split_len < 5 else cpe_split[4]
    return name, version
