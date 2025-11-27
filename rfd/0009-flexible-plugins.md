---
authors: Donny Peeters <@donnype>
state: implemented
discussion:
labels: Data Models, Plugins
---

# RFD 0009: Flexible (OCI) Plugins

## Introduction

Plugins are part of the core of OpenKAT.
They form the engine that continuously monitors important OOIs for Findings.
For both the community and experienced OpenKAT users,
being able to create, configure and extend plugins are perhaps the most important features we provide,
on the one hand because of the large open source community that provides vulnerability scanning scripts
and the fact that newly discovered threats need to be mitigated immediately,
and on the other hand because every organization is unique and needs tailored tooling as well to monitor their systems.

This means that managing plugins should be as easy as possible.
One big improvement has recently been to containerize all of our plugins by default in V2.
This means that users can host an image that adheres to our specification remotely and add it to OpenKAT manually,
also
see [this (outdated) design document](https://github.com/minvws/nl-kat-coordination/blob/fb613fc6d0ee9c446d39e8326f04036997ad7e52/docs/source/developer-documentation/boefjes-runner.md).
Note that to consistently get data in and out of the ephemeral plugin containers,
as the document states, we are really bound to using an internal API.

However, it has become clear that this does not make creating plugin images trivial:

1. To reuse code that talks with our internal API for multiple images, we had to create an intermediate OCI image.
2. We could not reuse the code for non-Python-images, requiring multiple implementations or a different base image.
3. Even for Python-based-images we needed to install extra requirements to talk to the API such as requests/httpx.
4. We need to maintain multiple versions of these images for multiple versions of the API. This would mean that we
   need to add upgrade logic to a release for older plugin versions and track which image supports which API
   version. (This has caused bugs already for images that were not pinned.)
   Since these plugins were only uploading files to the API, this suggests that the API contained too many
   implementation details such as the task context and the file encodings.
5. Adding even just a script as a new plugin meant creating, hosting and maintaining a whole new OCI image.

We also noticed that a lot of plugins started to boil down to starting a subprocess that called the native tool in the
container directly and return the output.
Moreover, we still cannot handle certain scenarios with the old current boefje-normalizer-bit-structure (also see
`rfd/0006-plugins-database-schema.md`):

1. It is not possible to trigger normalizers on two or more raw files
2. It is not possible to get other oois into a normalizer
3. It is not possible to run a boefje on multiple OOIs at once
4. It is not possible to normalize multiple raw files at once

But with the new schema from RFD 0006 and the level of control introduced in the design of RFD 0007,
it is possible to mitigate these limitations.

## Proposal

The core of this proposal is to:

1. As per RFD 0006, treat boefje and normalizers simply as _plugins_.
2. Allow plugins to talk to both file and object APIs, so they can gather the data they need themselves dynamically,
   instead of limiting this to a declarative definition of the input type (see the `consumes` field).
3. Create a binary that we can mount in any container as an entrypoint at runtime, that calls the cli command in the
   `oci_arguments` field and sends the output (`stdout`) as a file to our internal API.
4. For any plugins that we do write custom code for, aim to normalizer data right away where possible. Files that
   are needed for e.g. audit trailing can simply be sent to the API in the same task.
5. Scope what these ephemeral containers can access by creating a fine-grained authorization scheme: define before
   starting the container what it should be allowed to access, and pass a token that has these rights attached to it
   in the container that we can check in the API again once the container starts performing requests to the API.
6. As we still have the common path of running a boefje on one or multiple hostnames or IP addresses: provide a way
   to pass these in the `oci_arguments` field using e.g. a template string such as `{hostname}`. For running
   plugins on multiple objects we could consider mounting or fetching a file with hostnames or creating more intricate
   templating logic. This is however the second step and perhaps something to refine in another RFD.

### Functional Requirements (FR)

1. Plugin creation should be significantly simpler than V1, avoiding the need for intermediate OCI images
2. Plugins should be language-agnostic - not limited to Python-based implementations
3. Plugins should be able to access both file and object APIs dynamically
4. Plugins should have fine-grained, scoped permissions (not full API access)
5. Plugins should be easy to work with, support multiple input patterns such as single OOI, multiple OOIs, files,
   or no input (standalone)
6. Plugin API communication should be secure and authenticated

### Extensibility (Potential Future Requirements)

1. Support for plugin workflows (chaining multiple plugins together)
2. Support for plugin delegation (one plugin spawning sub-plugins with reduced permissions)
3. Support for long-running plugins (hours/days) with token refresh
4. Support for plugin result streaming (partial results before completion)

### Why the proposal covers the requirements

- **FR 1**: Binary entrypoint eliminates need for intermediate Python-based API client images
- **FR 2**: Universal Go binary works with any container image/language
- **FR 3**: JWT tokens grant access to both `/files/` and `/objects/` API endpoints
- **FR 4**: Permission scoping in JWT tokens restricts access by PK, search query, and pagination limits
- **FR 5**: Five execution modes (MODE 1-5) support all input patterns
- **FR 6**: JWT authentication with signature verification and expiration

- **Ex 1**: MODE 4 and MODE 5 allow plugins to process multiple files
- **Ex 2**: Can be implemented by having plugins create sub-tasks via API
- **Ex 3**: Future enhancement to JWT token system (see RFD 0017)
- **Ex 4**: Can stream via multiple API calls during execution

## Implementation

The flexible OCI plugin system from this RFD has been fully implemented with comprehensive support for all proposed
features.

### Plugin Entrypoint Binary System

**Location:** `plugins/plugins/entrypoint.go`

A **Go binary** serves as the universal entrypoint for all containerized plugins. This binary:

- Executes the plugin command specified in `oci_arguments`
- Downloads files using `{file/<id>}` placeholders by calling the file API
- Uploads command output back to the OpenKAT API
- Handles stdin/stdout redirection for data processing

The binary is deployed via a Docker named volume that is mounted into all plugin containers. This approach:

- Works without host filesystem dependencies
- Is fast (volume created once, reused by all containers)
- Is portable across Docker Compose, Kubernetes, and Swarm environments

**For detailed discussion of deployment options (download, host mount, runtime copy, named volume), see RFD 0016.**

### Plugin Authentication Tokens

**Location:** `openkat/auth/jwt_auth.py`

Plugins authenticate with the API using **JWT (JSON Web Tokens)** that are:

- Generated before container execution with scoped permissions
- Passed to containers via environment variables
- Validated at the API level without database lookups
- Automatically expired after task timeout
- Used for automatic task-to-object attribution

The token system supports fine-grained permission scoping at multiple levels:

- **PK-level**: Access to specific objects by primary key
- **Search-level**: Access filtered by query parameters
- **Limit-level**: Pagination restrictions

When objects are created via the API, the `task_id` from the JWT payload is automatically captured in the `ObjectTask`
model, providing full traceability from objects → tasks → plugins → schedules.

**For detailed discussion of JWT structure, permission scoping patterns, and task attribution, see RFD 0017.**

### File and Object API Access

Both APIs are accessible to plugins with proper token scoping:

**File API** (`files/viewsets.py`):

- `FileViewSet` - CRUD operations with download support
- `FileDownloadView` - Secure downloads with permission checks
- Integrated with `django-downloadview` for efficient serving

**Object API** (`objects/viewsets.py`):
All object types have API endpoints:

- `HostnameViewSet`, `IPAddressViewSet`, `NetworkViewSet`
- `IPPortViewSet`, `SoftwareViewSet`, `FindingViewSet`
- DNS record viewsets (A, AAAA, CNAME, MX, NS, PTR, TXT, CAA, SRV)

**Permission enforcement:**

- All viewsets use `KATMultiModelPermissions`
- JWT tokens are validated against required permissions
- PK-level access control prevents unauthorized object access

### OCI Arguments Templating

**Location:** `plugins/runner.py` (lines 297-345)

Comprehensive placeholder support with **5 execution modes**:

**Supported placeholders:**

```python
format_map = {
    "{file}": target,  # Current file ID
    "{ipaddress}": target,  # IP address target
    "{hostname}": target,  # Hostname target
    "{mail_server}": target,  # Mail server target
}

# Static file references (entrypoint fetches):
# {file/123} - stays as-is, entrypoint downloads file
```

**Execution Modes:**

1. **MODE 1 - Direct Arguments** (single target with placeholders):

   ```
   target: "example.com"
   oci_arguments: ["nslookup", "{hostname}"]
   Result: nslookup example.com
   ```

2. **MODE 2 - Standalone** (no target, plugin fetches own data):

   ```
   target: None
   Plugin fetches its own data via API or doesn't need data
   ```

3. **MODE 3 - Sequential** (multiple targets with placeholders):

   ```
   target: ["example.com", "test.org"]
   oci_arguments: ["tool", "{hostname}"]
   Runs: tool example.com && tool test.org
   Concatenates output
   ```

4. **MODE 4 - Bulk stdin** (multiple targets without placeholders):

   ```
   target: ["example.com", "test.org"]
   oci_arguments: ["xargs", "-I", "%", "tool", "%"]
   IN_FILE environment variable: newline-separated targets:
       example.com
       test.org
   ```

5. **MODE 5 - File Processing**:
   ```
   oci_arguments: ["parse-nmap", "{file/123}"]
   Entrypoint fetches file and replaces with local path
   ```

### Fine-Grained Authorization Scope

Permissions are scoped before each plugin execution based on the plugin's declared needs and the specific task inputs.
The runner generates a JWT token with:

- Base permissions (all plugins can create files)
- Input-specific permissions (access to specific input files by PK)
- Plugin-declared permissions (from `plugin.permissions` field)

Permission validation occurs at the API level for every request, enforcing restrictions on:

- Object access by primary key
- Search query parameters
- Pagination limits

This ensures plugins can only access the resources they need for their specific task execution.

**For authentication implementation details, see RFD 0017.**

### Configuration Environment Variables

| Variable            | Default                 | Purpose                                               |
| ------------------- | ----------------------- | ----------------------------------------------------- |
| `ENTRYPOINT_VOLUME` | `plugin-entrypoint`     | Docker volume for entrypoint binary (see RFD 0015)    |
| `OPENKAT_HOST`      | `http://localhost:8000` | API endpoint for containers                           |
| `DOCKER_NETWORK`    | `bridge`                | Docker network for containers                         |
| `PLUGIN_TIMEOUT`    | `15` minutes            | Container timeout and token expiration (see RFD 0016) |
