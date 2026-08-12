=========================
How do I install OpenKAT?
=========================

OpenKAT can be installed in a number of ways. You can use OpenKAT in a way that suits your situation. For developers and for introductory purposes, there is a local installation. For production application there are debian packages that are automatically built from each release or pre-built docker containers. Also there is community work on kubernetes and nomad scripts. At VWS, OpenKAT is installed based on ansible script. Use the hardening guide for a production install.

Production environments
=======================

Pre-built Docker images
***********************

The pre-built docker images can be used for production installations of OpenKAT and can be found on the Github Container Registry. The deployment manual based on the pre-built docker images is included in this manual. A kubernetes script is being worked on for automatic deploy.

Debian packages
***************

The Debian packages can be used for production installations of OpenKAT and are available as artifacts from the Github actions in the repository of each module. How to install them is explained in the manual. A repository to enable ``apt install kat`` is under construction. The packages cannot easily be converted to RPM's, for this we do not have a solution yet.

Alternative installs
====================
The following alternative installs are possible for OpenKAT. These are community contributions and are thus not maintained by OpenKAT.

Kubernetes
**********
The Kubernetes files can be found at `https://gitlab.com/digilab.overheid.nl/platform/helm-charts/openkat/ <https://gitlab.com/digilab.overheid.nl/platform/helm-charts/openkat/>`_.

Ansible
*******
The Ansible files can be found at `https://github.com/sigio/openkat-ansible <https://github.com/sigio/openkat-ansible>`_.


Development environment
=======================

make kat
********

The 'developer option' or local install of OpenKAT builds the system from the source using ``make kat``. The manual for this install explains how to set up your computer for an install of OpenKAT.

Minimum requirements
====================

OpenKAT can run from a single computer or VM, but this limits the functionality in the long run. The starting point for a development setup would include about 25 GB of diskspace, 4GB of RAM and 2 cores. Diskspace is mostly used by the databases and some logging. More of everything is more fun.

Example infrastructure
======================

A larger installation of KAT can scale both horizontally and vertically. The setup depends on your own preferences. We do not have an estimate for your hardware planning, but most work is done by Mula and Octopoes.

An example is shown in the diagram below. OpenKAT runs behind a proxy with firewalls, with Rocky accessible as the front end. From rocky, a second proxy connects to OpenKAT's components. Most components can be duplicated to distribute load and ensure availability. The arrows in the drawing indicate the direction in which the connections are initiated.

.. image:: img/infraopenkat.png
  :alt: Infra example of OpenKAT

At the backend, a management interface can be added, adapted to the situation where OpenKAT is used. Each module has a healthpoint for monitoring.

Backups are particularly relevant for the raw data in Bytes and the userdata, possibly for speed the objects in Octopoes. Based on Bytes and the userdata, the system can in principle be redeployed and restored.
