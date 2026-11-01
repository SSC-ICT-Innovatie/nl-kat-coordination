# LeakIX

LeakIX is a project that goes around the Internet and finds services to index them.
They gather information on the Internet on the most common security misconfigurations currently open.

### Input OOIs

LeakIX expects an IPAddressV4, IPAddressV6 or Hostname as input.

### Output OOIs

LeakIX currently outputs the following OOIs:

| OOI type                    | Description                                                            |
| --------------------------- | ---------------------------------------------------------------------- |
| AutonomousSystem            | The AS announcing the scanned IP (netblocks are left to other boefjes) |
| IPAddressV4/IPAddressV6     | IP address the event was observed on                                   |
| IPPort                      | Open port found on the input OOI                                       |
| Hostname                    | Hostname of the event and hostnames from certificate SANs              |
| Software / SoftwareInstance | Detected software (service, modules, HTTP headers, OS, SSH banner)     |
| X509Certificate             | TLS certificate observed by LeakIX, including SAN links                |
| KATFindingType / Finding    | Leak findings and outdated TLS/SSL protocol version findings           |
| CVEFindingType              | Known vulnerability of the software behind the port                    |

### Extraction components

Each extraction component can be disabled through a boefje setting
(`enabled`/`disabled`, all enabled by default):

| Setting                       | Extracts                                                     |
| ----------------------------- | ------------------------------------------------------------ |
| `LEAKIX_EXTRACT_ASN`          | AutonomousSystem                                             |
| `LEAKIX_EXTRACT_CERTIFICATES` | X509Certificate + SAN hostnames                              |
| `LEAKIX_EXTRACT_SOFTWARE`     | Software from service info, modules, HTTP headers and the OS |
| `LEAKIX_EXTRACT_SSH`          | SSH server software from SSH banners                         |
| `LEAKIX_EXTRACT_TLS`          | Findings for outdated TLS/SSL protocol versions              |
