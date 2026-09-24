Observability
=============

OpenTelemetry
-------------

OpenTelemetry is a way to trace requests through the system. It is used to find out where a request is going wrong and to instrument performance problems. OpenTelemetry is not enabled by default, but can be enabled by uncommenting the environment variable ``SPAN_EXPORT_GRPC_ENDPOINT`` in the ``.env`` file.

Jaeger: Distributed Tracing
---------------------------

The `Jaeger <https://www.jaegertracing.io>`_ tracing system is used to view the traces. It can be enabled by enabling the `Docker Compose profile <https://docs.docker.com/compose/profiles/#enable-profiles>`_, for example by running ``docker-compose --profile jaeger up -d`` or using ``export COMPOSE_PROFILES=jaeger`` and then running Make as usual. The Jaeger UI can then be found at `http://localhost:16686`.

Pyroscope: Continuous Profiling
-------------------------------

Pyroscope is a continuous profiling tool that helps you understand the performance of your applications. It collects and visualizes profiling data, allowing you to identify performance bottlenecks and optimize resource usage. You'll be able to see how much CPU time is spent in different parts of your code, which functions are taking the most time, and how memory is being used over time.

1. Start openkat
2. ``docker compose --profile monitoring up -d``
3. Check `http://localhost:4040/` for pyroscope to see if it is working
4. Check `http://localhost:4000/a/grafana-pyroscope-app/explore` to see if it is working
