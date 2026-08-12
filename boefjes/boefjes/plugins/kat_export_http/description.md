# Export to HTTP api

This Boefje can be configured to run on selected OOIs with a selected clearance level, it then exports these OOIs to the configured HTTP endpoint.
Configure by copying this Boefje, and provinding Input OOIs of your choice. Limit Exported Objects by selecting an appropriate Scan Level.

### Input OOIs

Select your own desired inputs by creating a variant. By doing so the user can also select the Scan level, this limits the exported OOIs to only those who have received a high enough scan level, possibly ignoring objects outside of the scope of your organization.

### Configurables """

EXPORT_HTTP_ENDPOINT an http(s) url possibly containing Basic Auth credentials
EXPORT_REQUEST_HEADERS, an enter separated list of headers to be send with the request. Useful for injecting api-tokens.
EXPORT_HTTP_VERB, GET, POST, DEL, PUT, PATCH, defaults to POST
EXPORT_REQUEST_PARAMETER, optional named url/post parameter. If none is given the data will be posted as json body.
EXPORT_HTTP_ORGANIZATION_IDENTIFIER, optional overwritable organization name, defaults to the organization identiefier to which the OOI belongs. Will be added to the params / post data as 'organizaton'.
TIMEOUT defaults to 15
USERAGENT defaults to OpenKAT
REQUESTS_CA_BUNDLE optional local CA bundle file path when dealing with internal / self-signed servers.
