Objects and recursion
=====================

The information collected by OpenKAT is stored as objects.
Objects can be anything, like DNS records, hostnames, URLs, IP addresses, software, software versions, ports, etc.


Properties
----------
Objects can be viewed via the 'Objects' page in OpenKAT's main menu. Here, all objects including their type and scan level are shown.
Objects can be added, scanned, filtered and exported.

New objects can be created using the 'Add' option. This can be done individually or per CSV.
The specification of the CSV is included on the upload page.


Recursion
---------
These objects are part of a data model. The data model is the logical connection between all objects and provides the basis for analysis and reporting.
OpenKAT includes a data model suitable for information security, but it can be expanded or adapted for other applications.

Adding an initial object with an appropriate safeguard puts OpenKAT to work. This can be done during onboarding,
but objects can also be added individually or as CSV files. Objects are also referred to as 'Objects of Interest' (OOI).
The object itself contains the actual data: an object type describes the object and its logical relationships with other object types.

**Example:**
  If there is a hostname, OpenKAT also expects an IP address and possible open ports based on the data model.
  Depending on the given clearance level, this is then scanned, which in turn provides more information, which in turn may prompt new scans.
  How far OpenKAT goes with its search depends on the clearance levels.


Object clearance type
---------------------
Each object has a clearance type. The clearance type tells how the object was added to the Objects list. The following clearance types are available:

- Declared: objects that were added by the user.
- Inherited: objects identified through propagation and the parsing of bits and normalizers. This means there is a relation to other object(s).
- Empty: objects that do not have a relation to other objects.

The objects below show different clearance types for various objects. The hostname `mispo.es` was manually added and thus is `declared`.
The DNS zone is `inherited` based on the DNS zone plugin.

.. image:: img/objects-clearance-types.png
  :alt: different object clearance types
