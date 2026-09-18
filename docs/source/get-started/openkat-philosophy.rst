The OpenKAT philosophy
======================

OpenKAT continuously collects information about an IT environment, connects that information, and analyzes it to identify security risks.

The easiest way to understand OpenKAT is to follow what happens when you give it something to investigate.

From discovery to finding
-------------------------

Suppose you want to monitor `example.org`. OpenKAT can start by collecting information about the hostname.

A simplified flow might look like this:

.. code-block:: text

      example.org
        |
        v
      DNS information
        |
        v
      IP address
        |
        v
      Open ports
        |
        v
      Services
        |
        v
      Software
        |
        v
      Vulnerabilities
        |
        v
      Findings

Each step can provide information that makes the next step possible.

For example, discovering an IP address can make it possible to scan for open ports. An open port can reveal a service, which can provide information about the software running on that service. That software can then be checked for known vulnerabilities.

OpenKAT stores the information discovered along the way and uses the relationships between pieces of information to determine what can be discovered or analyzed next.

The main components
-------------------

OpenKAT separates the process of collecting, storing and analyzing information into different components.

At a high level, the process looks like this:

.. code-block:: text

      Information sources
        |
        v
      Collection
        |
        v
      Normalization
        |
        v
      Data model
        |
        v
      Analysis History
        |
        v
      Findings
        |
        v
      Reports

This separation makes OpenKAT modular. Different tools can be used to collect information, while the same data model and analysis mechanisms can be used to work with the results.

Objects of Interest
-------------------

OpenKAT represents information about an environment as Objects of Interest (OOIs).

An OOI represents something that OpenKAT knows about. Examples include:

- a hostname;
- an IP address;
- a URL;
- a network service;
- a port;
- a piece of software; or
- a vulnerability.

OOIs can be related to each other. For example, a hostname can resolve to an IP address, and an IP address can expose a service.

These relationships are important because they allow OpenKAT to build a connected view of an environment instead of storing every scan result separately.

Collecting information with Boefjes
-----------------------------------

OpenKAT uses Boefjes to collect information.

A Boefje is a small piece of software that performs a specific task. It might call an external tool, query a database, perform a network scan, or retrieve information from another source.

For example, a Boefje could:

- query DNS;
- perform a port scan;
- retrieve certificate information;
- query a vulnerability database; or
- run an external security tool.

The output of a Boefje is an observation that can be processed by OpenKAT.

Normalizing observations with Whiskers
--------------------------------------

Different tools produce information in different formats. OpenKAT therefore separates the raw output of a tool from the structured information that is added to the data model.

Whiskers transform observations into objects that OpenKAT understands.

For example, a tool might report:

.. code-block:: text

      93.184.216.34:443
      nginx/1.24.0

OpenKAT can turn this into structured objects representing an IP address, port, service and software.

This makes information from different tools comparable and allows it to be connected to information already known by OpenKAT.

The data model
--------------

The resulting objects are stored and connected in OpenKAT's data model.

A simplified example is:

.. code-block:: text

      Hostname
      |
      +---- resolves to ----> IP address
      |
      +---- exposes ----> Port
      |
      +---- runs ----> Service
      |
      +---- uses ----> Software
      |
      +---- affected by ----> Vulnerability

The data model gives OpenKAT context.

Knowing that a vulnerability exists in isolation is less useful than knowing which software is affected, which service is running that software, and which system exposes that service.

The model also allows information from different sources to describe the same environment.

Analysis with Bits
------------------

Once information has been collected and connected, OpenKAT can analyze it.

Bits are rules that analyze information in the OpenKAT data model. They can look for conditions that indicate a security risk or another situation that requires attention.

For example, a Bit might identify:

- software with a known vulnerability;
- an insecure configuration;
- an unexpected open port; or
- a system that does not meet a particular security requirement.

The result of an analysis is a finding.

Findings provide a way to turn collected technical information into information that is useful for security monitoring and decision-making.

Continuous discovery
--------------------

OpenKAT does not have to stop after the first scan.

When new information is discovered, it can make additional information discoverable.

For example:

.. code-block:: text

      Hostname
        |
        v
      New IP address discovered
        |
        v
      Scan the IP address
        |
        v
      New service discovered
        |
        v
      Identify software
        |
        v
      Check for vulnerabilities

This allows OpenKAT to gradually build a more complete picture of an environment.

OpenKAT can also schedule scans to refresh information that may become outdated. This is what makes continuous monitoring possible.

Observations and history
------------------------

OpenKAT keeps the observations from which its objects are derived. This provides traceability: it is possible to understand where information came from and when it was collected.

Keeping observations separate from the objects derived from them also means that OpenKAT can update its view of an environment without losing the original information that was collected.

This is useful when investigating changes or validating findings.

Controlling scans
-----------------

OpenKAT can perform different types of actions, from relatively passive information gathering to more active scanning.

To control this, OpenKAT uses clearance levels, also known as indemnities. A clearance determines which actions OpenKAT is allowed to perform for a particular object.

This allows an organization to decide how far OpenKAT may go when investigating its systems.

For example, an organization may allow passive discovery for one environment while permitting more active scanning for another.

See :doc:../user-manual/scan-levels-clearance-indemnities for more information.

Scheduling with Mula
--------------------

OpenKAT needs to decide when information should be collected or refreshed.

The Scheduler (Mula) component is responsible for scheduling tasks. It determines which work needs to be performed and when it should be run.

This allows OpenKAT to continuously refresh information instead of relying entirely on manually started scans.

Putting it all together
-----------------------

The main components work together roughly as follows:

.. code-block:: text

              +----------------------+
              |   Information        |
              |   sources & tools    |
              +----------+-----------+
                         |
                         v
                   +-----------+
                   |  Boefjes  |
                   |  Collect  |
                   +-----+-----+
                         |
                         v
                   +-----------+
                   | Whiskers  |
                   | Normalize |
                   +-----+-----+
                         |
                         v
                +------------------+
                |   OpenKAT data   |
                |      model       |
                |      (OOIs)      |
                +--------+---------+
                         |
              +----------+----------+
              |                     |
              v                     v
        +-----------+         +-----------+
        |   Bits    |         |  Further  |
        |  Analyze  |         | discovery |
        +-----+-----+         +-----+-----+
              |                     |
              v                     |
         +---------+                 |
         | Findings|                 |
         +----+----+                 |
              |                      |
              v                      |
         +---------+                 |
         | Reports |                 |
         +---------+                 |
                                     |
                <--------------------+


In practice, OpenKAT contains more components and interactions than this simplified diagram shows. The purpose of the diagram is to illustrate the main flow rather than every internal dependency.

Why is OpenKAT built this way?
------------------------------

The modular design gives OpenKAT several advantages.

Different tools can be combined.
********************************

A specialized security tool can focus on collecting one type of information without having to implement the rest of OpenKAT.

Information can be connected.
*****************************

Results from different tools can describe the same objects and relationships in the environment.

Discovery can be recursive.
***************************

Information found by one tool can provide the input for another tool.

Analysis can be separated from collection.
******************************************

New analysis rules can be created without changing the tools that collect information.

The system can be extended.
***************************

Organizations can add new collectors, analysis rules and integrations for their own environments and use cases.

Where to learn more
-------------------

This page provides a conceptual overview of how the main parts of OpenKAT work together.

For more detail about the architecture and individual components, see the :doc:../developer-documentation/index.

For information about using OpenKAT, see the :doc:../user-manual/index.

For information about installing and deploying OpenKAT, see the :doc:../installation-and-deployment/index.
