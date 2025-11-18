Plugin System
=============

OpenKAT v2 plugins are containerized applications that scan objects and produce data. Plugins run as OCI (Docker) containers, making them isolated and language-agnostic.

Overview
--------

Plugins execute as containerized tasks and can:

- Scan network objects (hostnames, IP addresses, etc.)
- Create objects via the OpenKAT API
- Be scheduled on object sets
- Run as any language/runtime in a container

Plugin Structure
----------------

Plugins are defined in JSON configuration files located in ``plugins/plugins/``:

- ``plugins.json`` - Core plugin definitions
- ``nuclei_plugins.json`` - Nuclei-based plugins
- ``finding_types.json`` - Finding type definitions
- ``business_rules.py`` - Business rule definitions

Each plugin directory contains:

.. code-block:: text

   plugins/plugins/
   ├── plugins.json           # Plugin metadata
   ├── kat_dns/
   │   ├── main.py            # Plugin script
   │   └── description.md     # User-facing documentation
   └── kat_nmap/
       ├── main.py
       └── description.md

Plugin Definition
-----------------

Plugins are defined in ``plugins.json``:

.. code-block:: json

   {
     "plugin_id": "dns",
     "name": "DNS",
     "description": "Fetch the DNS record(s) of a hostname.",
     "scan_level": 1,
     "consumes": ["type:hostname"],
     "oci_image": "ghcr.io/minvws/openkat/plugins:0.1.0",
     "oci_arguments": ["uv", "run", "kat_dns/main.py", "{hostname}"],
     "permissions": {
       "objects.view_hostname": {},
       "objects.add_ipaddress": {}
     }
   }

Plugin Fields
^^^^^^^^^^^^^

- **plugin_id**: Unique identifier for the plugin
- **name**: Human-readable name
- **description**: What the plugin does
- **scan_level**: Minimum scan level required (0-4)
- **consumes**: Input types (``type:hostname``, ``type:ipaddress``, or ``file:plugin-id``)
- **oci_image**: Docker image to use
- **oci_arguments**: Command and arguments to run in the container
- **permissions**: Django permissions required by the plugin
- **batch_size**: (Optional) Number of objects to process in one batch
- **recurrences**: (Optional) How often to run on same object

Placeholders in OCI Arguments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- ``{hostname}`` - Replaced with hostname value
- ``{ipaddress}`` - Replaced with IP address value
- ``{file}`` - Replaced with file path (for normalizers)

Plugin Types
------------

Scanner Plugins
^^^^^^^^^^^^^^^

Scanners take an object as input and produce raw data:

.. code-block:: json

   {
     "plugin_id": "nmap",
     "name": "Nmap",
     "scan_level": 2,
     "consumes": ["type:ipaddress"],
     "oci_image": "instrumentisto/nmap",
     "oci_arguments": ["nmap", "--top-ports", "250", "-oX", "-", "{ipaddress}"]
   }

Normalizer Plugins
^^^^^^^^^^^^^^^^^^

Normalizers process output files from scanners:

.. code-block:: json

   {
     "plugin_id": "parse-nmap",
     "name": "Parse NMAP XML",
     "scan_level": 2,
     "consumes": ["file:nmap", "file:masscan"],
     "oci_image": "ghcr.io/minvws/openkat/plugins:0.1.0",
     "oci_arguments": ["uv", "run", "kat_nmap/main.py", "{file}"]
   }

Writing a Plugin Script
------------------------

Plugin scripts receive environment variables and communicate via the OpenKAT API:

.. code-block:: python

   import os
   import json
   import httpx
   import argparse

   def main():
       # Get API credentials from environment
       token = os.getenv("OPENKAT_TOKEN")
       base_url = os.getenv("OPENKAT_API")

       # Parse command line arguments
       parser = argparse.ArgumentParser()
       parser.add_argument("hostname")
       args = parser.parse_args()

       # Perform scanning logic
       results = scan_hostname(args.hostname)

       # Create API client
       client = httpx.Client(
           base_url=base_url,
           headers={"Authorization": f"Token {token}"}
       )

       # Store objects via API
       response = client.post("/objects/", json={
           "hostname": [
               {"network": "internet", "name": args.hostname}
           ],
           "ipaddress": [
               {"network": "internet", "address": "192.0.2.1"}
           ]
       })

       # Output results to stdout
       print(json.dumps(results))

   if __name__ == "__main__":
       main()

