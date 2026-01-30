# Design considerations for new boefjes runner

The new boefjes runner will run boefjes in a containerized environment. This
ensures isolation of code and dependencies, and allows for easy distribution
of boefjes outside the KAT repository and release cycle.

A boefje can be written in any language, as long as it follows the I/O contract
(see below) and it is properly packaged in an OCI image.

## Images

[OCI images][oci-spec] will be
used to package the boefjes' code, its dependencies (libraries) and required
tools such as Nmap.

[oci-spec]: https://github.com/opencontainers/image-spec/blob/main/spec.md

### Distribution

OCI images can be distributed in any OCI registry, such as Docker Hub or
GitHub Container Registry. Several open source projects are available to
create a self-hosted OCI registry, such as [Harbor][harbor].

In the future, boefjes can be imported into the KATalogus using its OCI image URL. It can
be pinned to a version-specific tag, SHA256 identifier, or simply use the `latest`
tag. A JSON list of recommended boefjes will be included with each OpenKAT release,
or published to https://openkat.nl.

[harbor]: https://goharbor.io/

### Metadata

To import a boefje into the KATalogus, we need some of its metadata. We can
distribute this metadata together with the image by leveraging the [OCI image
manifest][oci-manifest-spec]. For example, we could add an annotation to the
manifest with a well-known name and predefined format, such as JSON, or add
multiple annotations for each metadata attribute.

The essential metadata includes:

- Name
- Version
- Description
- Image URL
- Settings schema
- List of OOI types that the boefje works on
- Boefjes runner HTTP API version
- Minimum compatible KAT version (for OOI schema compatibility)

[oci-manifest-spec]: https://github.com/opencontainers/image-spec/blob/main/manifest.md

## I/O

Because stdin and stdout in container orchestrators are relatively complicated
and work on a best-effort basis, this is not reliable enough for boefje input
and output. Also see the [OpenAPI docs](http://localhost:8006/docs),
where you can also find the full [OpenAPI specification](http://localhost:8006/openapi.json).
Kubernetes will for example redirect stdout and stderr to log files
and will by default rotate the log file when it gets larger than 10 MB. See the
[Kubernetes logging documentation][kubernetes-logging] for more information
about this. Tools like [filebeat][filebeat-kubernetes] also work by mounting the
host `/var/log/containers` in the filebeat container. This is something that can
be done with a cluster component like filebeat that is supposed to have access
to the log files of all containers. This should not be done with an application
like OpenKAT, because OpenKAT should not have access to the log files of other
applications that are running on the Kubernetes cluster.

Copying files from the container is also not an option, because for example the
`kubectl cp` command to copy files from a container actually executes `tar` in
the container using `kubectl exec`. There is also no guarantee that the
container will be around when it's done, because after the container exits it is
usually removed right away.

Because of this we designed a simple HTTP API for input and output. This HTTP
API will be part of new boefjes runner and will communicate with existing parts
of KAT such as bytes and mula (the scheduler) to get the boefje input and save
its output.

The HTTP API will be versioned, so that the API can evolve while staying
compatible with existing boefjes.

[kubernetes-logging]: https://kubernetes.io/docs/concepts/cluster-administration/logging/#how-nodes-handle-container-logs
[filebeat-kubernetes]: https://www.elastic.co/guide/en/beats/filebeat/current/running-on-kubernetes.html

### Input

The container will get a URL of an API endpoint that will provide its input as
one of its command line arguments. The container will then make a GET request
to this URL to get the input.

The input is a JSON object, specified by the following JSON schema:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://openkat.nl/boefje_input.schema.json",
  "type": "object",
  "title": "Boefje input",
  "additionalProperties": false,
  "properties": {
    "output_url": {
      "type": "string"
    },
    "task": {
      "properties": {
        "id": {
          "format": "uuid",
          "type": "string"
        },
        "data": {
          "properties": {
            "id": {
              "format": "uuid",
              "type": "string"
            },
            "boefje": {
              "properties": {
                "id": {
                  "minLength": 1,
                  "type": "string"
                },
                "version": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ],
                  "default": null
                },
                "oci_image": {
                  "anyOf": [
                    {
                      "type": "string"
                    },
                    {
                      "type": "null"
                    }
                  ],
                  "default": null
                }
              },
              "required": ["id"],
              "type": "object"
            },
            "input_ooi": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "null"
                }
              ],
              "default": null
            },
            "arguments": {
              "additionalProperties": true,
              "default": {},
              "type": "object"
            },
            "organization": {
              "type": "string"
            },
            "environment": {
              "anyOf": [
                {
                  "additionalProperties": {
                    "type": "string"
                  },
                  "type": "object"
                },
                {
                  "type": "null"
                }
              ],
              "default": null
            }
          },
          "required": ["id", "boefje", "organization"],
          "type": "object"
        }
      },
      "required": ["id", "data"],
      "type": "object"
    }
  },
  "required": ["output_url", "task"]
}
```

### Output

When the container is finished, it can POST its output to the URL specified in
the input JSON object. The output is a JSON object, specified by the following
JSON schema:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://openkat.nl/boefje_output.schema.json",
  "title": "Boefje output",
  "type": "object",
  "properties": {
    "status": {
      "enum": ["COMPLETED", "FAILED"],
      "type": "string"
    },
    "files": {
      "anyOf": [
        {
          "items": {
            "properties": {
              "name": {
                "type": "string"
              },
              "content": {
                "contentEncoding": "base64",
                "type": "string"
              },
              "tags": {
                "anyOf": [
                  {
                    "items": {
                      "type": "string"
                    },
                    "type": "array",
                    "uniqueItems": true
                  },
                  {
                    "type": "null"
                  }
                ],
                "default": null
              }
            },
            "required": ["name", "content"],
            "type": "object"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    }
  },
  "required": ["status"]
}
```

