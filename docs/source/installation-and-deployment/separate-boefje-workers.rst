Separate Boefje Workers
=======================

At this point, all of the boefjes built by OpenKAT are equipped with two possible commands:

- The regular command of providing an input URL as specified in :doc:`/developer-documentation/boefjes-runner` as a
  positional argument.
- Another command where only flags are provided, in which case the container will start a long running process to poll
  the boefje API for new tasks.

The second option is new. It allows users to start separate workers for specific boefjes that need to run often or run elsewhere.
It also gives a lot more flexibility when scaling horizontally.

.. code:: shell

    $ docker run ghcr.io/minvws/openkat/nmap --help
    Usage: python -m worker [OPTIONS] [INPUT_URL]

    Options:
      -p, --plugins TEXT              A list of plugin ids to filter on.
      -l, --log-level [DEBUG|INFO|WARNING|ERROR]
                                      Log level
      --help                          Show this message and exit.

This long running process will automatically filter the scheduler on tasks for the ``OCI_IMAGE`` specified through its env.
Additionally, you could start the process with a filter on specific plugin ids, like so:

.. code:: shell

    $ docker run --network nl-kat-coordination_boefjes ghcr.io/minvws/openkat/nmap -p nmap-udp  # optional filter
    1970-17-28T15:26:16.333927 [info] Starting runtime
    1970-17-28T15:26:16.334173 [info] Configured BoefjeAPI [base_url=http://boefje:8000, outgoing_request_timeout=30, images=['ghcr.io/minvws/openkat/nmap:latest'], plugins=['nmap-udp']]
    1970-17-28T15:26:16.331262 [info] Created worker pool for queue 'boefje'
    1970-17-28T15:26:16.334481 [info] Started listening for tasks from worker pid=16
    1970-17-28T15:26:16.334501 [info] Started listening for tasks from worker pid=17
    HTTP Request: POST http://boefje:8000/api/v0/scheduler/boefje/pop?limit=1 "HTTP/1.1 200 OK"

Note that to start a container in "worker-mode", it
needs access to the network of the boefje API. This may have a
different name for your installation based on your compose project.

This provides a potential performance boost when starting and stopping Docker images for each tasks gives a lot of overhead.
Especially the generic image is a good target as this holds many fairly simple boefjes.