Environment Variables
^^^^^^^^^^^^^^^^^^^^^^

Plugins receive these environment variables:

- ``OPENKAT_TOKEN``: Authentication token for API
- ``OPENKAT_API``: Base URL of the OpenKAT API
- ``OPENKAT_TASK_ID``: (Optional) Task ID for tracking
- ``OPENKAT_ORGANIZATION_CODE``: Organization code

API Endpoints
^^^^^^^^^^^^^

Common API endpoints for plugins:

.. code-block:: http

   # Create objects (bulk)
   POST /objects/
   {
     "hostname": [...],
     "ipaddress": [...],
     "dnsarecord": [...]
   }

   # Get an object
   GET /objects/hostname/?name=example.com

   # Delete DNS records
   DELETE /objects/hostname/internet|example.com/dnsrecord/?record_id=1,2,3

Plugin Execution Flow
----------------------

The plugin execution follows this sequence:

1. User schedules plugin on object set via Django interface
2. Django creates a Task for each object in the set
3. Celery worker fetches the Task from the queue
4. Celery runs the OCI container with specified arguments
5. Container executes the plugin script
6. Plugin script POSTs objects to the API
7. API stores objects in XTDB database
8. Container exits with status code
9. Celery marks Task as COMPLETED

Registering Plugins
-------------------

Plugins are automatically synced from ``plugins.json`` on startup. The ``sync()`` function in ``plugins/sync.py`` reads JSON files and creates/updates database records:

.. code-block:: python

   # plugins/sync.py
   from plugins.models import Plugin

   def sync() -> list[Plugin]:
       raw_plugins = []
       raw_plugins.extend(json.loads(Path("plugins/plugins/plugins.json").read_text()))

       for raw_plugin in raw_plugins:
           plugin = Plugin(
               plugin_id=raw_plugin.get("plugin_id"),
               name=raw_plugin.get("name"),
               scan_level=raw_plugin.get("scan_level", 1),
               # ... other fields
           )

       return Plugin.objects.bulk_create(plugins, update_conflicts=True, update_fields=[...])

To add a new plugin:

1. Add entry to ``plugins/plugins/plugins.json``
2. Restart the application (plugins are synced on startup)

Scheduling Plugins
------------------

Via Web Interface
^^^^^^^^^^^^^^^^^

1. Navigate to ``/plugins/``
2. Click on a plugin
3. Click "Schedule"
4. Select object set and interval
5. Save schedule

Via API
^^^^^^^

.. code-block:: http

   POST /api/v1/schedules/
   {
     "plugin_id": "dns",
     "object_set_id": 123,
     "interval": "PT24H",
     "enabled": true
   }

Manually Trigger
^^^^^^^^^^^^^^^^

Run a plugin immediately on an object:

.. code-block:: http

   POST /api/v1/tasks/
   {
     "type": "plugin",
     "data": {
       "plugin_id": "dns",
       "input_data": "internet|example.com"
     }
   }

Plugin Development
------------------

Creating a New Plugin
^^^^^^^^^^^^^^^^^^^^^

1. **Create plugin script** in ``plugins/plugins/kat_myplugin/main.py``:

   .. code-block:: python

      import os
      import httpx
      import argparse

      def main():
          token = os.getenv("OPENKAT_TOKEN")
          base_url = os.getenv("OPENKAT_API")

          parser = argparse.ArgumentParser()
          parser.add_argument("hostname")
          args = parser.parse_args()

          # Your scanning logic here

          client = httpx.Client(
              base_url=base_url,
              headers={"Authorization": f"Token {token}"}
          )

          # Store results via API
          client.post("/objects/", json={...})

      if __name__ == "__main__":
          main()

2. **Add to plugins.json**:

   .. code-block:: json

      {
        "plugin_id": "my-plugin",
        "name": "My Plugin",
        "description": "Does something useful",
        "scan_level": 1,
        "consumes": ["type:hostname"],
        "oci_image": "ghcr.io/minvws/openkat/plugins:0.1.0",
        "oci_arguments": ["uv", "run", "kat_myplugin/main.py", "{hostname}"]
      }

3. **Restart application** to sync the plugin

Testing Plugins Locally
^^^^^^^^^^^^^^^^^^^^^^^^

Run the plugin container manually:

