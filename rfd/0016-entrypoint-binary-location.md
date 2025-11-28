---
authors: Donny Peeters <@donnype>
state: implemented
discussion:
labels: Plugins, Containers, Infrastructure
---

# RFD 0015: Entrypoint Binary Location

## Introduction

In OpenKAT V2's flexible plugin system (RFD 0009),
we use a binary entrypoint that replaces the container's native entrypoint to provide a communication layer that:

- Executes the plugin command specified in `oci_arguments`
- Downloads files referenced as `{file/<id>}` placeholders
- Uploads command output to the OpenKAT API
- Handles authentication via JWT tokens for these calls
- Manages stdin/stdout redirection

The critical question is: **How to get this binary into the ephemeral plugin containers in development and production?**
The old implementation used a bind mount from the docker host (with a leaky environment variable) to the dynamic
plugin containers. This is not possible in general for many container orchestrators such as Kubernetes.

## Problem Statement

We need a mechanism to inject the entrypoint binary into plugin containers that:

1. Doesn't require modifying plugin images
2. Is maintainable and doesn't complicate deployments
3. Is performant and doesn't slow down container startup significantly
4. Survives container restarts and updates
5. Works nicely in both development and production environments

## Options

1. Download Binary from URL at Runtime
2. Volume Mount from Host
3. Copy Binary into Container at Runtime using `container.put_archive()`
4. Named Docker Volume: create a named volume, populate it with the binary, and mount it into all plugin containers.

### Comparison of Options

| Aspect                 | 1: Download                | 2: Host Mount        | 3: Runtime Copy | **4: Named Volume**       |
| ---------------------- | -------------------------- | -------------------- | --------------- | ------------------------- |
| **Complexity**         | Low                        | Low                  | High            | Medium: volume management |
| **Maintainability**    | Medium: version management | Low                  | Medium          | **High**: see above       |
| **Host dependencies**  | None                       | Strong: permissions? | None            | None                      |
| **Network dependency** | Strong                     | None                 | None            | None                      |
| **Startup speed**      | Slow (first)               | Fast                 | Medium          | Fast                      |
| **Security**           | Weak                       | Strong               | Strong          | Strong                    |
| **Portability**        | High                       | Low: update per host | High            | High                      |
| **K8s support**        | Yes                        | Difficult            | Yes             | **Yes**                   |

## Proposal

**Implement Option 4: Named Docker Volume** as the primary implementation strategy for the following reasons:

1. **No Host Dependencies**: Works without modifying the host filesystem
2. **Fast**: Volume is created once, all containers mount it instantly
3. **Portable**: Works in Docker Compose, Kubernetes, Swarm
4. **Secure**: No network downloads, binary bundled with application
5. **Maintainable**: Clear volume lifecycle, easy to inspect

**Configuration:**

```python
# settings.py
ENTRYPOINT_VOLUME = env("ENTRYPOINT_VOLUME", default="openkat-plugin-entrypoint")
```

**Volume lifecycle:**

- **Creation**: On first OpenKAT startup or explicit initialization
- **Update**: Delete volume and recreate (can be automated)
- **Cleanup**: Manual deletion or via `docker volume prune`

### Functional Requirements (FR)

1. Binary injection must not require modifying plugin images
2. May not induce overhead on running plugins
3. Must work in both development and production environments
4. Must be maintainable and easy to update

## Implementation

The named Docker volume approach has been implemented as proposed, see `plugins/runner.py`.

### Binary Building

The Go binary is built in the main Dockerfile in a separate build-stage during OpenKAT deployment, see the `Makefile`
and `plugins/plugins/entrypoint.go`.

**Useful scripts for inspecting the volume:**

```bash
docker volume inspect openkat-plugin-entrypoint
docker run --rm -v openkat-plugin-entrypoint:/plugin alpine ls -lah /plugin
```

**Updating/cleanup the entrypoint:**

```bash
docker volume rm openkat-plugin-entrypoint
```

### Kubernetes Adaptation

For Kubernetes deployments, the named volume can be replaced with a PersistentVolume.

### Functional Requirements Coverage

- **FR 1**: No plugin image modifications required
- **FR 2**: Fast startup
- **FR 3**: Works in dev (Docker Compose) and prod (K8s with PVC)
- **FR 4**: Replacing the volume on a redeployment is just a little extra work.

### Future Considerations

1. **Automatic Updates**: Detect when entrypoint binary changes, recreate the volume automatically
2. **Binary Verification**: Checksum validation, signature verification, tamper detection etc.
