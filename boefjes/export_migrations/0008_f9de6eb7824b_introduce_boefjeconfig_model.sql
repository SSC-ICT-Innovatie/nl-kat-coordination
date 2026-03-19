CREATE TABLE boefje_config (
    id SERIAL NOT NULL,
    settings VARCHAR(512) DEFAULT '{}' NOT NULL,
    enabled BOOLEAN DEFAULT 'false' NOT NULL,
    boefje_id INTEGER NOT NULL,
    organisation_pk INTEGER NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(boefje_id) REFERENCES boefje (id) ON DELETE CASCADE,
    FOREIGN KEY(organisation_pk) REFERENCES organisation (pk) ON DELETE CASCADE,
    CONSTRAINT unique_boefje_config_per_organisation_per_boefje UNIQUE (organisation_pk, boefje_id)
);
ALTER TABLE boefje_config OWNER TO katalogus_dba;
GRANT ALL ON boefje_config TO katalogus;

CREATE TABLE normalizer_config (
    id SERIAL NOT NULL,
    enabled BOOLEAN DEFAULT 'false' NOT NULL,
    normalizer_id INTEGER NOT NULL,
    organisation_pk INTEGER NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(normalizer_id) REFERENCES normalizer (id) ON DELETE CASCADE,
    FOREIGN KEY(organisation_pk) REFERENCES organisation (pk) ON DELETE CASCADE,
    CONSTRAINT unique_normalizer_config_per_organisation_per_normalizer UNIQUE (organisation_pk, normalizer_id)
);
ALTER TABLE normalizer_config OWNER TO katalogus_dba;
GRANT ALL ON normalizer_config TO katalogus;

ALTER TABLE boefje ADD COLUMN static BOOLEAN DEFAULT 'false' NOT NULL;
ALTER TABLE normalizer ADD COLUMN static BOOLEAN DEFAULT 'false' NOT NULL;