.. code-block:: bash

   # Build plugin image (if needed)
   docker build -f plugins/plugins/plugins.Dockerfile -t my-plugins .

   # Run plugin
   docker run --rm \
     -e OPENKAT_TOKEN="your-token" \
     -e OPENKAT_API="http://localhost:8000/api/v1" \
     my-plugins \
     uv run kat_dns/main.py example.com

Using External OCI Images
^^^^^^^^^^^^^^^^^^^^^^^^^^

You can use any publicly available Docker image:

.. code-block:: json

   {
     "plugin_id": "custom-scanner",
     "oci_image": "your-registry/scanner:latest",
     "oci_arguments": ["scan", "{hostname}"]
   }

The container must write objects to the OpenKAT API using provided environment variables.

Generic Entrypoint and Arbitrary Images
----------------------------------------

OpenKAT uses a generic entrypoint mechanism that allows you to use **any OCI-compatible container image** as a plugin, regardless of the language or tool it contains.

How It Works
^^^^^^^^^^^^

When a plugin task runs:

1. OpenKAT's task runner executes the specified ``oci_image`` with ``oci_arguments``
2. The container runs your command and writes output to **stdout**
3. The generic entrypoint script (implemented in Go) **captures all stdout**
4. The captured output is **automatically saved as a file** in OpenKAT
5. The file is associated with the task and made available for processing

This means you can use **any existing Docker image** without modification:

.. code-block:: json

   {
     "plugin_id": "nmap-scanner",
     "oci_image": "instrumentisto/nmap",
     "oci_arguments": [
       "nmap",
       "-sV",
       "--top-ports",
       "100",
       "-oX",
       "-",
       "{ipaddress}"
     ]
   }

In this example:

- The standard ``nmap`` Docker image is used directly
- Nmap outputs XML to stdout (the ``-`` in ``-oX -`` means stdout)
- OpenKAT captures the XML output and saves it as a file
- A separate normalizer plugin can then parse this XML file

Scanner + Normalizer Pattern
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This architecture encourages a **two-stage plugin pattern**:

**Stage 1: Scanner Plugin (arbitrary image)**

- Uses any existing tool's Docker image
- Runs the tool and outputs raw data to stdout
- No OpenKAT-specific code needed
- Output is automatically saved as a file

**Stage 2: Normalizer Plugin (OpenKAT integration)**

- Consumes the file from the scanner
- Parses the raw output
- Communicates with OpenKAT API to create objects
- Requires OpenKAT integration code

Example configuration:

.. code-block:: json

   [
     {
       "plugin_id": "nmap",
       "name": "Nmap Port Scanner",
       "oci_image": "instrumentisto/nmap",
       "oci_arguments": ["nmap", "-oX", "-", "{ipaddress}"],
       "consumes": ["type:ipaddress"]
     },
     {
       "plugin_id": "parse-nmap",
       "name": "Parse Nmap XML",
       "oci_image": "ghcr.io/minvws/openkat/plugins:0.1.0",
       "oci_arguments": ["uv", "run", "kat_nmap/main.py", "{file}"],
       "consumes": ["file:nmap"],
       "permissions": {
         "objects.add_ipport": {},
         "objects.add_ipservice": {}
       }
     }
   ]

Advantages of This Approach
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Reuse Existing Tools**: Use any scanning tool available as a Docker image (nmap, nikto, nuclei, masscan, etc.) without modification.

**Language Agnostic**: Scanner tools can be written in any language; you only need to write the normalizer in Python (or any language that can make HTTP requests).

**Separation of Concerns**: Scanning logic is separate from OpenKAT integration logic.

**Faster Development**: Focus on writing parsing/normalization code rather than implementing scanning functionality.

**Community Tools**: Leverage the vast ecosystem of existing security tools packaged as containers.

Example: Using Nuclei
^^^^^^^^^^^^^^^^^^^^^^

`Nuclei <https://github.com/projectdiscovery/nuclei>`_ is a popular vulnerability scanner with thousands of templates. You can use it directly:

.. code-block:: json

   {
     "plugin_id": "nuclei",
     "name": "Nuclei Scanner",
     "oci_image": "projectdiscovery/nuclei",
     "oci_arguments": ["nuclei", "-u", "{url}", "-json"],
     "consumes": ["type:url"]
   }

Then write a simple normalizer to parse Nuclei's JSON output and create findings in OpenKAT.

