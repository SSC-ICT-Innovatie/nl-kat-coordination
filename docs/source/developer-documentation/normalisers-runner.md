# Design considerations for new normalisers (whiskers) runner

_Status: Draft_

## Current situation

The current workflow is as follows:

```{mermaid}
graph LR;
    Mula--Tasks-->Boefjes;
    Boefjes--Information-->Bytes;
    Bytes--Information-->Whiskers;
    Whiskers--Objects-->Octopoes;
```

This diagram is simplified, because normalisers (whiskers) are actually scheduled by Mula as well.

normalisers are run within the context of the normalisers runner, within the Python process of the normalisers runner. This does not provide any isolation or sandboxing. There is currently also no method to redistribute normalisers, other than by copying the code to the normalisers runner.

## Requirements

[**_By Jan_**](https://github.com/minvws/nl-kat-coordination/issues/1136#issuecomment-1584306551)

Initially, our design called for normalisers as AWS Lambda-like functions. This would make it possible to run them in micro-VMs/micro-containers and distribute them as small code packages (e.g., code + requirements) targeting a specific pre-built Python (or other interpreter) container running on, for example, [Firecracker](https://firecracker-microvm.github.io).

This has a few advantages:

- The code of normalisers runs sandboxed.
- The input can be a single raw file (easily testable).
- They can be run in parallel.
- The output is easily tested by testing the returned objects for value and schema validity. (e.g. using [JSON Schema Validation](https://python-jsonschema.readthedocs.io/en/stable/validate/))
- The whole normaliser can be hashed, and as such, we can keep track of what we did with which code/input/output.
- Crashes can be caught at the runtime level and reported without boilerplate inside the normaliser.
- Support for multiple languages can be added.
- normalisers can carry conflicting dependencies without issue.
- Easily packaged (zip, OCI container of which the last might be overkill).
- Separation of runner code (e.g., Python 3.10 with a set of reasonable modules) and app code (e.g., the main method doing the heavy lifting).

This also has a few requirements:

- normalisers do not interact with the outside world (already met except for 1 normaliser who contacts Octopoes).
- normalisers list their requirements (already met).
- The Input and Output are text or binary blobs. (currently, the output is a Python object holding data mirroring the Octopoes model).

This also has a few drawbacks (some we can minimize):

- Startup time for a sandboxed normaliser is longer than for a direct method call.
- Not all functionality envisioned can be captured in a sandboxed normaliser which has no other I/O options than the initial raw file + job meta and the resulting output.
- Inter-related objects in the output stream are 'harder' to relate to each other than with Python's references. (maybe solvable by using something akin to [JSON Schema references ($ref)](https://json-schema.org/understanding-json-schema/structuring.html#ref))
- One-shot return of data, as the runner only processes all output once the container has returned.

Options that this gives us:

- Output can be JSON, and optionally with versioned schemas.
- Run various separate runner envs (e.g., Python 3.8, Python 3.9, PHP 7, PHP 8), needs requirements to be set in the normaliser manifest.
- Cache normaliser dependencies.

## Design

### Runtime

| Technology                     | Security                             | Startup overhead | Ease of Use | Distribution             |
| ------------------------------ | ------------------------------------ | ---------------- | ----------- | ------------------------ |
| MicroVM (Firecracker)          | Excellent isolation                  | High             | Hard        | VM image                 |
| Containers (Docker)            | Medium isolation                     | Medium-high      | Moderate    | OCI image                |
| Containers (hardened runtimes) | Excellent isolation                  | High             | Moderate    | OCI image                |
| WebAssembly                    | High isolation, sandboxed            | Medium-low       | Hard        | Several                  |
| Python Subprocess              | Limited isolation, security concerns | Medium-low       | Easy        | Zipfile with Python code |
| Python Inline                  | Limited isolation, security concerns | Low              | Easy        | Zipfile with Python code |

#### MicroVM (Firecracker)

- **Security:** Excellent isolation, leverages hardware security
- **Startup overhead:** High
- **Ease of Use:** Hard, hardware virtualisation extensions (Intel VT-x or AMD-V) are required. Nested virtualisation needs to be enabled to run in an existing virtual machine. As a developer, integrating Firecracker with existing code is not trivial and needs quite a bit of work to get right.
- **Distribution:** VM image with OS and userspace. The [Weave Ignite](https://github.com/weaveworks/ignite) project allow OCI images to be used, but this project is in alpha and seems abandoned by the authors. Building custom VM images is more work and requires build tooling that might not be available everywhere.

#### Containers (Docker)

- **Security:** Medium isolation, leverages Linux namespaces
- **Startup overhead:** Medium-high
- **Ease of Use:** Moderate, Docker is easy to run but does have some moving parts compared to a simple Python process. A big advantage is that many organisations already use Docker. There are many other container orchestrators such as Kubernetes and Nomand in use, but these require the use of a different API (but do use the same container image for distribution).
- **Distribution:** [OCI image](https://github.com/opencontainers/image-spec/blob/main/spec.md), with many build tools available (including in CI like GitHub Actions). OCI images can be distributed using [OCI registries](https://github.com/opencontainers/distribution-spec/blob/main/spec.md) and metadata can be provided in the OCI image manifest.

#### Containers (hardened runtimes)

Other container runtimes, such as [Kata Containers](https://katacontainers.io) or [gVisor](https://gvisor.dev) can provide excellent isolation while using the same OCI image distribution format used by Docker. When using container ochestrators such as Kubernetes, these runtimes can be used as a drop-in replacement for Docker. This means that the same OCI image can be used for distribution, and the same API can be used to run the container. For security-conscious organisations, using these hardened runtimes can provide additional security guarantees without requiring special adaptations in KAT.

- **Security:** Excellent isolation
- **Startup overhead:** High
- **Ease of Use:** Moderate, the runtime can be harder to set up than Docker, but the rest of the workflow is the same.
- **Distribution:** OCI image (see above)

#### WebAssembly (Wasm)

"[WebAssembly](https://webassembly.org) (abbreviated *Wasm*) is a binary instruction format for a stack-based virtual machine. Wasm is designed as a portable compilation target for programming languages, enabling deployment on the web for client and server applications."

- **Security:** High isolation, designed to run untrusted code in a secure sandbox
- **Startup overhead:** Medium-low
- **Ease of Use:** Hard, Python support for targeting WASI (WebAssembly System Interface) is relatively new. Also, modules using native code (such as Pydantic V2) cannot easily be compiled to WebAssembly at this time.
- **Distribution:** Several methods are available. A [Python zipapp](https://docs.python.org/3/library/zipapp.html) makes it possible to create a single small package with the normaliser code and any PyPI libraries. However, the relatively big Python standard library will need to made available separately. There have been [work to build Python code and all dependencies into a single Wasm module](https://blog.suborbital.dev/bringing-python-to-se2-with-webassembly), but it is unknown how well this works in practice. Support for OCI images exists, but mostly to be able to run WASM modules in container runtimes (e.g. [containerd runwasi](https://github.com/containerd/runwasi), [Docker+Wasm](https://www.docker.com/blog/docker-wasm-technical-preview/) for Docker desktop, [Podman with WasmEdge](https://wasmedge.org/docs/develop/deploy/podman/)).

#### Others

- Python Subprocess is easy to use, but has limited isolation and security concerns.
- Python Inline is simple, but has limited scalability and security concerns.
- Python Subprocess and Python Inline can use a Zipfile with Python code for distribution, which is relatively easy to use.

### Distribution

Distribution with OCI images would be the preferred way. OCI images have several advantages, namely that they provide immutable, reproducible, and verifiable builds.

It is possible to add metadata to the OCI image's manifest, which can be used to store information about the normaliser, such as the name, version, dependencies and input + output metadata.

Furthermore it is easy to distribute OCI images, as they can be pushed to a registry, and pulled from a registry such as Docker Hub, GitHub Container Registry, or Amazon Elastic Container Registry.

Unfortunately, not all runtimes discussed above can directly use OCI images. This means we would need to do extra work to either a) support a different distribution mechanism or b) use libraries to adapt OCI images for our runtime.

### Input/Output

The normaliser input is the Normaliser Meta object and a single raw file, and the output is a single normalised file. The input is a binary file coming from Bytes. The output is a JSON file of OOIs and Findings that is sent to Octopoes.

This Input/Output protocol needs to be specified more thoroughly and implemented before the new normalisers runner can be fully implemented. This can be done using the existing codebase, and we could include the new I/O protocol side by side to the current one so that we don't have to migrate all normalisers at the same time.

### Supervisor process

A single independent process that can be scaled horizontally (multiple processes) to provide multiple workers. The process works independently, meaning that there is no communication between the processes. The processes can be scaled up and down depending on the load and can be run on a single machine, or on multiple machines (e.g. using container orchestrator). They do not need to be aware of each other. The existing PostgreSQL is used to synchronise state.

## Discussion

- Do we want to support multiple languages for normalisers?
- Do we want to persist the normaliser output in Bytes, or send it directly to Octopoes?
- Do we want to align the runtime with one that can also work for Boefjes?
- Do we want to have support for multiple raw files as input?
- Do we want to reuse a running normaliser for multiple inputs, or do we set up and tear down the normaliser for each run?

## Conclusions

_As discussed with the team on 2023-07-20._

- The new normalisers output format should be refined and implemented outside the scope of the new normalisers runner.
- We need better development tooling (an SDK) for normalisers. A Python tool that takes a ZIP file from Bytes, runs the normaliser, and shows normaliser output on screen was proposed and would greatly help the development cycle.
- A new boefjes runner should be prioritised higher than the normalisers runner because we have more issues with the current boefjes runner: boefjes have more diverse dependencies and require external tools. We can likely reuse a part of the boefjes runner for normalisers.
- We should not forget about bits; these also need a better design.
- Overhead for runner normalisers should be limited, for example by allowing batched requests or multiple runs without having to restart the normaliser.
