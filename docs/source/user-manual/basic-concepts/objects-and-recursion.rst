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
- Inherited: objects identified through scanning and object discovery by plugins. This means there is a relation to other object(s).
- Empty: objects that do not have a relation to other objects.

The objects below show different clearance types for various objects. The hostname `mispo.es` was manually added and thus is `declared`.
The DNS zone is `inherited` based on the DNS zone plugin.

.. image:: img/objects-clearance-types.jpg
  :alt: different object clearance types

Scan level inheritance and recalculation
-----------------------------------------

When you set a scan level for an object, OpenKAT can automatically propagate that scan level to related objects. This inheritance works through specific DNS relationships.

How inheritance works
*********************

OpenKAT automatically recalculates scan levels when:

- You change an object's scan level from "Declared" to "Inherited"
- You change a declared scan level value
- Related objects are created or modified

The scan level of an inherited object is determined by the highest scan level among its related declared objects.

Inheritance paths
*****************

Scan level inheritance currently works through these specific paths:

**1. IP Address ↔ Hostname (via DNS A Records)**

When an IP address and hostname are connected through a DNS A record:

- If you set a scan level on an IP address, the hostname inherits it
- If you set a scan level on a hostname, the IP address inherits it
- The inheritance flows in both directions

Example:
  You add hostname ``example.com`` with scan level 2. When a DNS plugin discovers that ``example.com`` resolves to IP address ``192.0.2.1`` (creating a DNS A record), the IP address ``192.0.2.1`` automatically inherits scan level 2.

**2. Hostname ↔ Hostname (via CNAME Records)**

When two hostnames are connected through a DNS CNAME record:

- The alias hostname inherits the scan level from the target hostname
- The target hostname inherits the scan level from the alias hostname
- The inheritance flows in both directions

Example:
  You add hostname ``www.example.com`` with scan level 3. When a DNS plugin discovers that ``www.example.com`` is a CNAME pointing to ``example.com``, the target hostname ``example.com`` inherits scan level 3.

**3. Network → IP Addresses**

When IP addresses belong to a network:

- IP addresses can inherit their scan level from the network they belong to
- This inheritance flows from network to IP addresses only (one direction)

Example:
  You add network ``192.0.2.0/24`` with scan level 1. All IP addresses within this network range can inherit scan level 1.

Limitations
***********

The current scan level inheritance is intentionally limited to these specific DNS-related paths. This means:

- Other object types (ports, certificates, URLs, etc.) do not automatically inherit scan levels
- Complex relationships beyond DNS records do not trigger automatic inheritance
- You must manually set scan levels for objects outside these inheritance paths

Declared vs Inherited
*********************

When viewing an object's scan level, you'll see whether it is:

- **Declared**: You manually set this scan level
- **Inherited**: The scan level was automatically calculated from related objects
- **Empty (None)**: No scan level has been set yet

If you change an object from "Declared" to "Inherited", OpenKAT will:

1. Recalculate the scan level based on related objects
2. Recalculate scan levels for objects that were inheriting from this object
3. Update all affected objects in the system

This recalculation may take a moment to complete for large object graphs.

Best practices
**************

For efficient scan level management:

- Set scan levels on "root" objects (networks, primary domains)
- Let related objects (IPs, subdomains) inherit automatically
- Use "Declared" scan levels sparingly for exceptions
- Monitor the clearance level tab to verify inheritance is working correctly