What You Need to Write
^^^^^^^^^^^^^^^^^^^^^^^

In most cases, you only need to write **normalizer plugins** that:

1. Read the file produced by the scanner
2. Parse the output format (JSON, XML, CSV, etc.)
3. Extract relevant information
4. Create OpenKAT objects via the API

The scanner itself runs in its native container without any modifications.

Plugin Permissions
------------------

Plugins can declare required Django permissions:

.. code-block:: json

   {
     "permissions": {
       "objects.view_hostname": {},
       "objects.add_hostname": {},
       "objects.add_ipaddress": {},
       "objects.delete_dnsarecord": {}
     }
   }

Permissions are checked before task execution. Tasks are rejected if the plugin's permissions aren't granted.

Advanced Permissions
^^^^^^^^^^^^^^^^^^^^

File access permissions with search:

.. code-block:: json

   {
     "permissions": {
       "files.view_file": {
         "search": ["bgp-download", "rpki-download"],
         "limit": 1
       }
     }
   }

Batch Processing
----------------

Plugins can process multiple objects in a batch:

.. code-block:: json

   {
     "plugin_id": "rpki",
     "batch_size": 500,
     "consumes": ["type:ipaddress"],
     "oci_arguments": ["uv", "run", "kat_rpki/main.py"]
   }

When ``batch_size`` is set, the plugin receives multiple objects and must query them via the API.

Best Practices
--------------

1. **Error Handling**: Return non-zero exit codes on failure
2. **Timeouts**: Implement reasonable timeouts for network operations
3. **Logging**: Write logs to stderr (stdout is for data output)
4. **Idempotency**: Plugins should be safe to run multiple times
5. **API Usage**: Always use the API to store objects
6. **Resource Cleanup**: Clean up temporary files before exit
7. **Documentation**: Provide clear description.md files
8. **Testing**: Test plugins with various inputs
9. **Security**: Never log sensitive data (tokens, credentials)
10. **Container Size**: Keep OCI images small for faster startup

Example: Complete Plugin
-------------------------

Plugin configuration in ``plugins/plugins/plugins.json``:

.. code-block:: json

   {
     "plugin_id": "ssl-checker",
     "name": "SSL Certificate Checker",
     "description": "Checks SSL certificates for expiry and validity",
     "scan_level": 2,
     "consumes": ["type:hostname"],
     "oci_image": "ghcr.io/minvws/openkat/plugins:0.1.0",
     "oci_arguments": ["python", "kat_ssl/main.py", "{hostname}"],
     "permissions": {
       "objects.add_finding": {}
     }
   }

Plugin implementation in ``plugins/plugins/kat_ssl/main.py``:

.. code-block:: python

   import os
   import ssl
   import socket
   import httpx
   import argparse
   from datetime import datetime

   def check_ssl_cert(hostname: str) -> dict:
       try:
           context = ssl.create_default_context()
           with socket.create_connection((hostname, 443), timeout=10) as sock:
               with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                   cert = ssock.getpeercert()

                   # Parse expiry date
                   not_after = datetime.strptime(
                       cert['notAfter'],
                       '%b %d %H:%M:%S %Y %Z'
                   )
                   days_until_expiry = (not_after - datetime.now()).days

                   return {
                       "hostname": hostname,
                       "expiry_date": cert['notAfter'],
                       "days_remaining": days_until_expiry,
                       "issuer": dict(x[0] for x in cert['issuer'])
                   }
       except Exception as e:
           return {"error": str(e)}

   def main():
       token = os.getenv("OPENKAT_TOKEN")
       base_url = os.getenv("OPENKAT_API")

       parser = argparse.ArgumentParser()
       parser.add_argument("hostname")
       args = parser.parse_args()

       # Check certificate
       result = check_ssl_cert(args.hostname)

       if "error" not in result and result["days_remaining"] < 30:
           # Create finding for expiring certificate
           client = httpx.Client(
               base_url=base_url,
               headers={"Authorization": f"Token {token}"}
           )

           client.post("/objects/", json={
               "finding": [{
                   "finding_type": "SSL_EXPIRY_WARNING",
                   "object": f"internet|{args.hostname}",
                   "description": f"SSL certificate expires in {result['days_remaining']} days"
               }]
           })

       print(json.dumps(result))

   if __name__ == "__main__":
       main()
