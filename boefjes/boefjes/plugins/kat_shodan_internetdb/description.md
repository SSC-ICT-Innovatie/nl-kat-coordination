# Shodan InternetDB

Fast IP Lookups for Open Ports and Vulnerabilities. Only free for non-commercial use. The API gets updated once a week.

See: https://internetdb.shodan.io/, https://internetdb.shodan.io/docs

## Return Schema:

```
{
  "cpes": [
    "string"
  ],
  "hostnames": [
    "string"
  ],
  "ip": "string",
  "ports": [
    0
  ],
  "tags": [
    "string"
  ],
  "vulns": [
    "string"
  ]
}
```

Tags are discarded in the normalizer.
