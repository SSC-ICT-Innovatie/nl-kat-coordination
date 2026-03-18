.. _scan-levels-clearance-indemnities:

Scan levels, clearance & indemnities
====================================

Plugins (Boefjes) can collect information with varying intensity. OpenKAT has a system of clearance levels to control permission to perform scans and prevent damage to the systems under test.

* Plugins have a scan level
* Objects have clearance
* Users can receive and accept the ability to give clearance to an object and to start a scan

For each object, the 'clearance level' menu indicates how deeply scanning is allowed. Here the user agrees to the risks of the scans and gives permission to store the information gathered on these systems.

The levels used range from level 0 to level 4, from 'do not scan' to 'very intrusive'. Scanning levels are distributed in the data model, either by inheritance or by user statements. The different levels are qualitative in nature. L1 'do not touch' is obvious, but the difference between L2 'normal user' and L3 'detectable scanning' is at the discretion of the developer and administrator. The use of NMAP, for example, falls in between and depends heavily on the arguments the tool brings.

.. list-table:: Scan levels
   :class: table
   :widths: 25 50
   :header-rows: 1

   * - Level
     - Description
   * - L0
     - do nothing: do not touch and don't gather information about this object
   * - L1
     - retrieve information from public sources, but don't touch the object itself
   * - L2
     - touch at normal user level
   * - L3
     - detectable scanning
   * - L4
     - intensive scanning


Inheritance
-----------
Objects are linked to other objects in the data model.
You can choose to declare a clearance level to an object or to let it inherit the clearance level from connected objects.
Underlying objects will then receive the same clearance level, parent objects a lower level.
For example, a hostname has an IP address for which the same clearance level applies, but it also has a DNS server that may be outside the organization's domain and receives a lower level.

More information about the different clearance types for objects can be found here: :doc:`../basic-concepts/objects-and-recursion`.

Indemification by user
----------------------
The user's statement counts as an indemnification for scanning a particular object.
This obtains permission to scan and store the information.
The statement is given at the start of a new scan or specifically for certain objects.

Extended profiles
-----------------

L0: Do not scan
***************
The user can explicitly indicate that certain systems should not be scanned. For example, because he is not the owner of these.

L1: Do not touch
****************
OpenSource and passive data collection. For this profile, objects are viewed through various freely available data and sources via the Internet.
These can be sources that do not have explicit permission (e.g. LinkedIn, DNS, leaked password databases).
The goal here is to detect public information that could be a risk to the client: information that could be misused by an attacker in a targeted attack.

Examples of sources/tools used:

- Shodan (via API)
- HaveIbeenPnwed
- DNS

L2: Touching at the normal user level
*************************************
Targeted scans, limited intrusive. Scan will be dosed and skip known sensitive scans.
The scanned target usually continues to function without problems.

Example of scanning tools useful for this purpose:

- Nmap
- Nikto
- Burp passive scanner

L3: Detectable scan
*******************
This scan will be more intrusive: connect to services to find out versions, try to log in with commonly used (default) login credentials,
automated testing of found vulnerabilities whether they are vulnerable, more intensive guessing of urls and more intensive crawling of web pages.

A greater number of scans will be performed, resulting in a spike in data traffic. The infrastructure may not be designed for this.

Example of useful scanning tools and methods:

- Nessus, Nexpose, Acunetix
- Burp Intruder, active scanner

L4: Intensive scan
******************
The premise of the test profile is to verify whether an attacker can exploit vulnerabilities to give himself
more extensive access to the tested environment. Thus, known exploit code is applied in this level.
