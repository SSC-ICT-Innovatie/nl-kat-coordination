Business rules
==============

The Business rules page allows you to create custom SQL queries that generate findings based on your organization's specific security policies and compliance requirements.

Overview
--------

Business rules are custom security checks defined as SQL queries against the XTDB object database. They allow you to:

- Create organization-specific security findings
- Implement custom compliance checks
- Codify internal security policies
- Generate findings based on complex object relationships

Unlike plugins that scan external targets, business rules analyze objects already stored in OpenKAT's database.

Business Rule List
------------------

The Business rules page displays a table with:

- **Name**: The name of the business rule
- **Description**: What the rule checks for
- **Object type**: Which type of object this rule analyzes
- **Finding type**: The finding type code that will be generated
- **Enabled**: Whether the rule is currently active

Creating a Business Rule
-------------------------

To create a new business rule:

1. Click the "Add business rule" button
2. Fill in the required information:

   - **Name**: A descriptive name for the rule
   - **Description**: Explanation of what the rule checks
   - **Object type**: Which object type to query (Hostname, IPAddress, etc.)
   - **Finding type code**: Unique code for the generated finding
   - **SQL query**: The query that identifies violations

3. Test the query to ensure it works correctly
4. Enable the rule

SQL Query Structure
*******************

Business rule queries must follow this structure:

.. code-block:: sql

   SELECT _id
   FROM public.objects_hostname
   WHERE condition_that_indicates_violation

**Important**:

- The query must select the ``_id`` column
- Query the appropriate table for your object type (``objects_hostname``, ``objects_ipaddress``, etc.)
- The query should return object IDs that violate the rule
- A finding will be created for each returned object ID

Example Business Rules
----------------------

Missing DNSSEC
**************

Check for hostnames without DNSSEC enabled:

.. code-block:: sql

   SELECT h._id
   FROM public.objects_hostname h
   WHERE h.root = true
     AND NOT EXISTS (
       SELECT 1
       FROM public.objects_dnssecrecord d
       WHERE d.hostname_id = h._id
     )

This rule finds root domains that don't have DNSSEC configured.

Weak TLS Ciphers
****************

Identify services using weak TLS ciphers:

.. code-block:: sql

   SELECT s._id
   FROM public.objects_ipservice s
   JOIN public.objects_tlscipher c ON c.service_id = s._id
   WHERE c.cipher_suite LIKE '%RC4%'
      OR c.cipher_suite LIKE '%DES%'

This rule finds IP services offering weak or deprecated cipher suites.

Exposed Management Ports
*************************

Find IP addresses with management ports open:

.. code-block:: sql

   SELECT DISTINCT a._id
   FROM public.objects_ipaddress a
   JOIN public.objects_ipport p ON p.address_id = a._id
   WHERE p.port IN (22, 23, 3389, 5900)
     AND p.state = 'open'

This rule identifies IP addresses with common management ports exposed.

Managing Business Rules
------------------------

Enabling/Disabling Rules
*************************

To temporarily disable a business rule without deleting it:

1. Click the "Disable" button next to the rule
2. The rule will stop generating findings
3. Click "Enable" to resume checking

Editing Rules
*************

To modify an existing business rule:

1. Click on the rule name to view details
2. Click the "Edit" button
3. Modify the query, description, or other settings
4. Save the changes

**Note**: Editing a rule does not retroactively update or remove existing findings. Consider disabling the old rule and creating a new one if the logic changes significantly.

Deleting Rules
**************

To permanently remove a business rule:

1. Navigate to the rule detail page
2. Click the "Delete" button
3. Confirm the deletion

**Warning**: Deleted rules cannot be recovered, but their findings remain in the system until manually removed.

Viewing Generated Findings
***************************

To see findings created by a business rule:

1. Go to the Findings page
2. Filter by the finding type code used in your business rule
3. Review the objects that triggered the rule

See :doc:`findings` for more information about managing findings.

Database Schema
---------------

Business rules query the XTDB database. Common tables include:

Object Tables
*************

- ``public.objects_hostname`` - Hostnames
- ``public.objects_ipaddress`` - IP addresses
- ``public.objects_ipport`` - Open ports
- ``public.objects_network`` - Networks
- ``public.objects_ipservice`` - Network services
- ``public.objects_finding`` - Existing findings

DNS Tables
**********

- ``public.objects_dnsarecord`` - DNS A records
- ``public.objects_dnscnamerecord`` - DNS CNAME records
- ``public.objects_dnssecrecord`` - DNSSEC records
- ``public.objects_dnsnsrecord`` - DNS NS records

See the developer documentation for a complete schema reference.

Best Practices
--------------

**Start simple**: Test your SQL query in a database client before creating the business rule.

**Use meaningful finding codes**: Choose descriptive finding type codes that clearly indicate the issue (e.g., ``NO_DNSSEC``, ``WEAK_TLS_CIPHER``).

**Document your rules**: Use clear names and descriptions so other team members understand what each rule checks.

**Test before enabling**: Create the rule in disabled state, verify it generates expected findings, then enable it.

**Monitor performance**: Complex queries on large datasets may slow down the system. Optimize queries for performance.

**Version your rules**: Document changes to business rules over time, especially if they affect compliance reporting.

Use Cases
---------

Compliance Checking
*******************

Implement compliance requirements specific to your industry:

- Check for required security headers
- Verify certificate validity periods
- Ensure encryption standards are met

Policy Enforcement
******************

Codify internal security policies:

- Restrict services to specific ports
- Require specific configurations
- Enforce naming conventions

Custom Risk Scoring
*******************

Identify high-risk configurations:

- Services with known vulnerable versions
- Unusual port combinations
- Deprecated protocols in use

Related Pages
-------------

- :doc:`findings` - View and manage findings generated by business rules
- :doc:`../developer-documentation/business-rules` - Technical documentation for writing business rules
- :doc:`objects` - Understanding the object types available for querying
