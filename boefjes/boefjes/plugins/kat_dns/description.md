# DNS

The DNS boefje queries a configured recursive DNS resolver for records associated with an input hostname. It uses `dnspython` (not `dsnpython`). It also performs separate TXT lookups for `_dmarc.<hostname>` and `_domainkey.<hostname>`.

### Input OOI

- `Hostname`: the hostname to query.

### Configuration

- `REMOTE_NS`: recursive resolver address; defaults to `1.1.1.1`.
- `RECORD_TYPES`: optional comma-separated selection of record types. By default the boefje queries `A`, `AAAA`, `CAA`, `CERT`, `RP`, `SRV`, `TXT`, `MX`, `NS`, `CNAME`, `DNAME`, `SOA`, `LOC`, and `GPOS`. Unsupported names cause a configuration error (with the DNS improvements patch applied). These are **queried** types, not all normalized OOI types.

When `SOA` is selected, the boefje additionally searches parent names for a zone SOA record. DMARC and DKIM-related TXT lookups are performed separately from `RECORD_TYPES`.

### Output OOIs

The normalizer creates OOIs for the following DNS record types:

| OOI type                         | Description                                                                            |
| -------------------------------- | -------------------------------------------------------------------------------------- |
| `Hostname`                       | Input hostname and hostnames discovered in relevant DNS records                        |
| `DNSZone`                        | Zone associated with a discovered SOA record                                           |
| `IPAddressV4` / `IPAddressV6`    | IP addresses from A and AAAA answers                                                   |
| `DNSARecord` / `DNSAAAARecord`   | A and AAAA records linking hostnames and addresses                                     |
| `DNSSOARecord`                   | SOA records and their metadata                                                         |
| `DNSTXTRecord`                   | TXT records                                                                            |
| `DNSMXRecord`                    | Mail exchanger records                                                                 |
| `DNSNSRecord`                    | Nameserver records                                                                     |
| `DNSCNAMERecord`                 | CNAME records                                                                          |
| `DNSCAARecord`                   | Certification authority authorization records                                          |
| `DNSLOCRecord` / `DNSGPOSRecord` | Geographic location records; associated `GeographicPoint` objects may also be produced |
| `DMARCTXTRecord`                 | Parsed DMARC TXT data when recognized by the normalizer                                |
| `DKIMExists`                     | DKIM-related presence indication when recognized by the normalizer                     |

`CERT`, `RP`, `SRV`, and `DNAME` may be queried but are **not currently mapped to dedicated DNS record OOIs** by this normalizer.

### DNS failures and diagnostics

The boefje distinguishes missing answers from resolver failures. With the follow-up patch applied, successful answers can be preserved when another lookup fails, and optional `query_errors` diagnostics describe per-record lookup failures such as `NXDOMAIN`, `NOANSWER`, `TIMEOUT`, and `NO_NAMESERVERS`. This diagnostic field is part of the raw boefje output, not an OOI.

The boefje requests Extended DNS Error (EDE) information and can recognize certain DNSSEC-related resolver errors. It does **not** independently validate DNSSEC signatures; results depend on the configured resolver and its support for EDE.

### Email-security limitations

A DMARC TXT record being present does not establish that the policy is valid or effective. Full DMARC policy validation is not implemented here. DKIM uses a lookup at `_domainkey.<hostname>`; it does **not** enumerate selector-specific keys, so it cannot establish that DKIM signing is configured correctly for every sender.

### Operational considerations

DNS results depend on the recursive resolver, its caching, and the time of the query. A timeout or SERVFAIL/REFUSED is not proof that a record is absent. Run the boefje's tests and normalizer compatibility checks when changing supported record types or raw result formats.
