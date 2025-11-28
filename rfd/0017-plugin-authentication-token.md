---
authors: Donny Peeters <@donnype>
state: implemented
discussion:
labels: Security, Authentication, Plugins, Tasks
---

# RFD 0017: Plugin Authentication Token

## Introduction

In OpenKAT V2, plugins run in ephemeral containers that need to communicate with the internal API to download input
files, upload output files and create and retrieve objects.

To secure this communication, we need an authentication mechanism that:

1. Authenticates the containers
2. Authorize containers to access only the resources they need
3. Expires automatically to limit exposure
4. Can be generated and validated efficiently, not inducing overheads for running plugins

Moreover, we need to track which tasks created which objects for attribution and audit purposes.

## Proposal

The core of this proposal is to:

1. Use **JWT** for plugin authentication
2. Generate tokens on the fly with granular, scoped permissions
3. Still pass tokens to containers via **environment variables** as we are doing already
4. Validate tokens at the API level granularly
5. Add a permissions field on plugins to specify required permissions on top of the default permissions.
6. Encode **the task id in token payload** to enable automatic object-to-task attribution

JWT offers a stateless mechanism for authentication, which saves us the hassle of managing the tokens in the
database and risk not properly deleting these (though short-lived) tokens. This saves a lot of database round trips
and allows us to store the permissions specification in the payload at the same time.

Point 5 is special as it was a recent insight from a different requirement. The plugins talk to the API through a
callback, and every API call should be tied/scoped around the task plugins run in to decide how to store the objects.
But just like in user interfaces all data is stored for the current user, instead of creating a task-id-scoped API
especially for plugins, they could post the task id in their token. This has the added benefit that the current code
does not have to change at all in the plugins: the old token and api are passed already, and we only need to pass a
new value for the new token - passing the token is the same. This observation gives us more confidence that the api
endpoint and token could be a good minimal set of env variables each plugin needs and we can support that
implementation for a long time. (Note that this works both ways: we could change the authentication and authorization
to a stateful token again without rewriting the plugins.)

We could consider moving the plugin id to the token as well, but this hasn't been implemented at the time of writing.

### Functional Requirements (FR)

1. Plugins should be able to authenticate with the API using a token
2. Tokens should only grant access to resources (files/objects) needed for the task, with permissions per resource
3. Tokens should automatically expire after task completion or timeout
4. Objects created by plugins should be linked to their task

### Extensibility (Potential Future Requirements)

1. A token refresh mechanism for long-running tasks

## Implementation

The plugin authentication token system has been implemented as described.

### JWT Token Permissions

JWT tokens are generated before container execution with embedded permissions based on the django permissions, for
example:

```json
{
  "permissions": {
    "files.add_file": {},
    "files.view_file": { "pks": [123, 456] },
    "files.download_file": { "pks": [123] },
    "objects.add_hostname": {},
    "objects.view_ipaddress": { "search": "network=internet" }
  },
  "task_id": "uuid-of-task",
  "iat": 1234567890,
  "exp": 1234568790
}
```

The keys in the `permissions` field define the resource, and the value the fine-grained permissions on the resource.
Plugin permissions are added at runtime in `plugins/runner.py`.

### Permission Scoping Patterns

#### Pattern 1: Specific Resource Access (PK-based)

```python
"files.download_file": {"pks": [123, 456, 789]}
```

- Plugin can only download files with IDs 123, 456, or 789

#### Pattern 2: Query-Restricted Access (search-based)

```python
"objects.view_hostname": {"search": "network=internet"}
```

- Plugin can only list hostnames from the network `internet`

#### Pattern 3: Unlimited Creation

```python
"objects.add_dnsarecord": {}
```

- Plugin can create unlimited DNS A records
- No restrictions on the data access

#### Pattern 4: Limited Pagination

```python
"objects.list_ipaddress": {"limit": 100}
```

- Plugin can list IP addresses but max 100 per request

### Task Attribution via JWT Payload

The `ObjectTaskResultMixin` automatically does attribution when objects are created, see `objects/viewsets.py`:

```python
class ObjectTask(XTDBNaturalKeyModel):
    task_id = models.CharField(max_length=36)  # UUID from JWT
    type = models.CharField(max_length=32, default="plugin")
    plugin_id = models.CharField(max_length=64)
    output_object = models.CharField()  # OOI primary key

    _natural_key_attrs = ["task_id", "output_object"]
```

This gives:

- Automatic attribution without plugin code changes
- Enables tracing/auditing: object → task → plugin → schedule
- Supports audit queries: "which objects did task X create?"
- Links objects to files via TaskResult

### Configuration

**Settings** (`settings.py`):

```python
JWT_KEY = env.str("JWT_KEY", SECRET_KEY)
JWT_ALGORITHM = env.str("JWT_ALGORITHM", "HS256")
PLUGIN_TIMEOUT = env.int("PLUGIN_TIMEOUT", default=15)  # in minutes
```

**Relevant environment variables for containers:**

- `OPENKAT_TOKEN`: The JWT token
- `OPENKAT_HOST`: API base URL (e.g., `http://openkat:8000/api/v1/`)

### Functional Requirements Coverage

- **FR 1**: Plugins authenticate and authorize using JWT tokens via Authorization header
- **FR 2**: Tokens grant access only to specific resources via permission scoping
- **FR 3**: Tokens automatically expire after `PLUGIN_TIMEOUT` minutes
- **FR 4**: Task attribution is automatic via `ObjectTaskResultMixin`
