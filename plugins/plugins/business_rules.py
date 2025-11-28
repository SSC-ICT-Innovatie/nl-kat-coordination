SA_TCP_PORTS = [21, 22, 23, 5900]
DB_TCP_PORTS = [1433, 1434, 3050, 3306, 5432]
MICROSOFT_RDP_PORTS = [3389]
COMMON_TCP_PORTS = [25, 53, 80, 110, 143, 443, 465, 587, 993, 995]
ALL_COMMON_TCP = COMMON_TCP_PORTS + SA_TCP_PORTS + DB_TCP_PORTS + MICROSOFT_RDP_PORTS
COMMON_UDP = [53]
INDICATORS = [
    "ns1.registrant-verification.ispapi.net",
    "ns2.registrant-verification.ispapi.net",
    "ns3.registrant-verification.ispapi.net",
]


def get_rules():
    rules = {
        "ipv6_webservers": {
            "name": "ipv6_webservers",
            "description": "Checks if webserver has IPv6 support",
            "finding_type_code": "KAT-WEBSERVER-NO-IPV6",
        },
        "ipv6_nameservers": {
            "name": "ipv6_nameservers",
            "description": "Checks if nameserver has IPv6 support",
            "finding_type_code": "KAT-NAMESERVER-NO-IPV6",
        },
        "missing_spf": {
            "name": "missing_spf",
            "description": "Checks if the hostname has valid SPF records",
            "finding_type_code": "KAT-NO-SPF",
        },
        "open_sysadmin_port": {
            "name": "open_sysadmin_port",
            "description": "Detect open sysadmin ports",
            "finding_type_code": "KAT-OPEN-SYSADMIN-PORT",
        },
        "open_database_port": {
            "name": "open_database_port",
            "description": "Detect open database ports",
            "finding_type_code": "KAT-OPEN-DATABASE-PORT",
        },
        "open_remote_desktop_port": {
            "name": "open_remote_desktop_port",
            "description": "Detect open RDP ports",
            "finding_type_code": "KAT-REMOTE-DESKTOP-PORT",
        },
        "open_uncommon_port": {
            "name": "open_uncommon_port",
            "description": "Detect open uncommon ports",
            "finding_type_code": "KAT-UNCOMMON-OPEN-PORT",
        },
        "open_common_port": {
            "name": "open_common_port",
            "description": "Checks for open common ports",
            "finding_type_code": "KAT-OPEN-COMMON-PORT",
        },
        "missing_caa": {
            "name": "missing_caa",
            "description": "Checks if a hostname has a CAA record",
            "finding_type_code": "KAT-NO-CAA",
        },
        "missing_dmarc": {
            "name": "missing_dmarc",
            "description": "Checks if mail servers have DMARC records",
            "finding_type_code": "KAT-NO-DMARC",
        },
        "domain_owner_verification": {
            "name": "domain_owner_verification",
            "description": "Checks if the hostname has pending ownership",
            "finding_type_code": "KAT-DOMAIN-OWNERSHIP-PENDING",
        },
    }
    for software in ["mysql", "mongodb", "openssh", "rdp", "pgsql", "telnet", "db2"]:
        rules[f"{software}_detection"] = {
            "name": f"{software}_detection",
            "description": f"Checks if {software} is running on the IPAddress.",
            "finding_type_code": "KAT-EXPOSED-SOFTWARE",
        }

    return rules
