=======
Modules
=======

OpenKAT consists of individual modules, each of which performs a subtask of the system. The modules are specific to OpenKAT. Rocky is the frontend, Mula is the scheduler, Bytes the storage of raw data, Octopoes contains the data model and Boefjes and Whiskers and are separate components stored in the KATalogus. OpenKAT uses Manon for the design in order to easily comply with accessibility and style requirements.

The overarching concept of OpenKAT is explained in the section :ref:`basics-of-openkat`. The explanation centers around the image below. All modules of OpenKAT can be found there, except for our web interface and styling modules Rocky and Manon.

.. image:: https://docs.openkat.nl/_images/stappenopenkat.png

The source code and technical documentation is included for each module in its own github repository. This document refers to these repos and their documentation. If you have any questions, please contact the team, see 'Contact' in the readme of the NL-KAT-Coordination repo.

Rocky - frontend
================

Rocky is the front end for OpenKAT and based on a Django framework. Through Rocky, OpenKAT can be accessed. It provides a user interface for all information present in the system. It is also possible to access OpenKAT only through the APIs.

`Rocky <https://github.com/SSC-ICT-Innovatie/nl-kat-coordination/tree/main/rocky>`_ is the folder containing Rocky's source code and documentation.

Mula - scheduler
================

Mula is the scheduler, which controls OpenKAT. Mula has extensive technical documentation and design schematics.

`Mula <https://github.com/SSC-ICT-Innovatie/nl-kat-coordination/tree/main/mula>`_ is the folder containing Mula's source code and documentation.

Octopoes - datamodel
====================

Octopoes contains the data model with object-types and the XTDB with all objects. The documentation accompanying Octopoes covers the technical side of the logic behind OpenKAT and includes extensive information for people who want to work with the data model themselves.

`Octopoes <https://github.com/SSC-ICT-Innovatie/nl-kat-coordination/tree/main/octopoes>`_ is the folder containing the source code and documentation of Octopoes.

Bytes - raw data storage
========================

Bytes is a relatively simple datastore for the raw data provided by OpenKAT. In addition to storage, Bytes also handles assurance by having a timestamp created from the stored data.

`Bytes <https://github.com/SSC-ICT-Innovatie/nl-kat-coordination/tree/main/bytes>`_ is the repository containing Bytes' source code and documentation.

Boefjes and whiskers - scanners and normalizers
===============================================

The KATalog contains all boefjes and whiskers. The KATalog is easy to add new boefjes and normalizers. The general documentation contains some pointers for writing boefjes. The team is happy to help you if you want to get started with these. The readme of `NL-KAT-Coordination repo <https://github.com/SSC-ICT-Innovatie/nl-kat-coordination>`_. contains all the ways to contact the team.

`Boefjes <https://github.com/SSC-ICT-Innovatie/nl-kat-coordination/tree/main/boefjes>`_ is the folder containing the source code and documentation of Boefjes, Whiskers and Bits.

Manon - styling
===============

Content and form are separated in Rocky. The form is contained in Manon, which as far as OpenKAT is applied in the context of the central government helps to comply with the central government house style. For Web sites outside this context, Manon is also applicable, but with a different style.

`NL-RDO-Manon <https://github.com/minvws/nl-rdo-manon>`_ is the repository containing Manon's source code.
