import logging
import re
from enum import Enum

logger = logging.getLogger(__name__)


class VersionCheck(Enum):
    SMALLER = 1
    SMALLER_EQUAL = 3
    EQUAL = 2
    GREATER_EQUAL = 6
    GREATER = 4
    UNKNOWN = 0
    ALL = 7


def check_version(version1: str, version2: str) -> VersionCheck:
    """
    Checks first string in regard to second string
    Output: VersionCheck.{SMALLER,SMALLER_EQUAL,EQUAL,GREATER_EQUAL,GREATER,UNKNOWN}
    """

    # Split the version until first dot
    version1_split = version1.split(".", 1)
    version2_split = version2.split(".", 1)

    # Check versions until first dot
    v1 = version1_split[0]
    v2 = version2_split[0]
    if v1 != v2 and v1.isnumeric() and v2.isnumeric():
        if int(v1) < int(v2):
            return VersionCheck.SMALLER
        elif int(v1) > int(v2):
            return VersionCheck.GREATER_EQUAL
    elif v1 != v2:
        # Check for packages, because we cannot compare those on name only (can start with version)
        pack1 = re.split("[+-]", v1)
        pack2 = re.split("[+-]", v2)
        if pack1[0].isnumeric() and pack2[0].isnumeric():
            # Has a package-name, but it starts with version-numbers  # https://snyk.io/vuln/debian%3A12%3Awordpress
            first_part_check = check_version(pack1[0], pack2[0])
            if first_part_check != VersionCheck.EQUAL:
                return first_part_check
            else:
                # Version is the same, but package different.. impossible to compare
                return VersionCheck.UNKNOWN
        elif (len(pack1) > 1 or len(pack2) > 1) and v1 != v2:
            # They have different packages, impossible to compare
            return VersionCheck.UNKNOWN
        else:
            # The same package name or no packages at all but versionname is non-numeric
            if v1 < v2:
                return VersionCheck.SMALLER
            elif v2 > v1:
                return VersionCheck.GREATER

    # Check part after the first dot
    if len(version1_split) == 1 and len(version2_split) == 1:
        # This was the last part
        return VersionCheck.EQUAL
    elif len(version1_split) == 1:
        # version 1 < version 1.1
        return VersionCheck.SMALLER
    elif len(version2_split) == 1:
        # version 1 > version 1.1
        return VersionCheck.GREATER
    else:
        # Compare next part of version
        return check_version(version1_split[1], version2_split[1])


def check_version_agains_versionlist(my_version: str, all_versions: list[str]) -> tuple[bool, list[str] | None]:
    lowerbound = all_versions.pop(0).strip()
    upperbound = None

    regex_ineq_upperbound = "^([<=]+)"
    regex_ineq_lowerbound = "^(>=?)"

    start_inequality = re.search(regex_ineq_lowerbound, lowerbound)
    start_version = re.search("^[0-9a-z*]", lowerbound)
    end_bracket = None

    lowerbound_ok = False

    # Check if lowerbound is < or <=
    if re.search(r"^[\[(]", lowerbound):
        # Example: "(1.1,1.4]"  # https://snyk.io/vuln/maven%3Aorg.apache.nifi%3Anifi-security-utils
        upperbound = all_versions.pop(0).strip()
        end_bracket = re.search("[])]$", upperbound)
        if not upperbound or not end_bracket:
            # Unexpected input: there is no closing-bracket
            logger.warning(
                "Unexpected input, missing closing bracket for %s,%s. Ignoring input.", lowerbound, upperbound
            )
            return False, None
        lowerbound_versioncheck = VersionCheck.GREATER if lowerbound[0] == "(" else VersionCheck.GREATER_EQUAL
        lowerbound = lowerbound[1:].strip()
        if len(lowerbound) == 0:
            # Example: "(,1.2)"  # https://snyk.io/vuln/maven%3Aorg.apache.nifi%3Anifi-security-utils
            lowerbound_ok = True
    elif start_inequality:
        # Example: ">1.2,<=1.8"  # https://snyk.io/vuln/npm%3Alodash
        if start_inequality.group(0) == ">":
            lowerbound_versioncheck = VersionCheck.GREATER
        elif start_inequality.group(0) == ">=":
            lowerbound_versioncheck = VersionCheck.GREATER_EQUAL
        lowerbound = lowerbound[len(start_inequality.group(0)) :].strip()
        if len(all_versions) == 0:
            return False, None
        upperbound = all_versions.pop(0).strip()
    elif lowerbound == "*":
        lowerbound_ok = True
        upperbound = lowerbound
    elif start_version:
        # Example: "1.2"
        upperbound = f"={lowerbound}"
        lowerbound_ok = True
    elif re.search(regex_ineq_upperbound, lowerbound):
        # Example: "<= 1.5"
        lowerbound_ok = True
        upperbound = lowerbound
    else:
        # Warning: unexpected not implemented something
        return False, None

    # Check lowerbound
    if not lowerbound_ok:
        check_version_result = check_version(my_version, lowerbound)
        if check_version_result.value & lowerbound_versioncheck.value == 0:
            return False, all_versions

    # Check if upperbound is >, >=, = or *
    if upperbound is None:
        logger.warning("Unexpected upperbound in kat_snyk.normalize: %s", all_versions)
        return False, None

    start_inequality = re.search(regex_ineq_upperbound, upperbound)

    if end_bracket:
        # Example: "(1.2,1.4]"
        upperbound_versioncheck = VersionCheck.SMALLER if upperbound[-1] == ")" else VersionCheck.SMALLER_EQUAL
        upperbound = upperbound[:-1].strip()
    elif start_inequality:
        # Example: "<=1.4"
        if start_inequality.group(0) == "<":
            upperbound_versioncheck = VersionCheck.SMALLER
        elif start_inequality.group(0) == "<=":
            upperbound_versioncheck = VersionCheck.SMALLER_EQUAL
        elif start_inequality.group(0) == "=":
            upperbound_versioncheck = VersionCheck.EQUAL
        upperbound = upperbound[len(start_inequality.group(0)) :].strip()
    elif upperbound == "*":
        upperbound_versioncheck = VersionCheck.ALL
    else:
        logger.warning("Unexpected input in kat_snyk.normalize: %s", all_versions)
        return False, None

    # Check upperbound
    check_version_result = check_version(my_version, upperbound)
    if check_version_result.value & upperbound_versioncheck.value == 0:
        return False, all_versions

    return True, all_versions


def check_version_in(version: str, versions: str) -> bool:
    if not version:
        return False
    all_versions: list[str] | None = versions.split(
        ","
    )  # Example: https://snyk.io/vuln/composer%3Awoocommerce%2Fwoocommerce-blocks
    in_range = False
    while not in_range and all_versions:
        in_range, all_versions = check_version_agains_versionlist(version, all_versions)
    return in_range