The tags for each file can include a MIME type.

## Logging

Logging will be captured through the container's orchestrator/runtime API and
stored in Bytes. Alternatively, the boefje can output its own logging in a
separate file as part of its output, which will be stored in Bytes as well.

## Runtimes

### Docker

Docker containers can be run as one-off jobs by creating a container, polling
its status on a regular interval, and removing it when it is finished.

An official, well-maintained Python API is available:

- https://pypi.org/project/docker/
- https://docker-py.readthedocs.io/en/stable/
- https://github.com/docker/docker-py

Logging can be captured through the API, but the specifics of available on the
logging driver: https://docs.docker.com/config/containers/logging/json-file/

### Kubernetes

Kubernetes has a specific object type for one-off workloads:
[Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/).

These Jobs can be created through the Kubernetes API, and their status can be
polled (pull-based) or watched (push-based) through the API as well.

An official, well-maintained Python API is available:

- https://pypi.org/project/kubernetes/
- https://github.com/kubernetes-client/python

Logging can be captured [through the API][k8s-logs-api], but logs get rotated so
a large volume of logs may not be fully available. See
https://kubernetes.io/docs/concepts/cluster-administration/logging/ for more
details.

[k8s-logs-api]: https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.27/#read-log-pod-v1-core

### Nomad

Nomad can run one-off jobs by setting the job type to 'batch':

- https://developer.hashicorp.com/nomad/docs/job-specification/job#type
- https://developer.hashicorp.com/nomad/docs/schedulers#batch

An unofficial Python API is available:

- https://pypi.org/project/python-nomad/
- https://github.com/jrxfive/python-nomad

Logging can be captured [through the API][nomad-logs-api],
but Nomad does not retain logs for long periods of time. From
https://developer.hashicorp.com/nomad/tutorials/manage-jobs/jobs-accessing-logs:

> While the logs command works well for quickly accessing application logs, it
> generally does not scale to large systems or systems that produce a lot of log
> output, especially for the long-term storage of logs. Nomad's retention of log
> files is best effort, so chatty applications should use a better log retention
> strategy.

[nomad-logs-api]: https://developer.hashicorp.com/nomad/api-docs/client#stream-logs

## Building images with this spec from the current boefjes

The approach to building OCI images from the boefjes we currently have in our
system has been discussed in [this ticket][ticket], with the first versions
having been implemented in these PRs:

- https://github.com/SSC-ICT-Innovatie/nl-kat-coordination/pull/2709
- https://github.com/SSC-ICT-Innovatie/nl-kat-coordination/pull/2832

### Summary of decisions

We decided not to focus on the following:

- We are **not** going to provide plain zip archives in the near future.
- Discoverability of images from external repositories (potentially containing
  multiple boefjes) will be pushed to later versions of OpenKAT.

In terms of how we are going to build images, we decided to:

- Just leverage Docker as this has to be available for OpenKAT devs anyway.
- Aim to keep the build scripts flexible but simple, e.g. for `kat_dnssec` we have:

```
docker build -f ./boefjes/plugins/kat_dnssec/boefje.Dockerfile -t openkat/dns-sec --build-arg BOEFJE_PATH=./boefjes/plugins/kat_dnssec .
```

- Use, as shown above, the [naming convention][dockerfile-naming] for Dockerfiles
  since we may want to add normaliser Dockerfiles in the same directory.
- Use a Python base image for all our boefjes, so we can use shared Python code to
  communicate with the boefjes API. Since there is no one tool available across Docker base images
  that can perform HTTP communication, we might as well use Python for this. Other possible tools to perform HTTP
  communication are curl, wget and/or other HTTP clients. Later, we can consider
  creating platform-specific, pre-built binaries using languages such as Go or Rust.
- In particular, build the images using a `python:3.11-slim` base image. A basic check shows the following
  sizes per base image, but Alpine [does not support standard PyPI wheels][wheels]:

| python:3.11 | python:3.11-slim | python:3.11-alpine |
| ----------- | ---------------- | ------------------ |
| 1.01 GB     | 157 MB           | 57 MB              |

In terms of when to build images, we decided to:

- Make the builds part of the installation script through `make -C boefjes images`.
- Put the responsibility to (re)build new images while developing boefjes on developers.

[ticket]: https://github.com/SSC-ICT-Innovatie/nl-kat-coordination/issues/2443
[dockerfile-naming]: https://docs.docker.com/build/building/packaging/#filename
[wheels]: https://pythonspeed.com/articles/alpine-docker-python/

## Limitations

In this design the boefjes runner will create a new container for each task,
which has a non-negligible overhead. This overhead can be reduced by batching
multiple tasks in a single container run. This design does not currently
consider that to ensure the implementation is as simple as possible. It can be
added to the runner in the future, but will also require changes to the KAT
scheduler to support scheduling batched tasks. Also see the following issues
and discussions to see the progress on this (performance) feature:

- https://github.com/minvws/nl-kat-coordination/issues/2613
- https://github.com/minvws/nl-kat-coordination/issues/2857
- https://github.com/minvws/nl-kat-coordination/issues/2811
