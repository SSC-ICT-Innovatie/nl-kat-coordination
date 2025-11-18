================
What is OpenKAT?
================

Introduction
============

OpenKAT is a monitoring tool and vulnerability scanner designed to automatically and continuously monitor, record, and analyze the status of information systems. It scans networks, analyzes vulnerabilities, and generates clear, accessible reports. By integrating the most commonly used network tools and scanning software into a modular framework, OpenKAT accesses external databases and combines the information from all these sources into clear reports.


Why was OpenKAT created?
========================

OpenKAT was created by the Dutch Ministry of Health during the COVID-19 pandemic. New systems and functions were developed at high speed and monitoring was needed. OpenKAT made it possible to automatically monitor multiple organizations at the same time, so vulnerabilities could be found quickly.


Why is OpenKAT useful?
======================

OpenKAT is useful if you wish to know if there are vulnerabilities and configuration mistakes hiding somewhere. Most security incidents are caused by known vulnerabilities and small errors. OpenKAT finds them before they are found by bad actors.


Who is OpenKAT for?
===================

OpenKAT is built to monitor a larger number of systems, such as the IT systems during the pandemic. It is both for organizations that want to monitor their own systems and organizations which are responsible for monitoring other organizations. For example, Z-CERT, which is responsible for monitoring all healthcare organizations as a CSIRT, or the Dutch Ministry of Health, which monitored all the test providers that wanted to connect to CoronaCheck.

The nicest playground for OpenKAT is a situation where many systems are active. In the user group around OpenKAT we see larger organizations from the non-profit sector, their service providers, hosting providers, auditors and others involved in information security.


Which problem does OpenKAT solve?
=================================
OpenKAT was created as a monitoring tool with automation, flexibility and traceability in mind. Being a modular framework based on a datamodel, it has plugins for datacollection, automatic scanning, businessrules for analysis, external timestamps on all original data and practical reports.


Framework
---------
The open structure allows you to modify, tweak and add tools for scanning, storage, analysis and reports. With such flexibility and separation of tasks, the bits almost fall out. It allows for easy adaptation to new developments.


Plugins for scanning
--------------------
Plugins do the scanning, ranging from a small script to external tools with a wide range of inputs. New threat around the corner? Build your own plugin to catch it, and as all data is stored you might be able to find vulnerable systems right away.


External timestamps
-------------------
All output from the scans is stored, with its metadata, hashed and timestamped by an external server. This allows you to 'prove' which information was collected, how and when.


Datamodel
---------
To combine information from several sources OpenKAT uses an extendable datamodel with objects. An IP address is such an object, and can be found through different tools and through logical relations in the datamodel.


Automatic scanning
------------------
OpenKAT will scan for new information, using the logic in the datamodel. The results of the scans spark new actions, just as time passing starts new scans to refresh and check the state of the systems in the OpenKAT database.


Indemnity per user and organisation
-----------------------------------
The intensity of a scan can be set in the system by granting it permission for a certain level of intrusion. OpenKAT can be set to a level where it might bring down a system so it needs an “OK” from the user for such steps.


Findings and reports
--------------------
Results of the analysis are available for easy viewing in the frontend, per PDF or through the API. The findings can be collected into different kinds of reports. These reports can be scheduled, so they will be generated automatically for you.


Security concept
================

The premise behind OpenKAT is that most security incidents are caused by known vulnerabilities and configuration errors. Making mistakes is human, so they cannot be completely prevented. Therefore, the goal is to find known vulnerabilities and configuration errors and fix them as quickly as possible. OpenKAT provides the tools for this. The Ministry of Health in the Netherlands made it publicly available under the EU PL 1.2 licence, to be applied as widely as possible.


Responsible disclosure
======================

OpenKAT scans for vulnerabilities. If you find any, it is important that you deal with them properly. If you come across a vulnerability in a central government system you can report it to the `NCSC <https://www.ncsc.nl/contact/kwetsbaarheid-melden>`_.

Many organizations have their contact information in ``security.txt`` in the root of their domain, so you can reach the right people directly. Not every organization handles it equally professionally, but that's no reason not to want to use that standard yourself.

If you find any vulnerabilities in the software of OpenKAT itself you can report them by e-mail to: security @ irealisatie.nl (remove the spaces).


Where do I start with OpenKAT?
==============================

Start by reading the :doc:`/user-manual/index`, which explains how OpenKAT works. After that, if you want to read more about how the system works on a technical level and what the main principles are, check the :doc:`/developer-documentation/index`.

The documentation gives an impression, but trying OpenKAT yourself is the best way to find out how it works. In :doc:`/installation-and-deployment/index`, you can find all the information about installing OpenKAT on your system.

The easiest way to get to know the system is a local installation. If you don't have a debian or ubuntu machine (yet), try the Gitpod test environment. :doc:`/installation-and-deployment/install` has a comprehensive roadmap for creating a local installation. In addition to the documentation, read `the README from the general repository <https://github.com/minvws/nl-kat-coordination>`_.


Where is the software located?
==============================

OpenKAT consists of separate modules that each perform a specific task. All modules are located in the `NL-KAT-Coordination <https://github.com/minvws/nl-kat-coordination>`_ repository. The :doc:`../developer-documentation/basic-principles/modules` section of the documentation goes into detail on each of these modules.


What are the plans for the future?
==================================

OpenKAT was created during the pandemic. Publishing the source code is one way to give the software built during this period a longer life. With OpenKAT, the Ministry of Health is contributing to the `National Cybersecurity Strategy <https://www.rijksoverheid.nl/actueel/nieuws/2022/10/10/kabinet-presenteert-nieuwe-cybersecuritystrategie>`_ (Dutch) and supports the continued development of the system.

Since the source code was published, 'OpenKAT days' have been organized regularly, the community around OpenKAT has grown, and developers from various other organizations are working on modules for the system. It is the first government project to be developed in this way. If you also want to help, contact the team at meedoen@openkat.nl.

The long-term goal is for OpenKAT to play a permanent role in information security in healthcare and in the Netherlands as a whole. The system itself provides a good basis for this and its modular structure makes it easily adaptable to a specific context. Thanks to the EU PL 1.2 license, such contributions will be made available to all users as much as possible.