-- For backward compatibility we insert all boefje and normalizer models and set the 'settings' and 'enabled' fields.
INSERT INTO boefje (
  plugin_id,
  name,
  description,
  scan_level,
  consumes,
  produces,
  environment_keys,
  oci_image,
  oci_arguments,
  version,
  static
) values
      ('adr-finding-types', 'ADR Finding Types', 'Hydrate information on API Design Rules (ADR) finding types for common design mistakes.', '0', '{"ADRFindingType"}', '{"boefje/adr-finding-types"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('adr-validator', 'API Design Rules validator', 'Validate if an API conforms to the API Design Rules (ADR).', '1', '{"RESTAPI"}', '{"boefje/adr-validator"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('binaryedge', 'BinaryEdge', 'Use BinaryEdge to find open ports with vulnerabilities. Requires a BinaryEdge API key.', '2', '{"IPAddressV4", "IPAddressV6"}', '{"boefje/binaryedge"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('censys', 'Censys', 'Use Censys to discover open ports, services and certificates. Requires an API key.', '1', '{"IPAddressV4", "IPAddressV6"}', '{"boefje/censys"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('certificate-search', 'CRT', 'Searches for certificates and new hostnames in the transparency logs of crt.sh.', '1', '{"DNSZone"}', '{"boefje/certificate-search"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('CVE-2023-34039', 'CVE-2023-34039 - VMware Aria Operations', 'Checks if there are static SSH keys present that can be used for remote code execution on VWware Aria Operations (CVE-2023-34039). This vulnerability can be used to bypass SSH authentication and gain access to the Aria Operations for Networks CLI.', '4', '{"IPService"}', '{"boefje/CVE-2023-34039"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('CVE_2023_35078', 'CVE-2023-35078 - Ivanti EPMM', 'Checks websites for the presents of the Ivanti EPMM interface and whether the interface is vulnerable to the remote unauthenticated API access vulnerability (CVE-2023-35078). Script contribution by NFIR.', '2', '{"Website"}', '{"boefje/CVE_2023_35078"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('cve-finding-types', 'CVE Finding Types', 'Hydrate information of Common Vulnerabilities and Exposures (CVE) finding types from the CVE API.', '0', '{"CVEFindingType"}', '{"boefje/cve-finding-types"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('cwe-finding-types', 'CWE Finding Types', 'Hydrate information of Common Weakness Enumeration (CWE) finding types.', '0', '{"CWEFindingType"}', '{"boefje/cwe-finding-types"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('dicom', 'DICOM', 'Find exposed DICOM servers. DICOM servers are used to process medical imaging information.', '2', '{"IPAddressV4", "IPAddressV6"}', '{"boefje/dicom"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('dns-records', 'DNS records', 'Fetch the DNS record(s) of a hostname.', '1', '{"Hostname"}', '{"boefje/dns-records"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('dns-zone', 'DNS zone', 'Fetch the parent DNS zone of a DNS zone.', '1', '{"DNSZone"}', '{"boefje/dns-zone"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('dns-sec', 'DNSSEC', 'Validates DNSSEC of a hostname by checking the cryptographic signatures.', '1', '{"Hostname"}', '{"boefje/dns-sec"}', '{"TEST_KEY"}', 'ghcr.io/minvws/openkat/dns-sec:latest', '{}', null, true),
      ('external_db', 'External database host fetcher', 'Fetch hostnames and IP addresses/netblocks from an external database with API. See `description.md` for more information. Useful if you have a large network and wish to add all your hosts. You can also upload hosts through the CSV upload functionality.', '0', '{"Network"}', '{"boefje/external_db"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('fierce', 'Fierce', 'Perform DNS reconnaissance using Fierce. Helps to locate non-contiguous IP space and hostnames against specified hostnames. No exploitation is performed. Beware if your DNS is managed by an external party. This boefjes performs a brute force attack against the name server.', '3', '{"Hostname"}', '{"boefje/fierce"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('green-hosting', 'GreenHosting', 'Use the Green Web Foundation Partner API to check whether the website is hosted on a green server. Meaning it runs on renewable energy and/or offsets its carbon footprint. Does not require an API key.', '1', '{"Website"}', '{"boefje/green-hosting"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('kat-finding-types', 'KAT Finding Types', 'Hydrate information of KAT finding types.', '0', '{"KATFindingType"}', '{"boefje/kat-finding-types"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('leakix', 'LeakIX', 'Use LeakIX to find open ports, software and vulnerabilities. Requires a LeakIX API key.', '1', '{"IPAddressV4", "Hostname", "IPAddressV6"}', '{"boefje/leakix"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('log4shell', 'Log4Shell', 'Checks for the Log4j vulnerability. This boefje will not create a finding. Requires a trusted FQDN for the catch callbacks.', '4', '{"Hostname"}', '{"boefje/log4shell"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('masscan', 'masscan', 'Quickly scan large amounts of IPs. Due to the quick scanning it may not always show accurate results.', '2', '{"IPV4NetBlock"}', '{"boefje/masscan"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('nikto', 'Nikto', 'Uses Nikto', '3', '{"HostnameHTTPURL"}', '{"boefje/nikto"}', '{"TEST_KEY"}', 'openkat/nikto', '{}', null, true),
      ('nmap-ip-range', 'Nmap IP range', 'Scan an IP range and store found IPs. Defaults to top-250 TCP and top-10 UDP on ranges with 1024 addresses or less (max is a /22). Larger ranges are skipped by default.', '2', '{"IPV6NetBlock", "IPV4NetBlock"}', '{"boefje/nmap-ip-range"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('nmap-ports', 'Nmap Ports', 'Scan a specific set of ports including service detection.', '2', '{"IPAddressV4", "IPAddressV6"}', '{"boefje/nmap-ports"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('nmap', 'Nmap TCP', 'Defaults to top 250 TCP ports. Includes service detection.', '2', '{"IPAddressV4", "IPAddressV6"}', '{"boefje/nmap"}', '{"TEST_KEY"}', 'ghcr.io/minvws/openkat/nmap:latest', '{"--open", "-T4", "-Pn", "-r", "-v10", "-sV", "-sS"}', null, true),
      ('nmap-udp', 'Nmap UDP', 'Defaults to top 250 UDP ports. Includes service detection.', '2', '{"IPAddressV4", "IPAddressV6"}', '{"boefje/nmap-udp"}', '{"TEST_KEY"}', 'ghcr.io/minvws/openkat/nmap:latest', '{"--open", "-T4", "-Pn", "-r", "-v10", "-sV", "-sU"}', null, true),
      ('nuclei-cve', 'Nuclei CVE scan', 'Nuclei is used to send requests across targets based on a template, providing fast scanning. (CVE scanning).', '3', '{"HostnameHTTPURL", "Hostname"}', '{"boefje/nuclei-cve"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('nuclei-exposed-panels', 'Nuclei Exposed panels', 'Nuclei is used to send requests across targets based on a template, providing fast scanning. Can be used to find specific exposed administrative panels in your network.', '3', '{"HostnameHTTPUR", "Hostname"}', '{"boefje/nuclei-exposed-panels"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('nuclei-takeover', 'Nuclei takeover scan', 'Nuclei is used to send requests across targets based on a template, providing fast scanning. This will try to perform a sub sub-domain takeover.', '3', '{"HostnameHTTPURL", "Hostname"}', '{"boefje/nuclei-takeover"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('rdns', 'Reverse DNS', 'Resolve IP addresses to a hostname.', '1', '{"IPAddressV4", "IPAddressV6"}', '{"boefje/rdns"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('retirejs-finding-types', 'RetireJS Finding Types', 'Hydrate information of RetireJS finding types.', '0', '{"RetireJSFindingType"}', '{"boefje/retirejs-finding-types"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('rpki', 'RPKI', 'Check BGP announcements to see if an IPv4 or IPv6 address has Validated ROA Payload (VRPs).', '1', '{"IPAddressV4", "IPAddressV6"}', '{"boefje/rpki"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('security_txt_downloader', 'Security.txt downloader', 'Downloads the security.txt file from the target website to check if it contains all the required elements.', '2', '{"Website"}', '{"boefje/security_txt_downloader"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('service_banner', 'Service banner download', 'Downloads service banners from the target hosts.', '2', '{"IPPort"}', '{"boefje/service_banner"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('shodan', 'Shodan', 'Use Shodan to find open ports with vulnerabilities that are found on that port. Requires an API key.', '1', '{"IPAddressV4", "IPAddressV6"}', '{"boefje/shodan"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('snyk', 'Snyk.io-vulnerabilities', 'Get Snyk.io vulnerabilities based on identified Software.', '1', '{"SoftwareInstance"}', '{"boefje/snyk"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('snyk-finding-types', 'SNYK Finding Types', 'Hydrate information of SNYK finding types.', '0', '{"SnykFindingType"}', '{"boefje/snyk-finding-types"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('ssl-certificates', 'SSLCertificates', 'Scan SSL certificates of websites. Checks if certificates are valid and/or expired.', '2', '{"Website"}', '{"boefje/ssl-certificates"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('ssl-version', 'SSLScan', 'Scan SSL/TLS versions (protocols) of websites. Will result in findings if outdated SSL/TLS versions are identified such as SSLv3. ', '2', '{"Website"}', '{"boefje/ssl-version"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('testssl-sh-ciphers', 'Testssl.sh Ciphers', 'Checks the SSL and TLS ciphers of a website for any insecure ciphers that are offered.', '2', '{"IPService"}', '{"boefje/testssl-sh-ciphers"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('webpage-analysis', 'WebpageAnalysis', 'Downloads a resource and uses several different normalizers to analyze', '2', '{"HTTPResource"}', '{"application/vnd.ms-powerpoint", "audio/mpeg", "application/json+har", "application/json", "application/msword", "application/x-troff-me", "application/oda", "application/postscript", "application/x-csh", "audio/x-pn-realaudio", "application/x-cpio", "image/x-portable-bitmap", "application/vnd.apple.mpegurl", "text/richtext", "application/x-dvi", "application/x-python-code", "application/x-hdf5", "audio/x-aiff", "application/x-sv4crc", "image/x-xbitmap", "application/x-ustar", "image/x-xpixmap", "application/x-troff-ms", "video/x-sgi-movie", "image/png", "video/x-msvideo", "boefje/webpage-analysis", "application/manifest+json", "text/tab-separated-values", "application/x-netcdf", "image/ief", "image/x-portable-anymap", "message/rfc822", "application/xml", "application/x-troff-man", "audio/basic", "openkat-http/body", "text/csv", "application/x-texinfo", "application/x-sh", "video/quicktime", "application/x-pkcs12", "image/tiff", "application/wasm", "text/x-setext", "openkat-http/headers", "application/zip", "image/x-portable-pixmap", "text/html", "application/x-pn-realaudio", "application/x-wais-source", "application/x-shar", "text/plain", "text/x-python", "text/css", "application/pkcs7-mime", "audio/x-wav", "application/x-tcl", "image/x-xwindowdump", "application/x-tex", "application/pdf", "application/x-hdf", "image/gif", "application/x-tar", "application/octet-stream", "image/vnd.microsoft.icon", "application/x-mif", "video/mpeg", "image/x-cmu-raster", "application/x-bcpio", "application/x-gtar", "video/mp4", "image/svg+xml", "image/jpeg", "image/x-portable-graymap", "application/javascript", "application/x-latex", "image/x-rgb", "video/webm", "application/x-sv4cpio", "application/x-shockwave-flash", "text/x-vcard", "text/xml", "text/x-sgml", "application/vnd.ms-excel", "image/x-ms-bmp", "application/x-troff"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('webpage-capture', 'Webpage Capture', 'Takes a screenshot of a webpage. Image can be found on the Tasks page in the downloadable ''meta and raw data'' file.', '2', '{"HostnameHTTPURL", "IPAddressHTTPURL"}', '{"application/har+json", "application/json", "boefje/webpage-capture", "image/png", "application/localstorage+json", "application/zip+json"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('wp-scan', 'WPScan', 'Scans WordPress websites.', '2', '{"SoftwareInstance"}', '{"boefje/wp-scan"}', '{"TEST_KEY"}', null, '{}', null, true),
      ('pdio-subfinder', 'Subfinder', 'A subdomain discovery tool. (projectdiscovery.io). Returns valid subdomains for websites using passive online sources. Beware that many of the online sources require their own API key to get more accurate data.', '1', '{"Hostname"}', '{"boefje/pdio-subfinder"}', '{"TEST_KEY"}', null, '{}', null, true)
    on conflict do nothing;

INSERT INTO normalizer (
  plugin_id,
  name,
  description,
  consumes,
  produces,
  environment_keys,
  version,
  static
) values
      ('kat_adr_finding_types_normalize', 'API Design Rules (ADR) Finding Types', 'Parse API Design Rules (ADR) finding types.', '{"boefje/adr-finding-types", "normalizer/kat_adr_finding_types_normalize"}', '{"ADRFindingType"}', '{"TEST_KEY"}', null, true),
      ('adr-validator-normalize', 'API Design Rules validator', 'Parses and validates the API Design Rules (ADR). https://www.forumstandaardisatie.nl/open-standaarden/rest-api-design-rules', '{"boefje/adr-validator", "normalizer/adr-validator-normalize"}', '{"APIDesignRule", "APIDesignRuleResult", "ADRFindingType", "Finding"}', '{"TEST_KEY"}', null, true),
      ('kat_answer_parser', 'Answer Parser', 'Parses the answers from ''Config'' objects. Config OOIs are used when your policies and objects need different treatment from the usual setup.', '{"answer", "normalizer/kat_answer_parser"}', '{"Config"}', '{"TEST_KEY"}', null, true),
      ('kat_binaryedge_containers', 'BinaryEdge containers', 'Parse BinaryEdge data to check if Kubernetes hosts have any vulnerabilities. Creates ''VERIFIED-VULNERABILITY'' findings.', '{"boefje/binaryedge", "normalizer/kat_binaryedge_containers"}', '{"KATFindingType", "SoftwareInstance", "Service", "IPPort", "Finding", "Software", "IPService", "CVEFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_binaryedge_databases', 'BinaryEdge databases', 'Parses BinaryEdge data to check if any Cassandra, ElasticSearch, Memcached, MongoDB and Redis servers are identified and parses the version number. Create ''EXPOSED-SOFTWARE'' findings.', '{"boefje/binaryedge", "normalizer/kat_binaryedge_databases"}', '{"KATFindingType", "SoftwareInstance", "Service", "IPPort", "Finding", "Software", "IPService", "CVEFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_binaryedge_http_web', 'BinaryEdge Websites', 'Parses BinaryEdge data to check for AWS secrets, F5 BIG IP loadbalancers and Citrix NetScaler.', '{"boefje/binaryedge", "normalizer/kat_binaryedge_http_web"}', '{"KATFindingType", "SoftwareInstance", "Service", "IPPort", "Finding", "Software", "IPService", "CVEFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_binaryedge_message_queues', 'BinaryEdge message queues', 'Parses BinaryEdge data to check for message queues (mqtt) servers. Creates the finding ''EXPOSED-SOFTWARE'' if mqtt servers are found.', '{"boefje/binaryedge", "normalizer/kat_binaryedge_message_queues"}', '{"KATFindingType", "SoftwareInstance", "Service", "IPPort", "Finding", "Software", "IPService", "CVEFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_binaryedge_protocols', 'BinaryEdge SSL/TLS protocols', 'Parses BinaryEdge data to check for various vulnerabilities within SSL/TLS protocols, such as Heartbleed, Secure Renegotiation and SSL Compression.', '{"boefje/binaryedge", "normalizer/kat_binaryedge_protocols"}', '{"KATFindingType", "SoftwareInstance", "Service", "IPPort", "Finding", "Software", "IPService", "CVEFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_binaryedge_remote_desktop', 'Binary Edge remote desktop', 'Parses BinaryEdge data to check for remote desktop services such as RDP, VNC and X11. Creates ''EXPOSED-SOFTWARE'' findings.', '{"boefje/binaryedge", "normalizer/kat_binaryedge_remote_desktop"}', '{"KATFindingType", "SoftwareInstance", "Service", "IPPort", "Finding", "Software", "IPService", "CVEFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_binaryedge_service_identification', 'BinaryEdge service identification', 'Parses BinaryEdge data to check if Software is present that is known for malware.', '{"boefje/binaryedge", "normalizer/kat_binaryedge_service_identification"}', '{"KATFindingType", "SoftwareInstance", "Service", "IPPort", "Finding", "Software", "IPService", "CVEFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_binaryedge_services', 'BinaryEdge services', 'Parses BinaryEdge data to check for services such as SSH, rsync, FTP, telnet and SMB.', '{"boefje/binaryedge", "normalizer/kat_binaryedge_services"}', '{"KATFindingType", "SoftwareInstance", "Service", "IPPort", "Finding", "Software", "IPService", "CVEFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_burpsuite_normalize', 'Burpsuite normalizer', 'Parses Burpsuite XML output into findings. Check https://docs.openkat.nl/manual/normalizers.html#burp-suite on how to create the XML file.', '{"xml/burp-export", "normalizer/kat_burpsuite_normalize"}', '{"Finding", "IPPort", "CVEFindingType"}', '{"TEST_KEY"}', null, true),
      ('calvin-normalize', 'Calvin', 'Produces applications and incidents for Calvin.', '{"boefje/calvin", "normalizer/calvin-normalize"}', '{"Application", "Incident"}', '{"TEST_KEY"}', null, true),
      ('kat_censys_normalize', 'Censys', 'Parses Cencys data into objects that can be used by other boefjes and normalizers. Can create ports, certificates, software, websites and headers. Doesn''t create findings.', '{"boefje/censys", "normalizer/kat_censys_normalize"}', '{"IPPort", "X509Certificate", "SoftwareInstance", "ResolvedHostname", "HTTPHeader"}', '{"TEST_KEY"}', null, true),
      ('kat_crt_sh_normalize', 'Certificate Transparency logs (crt.sh)', 'Parses data from certificate transparency logs (crt.sh) into hostnames and X509 certificates.', '{"boefje/certificate-search", "normalizer/kat_crt_sh_normalize"}', '{"Hostname", "X509Certificate"}', '{"TEST_KEY"}', null, true),
      ('kat_CVE_2023_35078_normalize', 'CVE-2023-35078 Ivanti EPMM', 'Checks if the Ivanti EPMM website is vulnerable to CVE-2023-35078. Produces a finding if it is vulnerable.', '{"boefje/CVE_2023_35078", "normalizer/kat_CVE_2023_35078_normalize"}', '{"Finding", "CVEFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_cve_2024_6387_normalize', 'CVE-2024-6387 OpenSSH', 'Checks the service banner for a race condition in OpenSSH server which can result in an unauthenticated remote attacker to trigger that some signals are handled in an unsafe manner (CVE-2024-6387). Requires the Service-Banner-boefje to be enabled.', '{"openkat/service-banner", "normalizer/kat_cve_2024_6387_normalize"}', '{"Finding", "CVEFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_cve_finding_types_normalize', 'CVE finding types', 'Parses Common Vulnerability Exposures (CVE) into findings.', '{"boefje/cve-finding-types", "normalizer/kat_cve_finding_types_normalize"}', '{"CVEFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_cwe_finding_types_normalize', 'CWE finding', 'Parses Common Weakness Enumeration (CWE) into findings.', '{"boefje/cwe-finding-types", "normalizer/kat_cwe_finding_types_normalize"}', '{"CWEFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_dicom_normalize', 'DICOM servers', 'Parses medical imaging data (DICOM) into findings and identified software.', '{"boefje/dicom", "normalizer/kat_dicom_normalize"}', '{"KATFindingType", "SoftwareInstance", "IPPort", "Finding", "Software"}', '{"TEST_KEY"}', null, true),
      ('kat_dns_normalize', 'DNS records', 'Parses DNS records. Can parse A, AAAA, CAA, CNAME, MX, NS, SOA, TXT, DKIM and DMARC data.', '{"boefje/dns-records", "normalizer/kat_dns_normalize"}', '{"IPAddressV6", "DNSARecord", "DNSNSRecord", "DNSTXTRecord", "DNSSOARecord", "NXDOMAIN", "DNSCNAMERecord", "DNSMXRecord", "Hostname", "Network", "DNSAAAARecord", "IPAddressV4", "DNSZone"}', '{"TEST_KEY"}', null, true),
      ('kat_dns_zone_normalize', 'DNS zone', 'Parses the parent DNS zone into new hostnames and DNS zones.', '{"boefje/dns-zone", "normalizer/kat_dns_zone_normalize"}', '{"Hostname", "DNSZone", "DNSSOARecord"}', '{"TEST_KEY"}', null, true),
      ('kat_dnssec_normalize', 'DNSSEC', 'Parses DNSSEC data into findings.', '{"boefje/dns-sec", "openkat/dnssec-output", "normalizer/kat_dnssec_normalize"}', '{"KATFindingType", "Finding"}', '{"TEST_KEY"}', null, true),
      ('kat_external_db_normalize', 'External database hosts fetcher', 'Parse the fetched host data from the external database into hostnames and IP-addresses.', '{"boefje/external_db", "normalizer/kat_external_db_normalize"}', '{"Hostname", "IPAddressV4", "IPV4NetBlock", "IPAddressV6", "IPV6NetBlock"}', '{"TEST_KEY"}', null, true),
      ('kat_fierce_normalize', 'Fierce', 'Parse the DNS reconnaissance data from Fierce into hostnames and/or IP addresses.', '{"boefje/fierce", "normalizer/kat_fierce_normalize"}', '{"IPAddressV6", "DNSARecord", "Hostname", "DNSAAAARecord", "IPAddressV4"}', '{"TEST_KEY"}', null, true),
      ('kat_generic_finding_normalize', 'Finding types', 'Parses data to create (CVE) Findings.', '{"openkat/finding", "normalizer/kat_generic_finding_normalize"}', '{"Finding", "CVEFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_green_hosting_normalize', 'Green Hosting', 'Parses the Green Hosting output into findings.', '{"boefje/green-hosting", "normalizer/kat_green_hosting_normalize"}', '{"KATFindingType", "Finding"}', '{"TEST_KEY"}', null, true),
      ('kat_kat_finding_types_normalize', 'KAT finding types', 'Parses KAT finding types.', '{"boefje/kat-finding-types", "normalizer/kat_kat_finding_types_normalize"}', '{"KATFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_leakix_normalize', 'LeakIX', 'Parses the LeakIX output into findings and identified software and services.', '{"boefje/leakix", "normalizer/kat_leakix_normalize"}', '{"KATFindingType", "SoftwareInstance", "Service", "IPPort", "Finding", "Software", "IPService", "CVEFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_manual_csv', 'Manual CSV', 'Parses uploaded CSV files into objects.', '{"manual/csv", "normalizer/kat_manual_csv"}', '{"OOI"}', '{"TEST_KEY"}', null, true),
      ('kat_manual_ooi', 'Manual OOI normalizer', 'Parses manually added objects.', '{"manual/ooi", "normalizer/kat_manual_ooi"}', '{"OOI"}', '{"TEST_KEY"}', null, true),
      ('kat_masscan_normalize', 'masscan', 'Parse output from masscan into open ports for each scanned IP.', '{"boefje/masscan", "normalizer/kat_masscan_normalize"}', '{"IPAddressV4", "IPAddressV6", "IPPort"}', '{"TEST_KEY"}', null, true),
      ('kat_nikto_normalize', 'Nikto', null, '{"boefje/nikto-output", "normalizer/kat_nikto_normalize"}', '{"Software", "SoftwareInstance", "Finding", "KATFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_nmap_normalize', 'nmap', 'Parses data from all nmap variants into IP-addresses, ports and services.', '{"boefje/nmap", "boefje/nmap-udp", "boefje/nmap-ports", "boefje/nmap-ip-range", "openkat/nmap-output", "normalizer/kat_nmap_normalize"}', '{"IPAddressV6", "Service", "IPPort", "IPAddressV4", "IPService"}', '{"TEST_KEY"}', null, true),
      ('kat_nuclei_cve_normalize', 'Nuclei CVE', 'Parses Nuclei CVE data into findings.', '{"boefje/nuclei-cve", "normalizer/kat_nuclei_cve_normalize"}', '{"Finding", "CVEFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_nuclei_exposed_panels_normalize', 'Nuclei exposed admin panels', 'Parses Nuclei of exposed panels into findings.', '{"boefje/nuclei-exposed-panels", "normalizer/kat_nuclei_exposed_panels_normalize"}', '{"Finding", "KATFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_nuclei_takeover_normalize', 'Nuclei takeover', 'Parses Nuclei takeover data into findings.', '{"boefje/nuclei-takeover", "normalizer/kat_nuclei_takeover_normalize"}', '{"Finding", "KATFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_rdns_normalize', 'Reverse DNS', 'Parses reverse DNS data into PTR records.', '{"boefje/rdns", "normalizer/kat_rdns_normalize"}', '{"DNSPTRRecord"}', '{"TEST_KEY"}', null, true),
      ('kat_report_data', 'Report data', 'Parses (uploaded) report data to create reports.', '{"openkat/report-data", "normalizer/kat_report_data"}', '{"ReportData"}', '{"TEST_KEY"}', null, true),
      ('kat_retirejs_finding_types_normalize', 'RetireJS finding types', 'Parses RetireJS data into findings.', '{"boefje/retirejs-finding-types", "normalizer/kat_retirejs_finding_types_normalize"}', '{"RetireJSFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_rpki_normalize', 'RPKI', 'Parses RPKI data into findings.', '{"rpki/results", "normalizer/kat_rpki_normalize"}', '{"Finding", "KATFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_sec_txt_downloader_normalize', 'Security.txt downloader', 'Parses the downloaded security.txt data from a website.', '{"boefje/security_txt_downloader", "normalizer/kat_sec_txt_downloader_normalize"}', '{"SecurityTXT", "Website", "URL"}', '{"TEST_KEY"}', null, true),
      ('kat_shodan_normalize', 'Shodan', 'Parses Shodan data into (CVE) findings and ports.', '{"boefje/shodan", "normalizer/kat_shodan_normalize"}', '{"Finding", "IPPort", "CVEFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_snyk_normalize', 'Snyk.io', 'Parses Snyk.io data into various findings.', '{"boefje/snyk", "normalizer/kat_snyk_normalize"}', '{"Finding", "KATFindingType", "SnykFindingType", "CVEFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_snyk_finding_types_normalize', 'Snyk.io finding types', 'Parses Snyk.io data into Finding Types. Required for the Snyk Normalizer.', '{"boefje/snyk-finding-types", "normalizer/kat_snyk_finding_types_normalize"}', '{"SnykFindingType"}', '{"TEST_KEY"}', null, true),
      ('kat_ssl_certificates_normalize', 'SSL certificates', 'Parses SSL certificates data into X509 certificates.', '{"boefje/ssl-certificates", "normalizer/kat_ssl_certificates_normalize"}', '{"X509Certificate"}', '{"TEST_KEY"}', null, true),
      ('kat_ssl_scan_normalize', 'SSL scan', 'Parses SSL scan version data into findings.', '{"boefje/ssl-version", "normalizer/kat_ssl_scan_normalize"}', '{"KATFindingType", "Finding"}', '{"TEST_KEY"}', null, true),
      ('kat_ssl_test_ciphers_normalize', 'SSL test ciphers', 'Parses TestSSL data into TLS ciphers.', '{"boefje/testssl-sh-ciphers", "normalizer/kat_ssl_test_ciphers_normalize"}', '{"TLSCipher"}', '{"TEST_KEY"}', null, true),
      ('kat_wappalyzer_normalize', 'Wappalyzer', 'Checks HTTP responses for Software versions.', '{"application/json+har", "normalizer/kat_wappalyzer_normalize"}', '{"Software", "SoftwareInstance"}', '{"TEST_KEY"}', null, true),
      ('kat_check_images', 'Webpage analysis check images for metadata', 'Checks images for metadata.', '{"image/jpeg", "image/jpg", "image/gif", "image/png", "image/bpm", "image/ico", "normalizer/kat_check_images"}', '{"ImageMetadata"}', '{"TEST_KEY"}', null, true),
      ('kat_find_images_in_html', 'Webpage analysis find images in html', 'Parses websites to find images.', '{"text/html", "normalizer/kat_find_images_in_html"}', '{"HTTPResource"}', '{"TEST_KEY"}', null, true),
      ('kat_webpage_analysis_headers_normalize', 'Webpage analysis HTTP headers', 'Parses the HTTP headers from websites.', '{"openkat-http/headers", "normalizer/kat_webpage_analysis_headers_normalize"}', '{"HTTPHeader"}', '{"TEST_KEY"}', null, true),
      ('kat_wpscan_normalize', 'WPscan', 'Creates findings from WPscan data.', '{"boefje/wp-scan", "normalizer/kat_wpscan_normalize"}', '{"Finding", "CVEFindingType"}', '{"TEST_KEY"}', null, true),
      ('pdio-subfinder-normalizer', 'PDIO subfinder', 'Parses ProjectDiscovery subfinder data for finding subdomains.', '{"boefje/pdio-subfinder", "normalizer/pdio-subfinder-normalizer"}', '{"Hostname"}', '{"TEST_KEY"}', null, true)
    on conflict do nothing;

INSERT INTO boefje_config (settings, boefje_id, organisation_pk)
SELECT s.values, b.id, s.organisation_pk FROM settings s
JOIN boefje b on s.plugin_id = b.plugin_id;

INSERT INTO boefje_config (enabled, boefje_id, organisation_pk)
SELECT p.enabled, b.id, p.organisation_pk FROM plugin_state p
  JOIN boefje b ON p.plugin_id = b.plugin_id
  LEFT JOIN boefje_config bc ON bc.boefje_id = b.id
WHERE bc.boefje_id IS NULL;

INSERT INTO normalizer_config (enabled, normalizer_id, organisation_pk)
SELECT p.enabled, n.id, p.organisation_pk FROM plugin_state p
  JOIN normalizer n ON p.plugin_id = n.plugin_id
  LEFT JOIN normalizer_config nc ON nc.normalizer_id = n.id WHERE nc.normalizer_id IS NULL;

UPDATE boefje_config bc SET enabled = p.enabled FROM plugin_state p
  JOIN boefje b ON p.plugin_id = b.plugin_id
WHERE b.id = bc.boefje_id AND p.organisation_pk = bc.organisation_pk;

UPDATE normalizer_config nc SET enabled = p.enabled FROM plugin_state p
  JOIN normalizer n ON p.plugin_id = n.plugin_id
WHERE n.id = nc.normalizer_id AND p.organisation_pk = nc.organisation_pk;

-- End of backward compatibility changes, we can safely drop the old tables.

DROP TABLE settings;
DROP TABLE plugin_state;
