import json

import requests
from bs4 import BeautifulSoup

from boefjes.plugins.kat_snyk import check_version


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ = boefje_meta["arguments"]["input"]["software"]
    software_name = input_["name"]
    software_version = input_["version"]

    result: dict[str, list[dict]] = {"table_versions": [], "table_vulnerabilities": [], "cve_vulnerabilities": []}
    url_snyk = f"https://snyk.io/vuln/npm:{software_name.lower().replace(' ', '-')}"
    page = requests.get(url_snyk, timeout=30)
    soup = BeautifulSoup(page.content, "html.parser")
    tables = soup.find_all("table")
    for table in tables:
        if table.find("thead") is None:
            continue

        headers = [header.text.strip() for header in table.select("thead th")]
        temp_soup = [
            {headers[i]: cell for i, cell in enumerate(row.find_all("td"))}
            for row in table.find("tbody").find_all("tr")
        ]

        if table.find("thead") and table.find("thead").find("tr", {"class": "vue--table__row"}):
            # Direct vulnerabilities table
            for info in temp_soup:
                try:
                    parsed_info = {
                        "Vuln_href": info["Vulnerability"].find("a", href=True)["href"].split("/")[-1],
                        "Vuln_text": info["Vulnerability"].text.strip()[2:].strip(),
                        "Vuln_versions": info["Vulnerable Version"].text.strip(),
                    }
                except KeyError:
                    continue

                if check_version.check_version_in(software_version, parsed_info["Vuln_versions"]):
                    # Check if there is a CVE code available for this vulnerability
                    url_snyk = f"https://snyk.io/vuln/{parsed_info['Vuln_href']}"
                    vuln_page = requests.get(url_snyk, timeout=30)
                    vuln_soup = BeautifulSoup(vuln_page.content, "html.parser")
                    cve_element = vuln_soup.select("[class='cve']")
                    cve_code = cve_element[0].text.split("\n")[0] if cve_element else ""

                    if cve_code.startswith("CVE-"):
                        result["cve_vulnerabilities"].append(
                            {"cve_code": cve_code, "Vuln_text": parsed_info["Vuln_text"]}
                        )
                    else:
                        result["table_vulnerabilities"].append(parsed_info)

        elif table.attrs.get("data-vue") == "vulns-version-table":
            # Versions table
            for info in temp_soup:
                result["table_versions"].append(
                    {
                        "Version_href": info["Version"].find("a", href=True)["href"].split("/")[-1],
                        "Version_text": info["Version"].find("a").text.strip(),
                        "is_latest": len(info["Version"].find_all("a")) == 2
                        and info["Version"].find_all("a")[1].text.strip() == "Latest",
                    }
                )

    return [(set(), json.dumps(result))]
