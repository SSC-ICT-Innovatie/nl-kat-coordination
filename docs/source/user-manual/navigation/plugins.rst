Plugins
=======

The Plugins page is where you can see which plugins are available and configure them for your organization.
Plugins are containerized scanners that check your objects for security issues, discover new information, or validate configurations.

Before a plugin can run, the following conditions must be met:

- The plugin is available in the system (defined in ``plugins/plugins/plugins.json``)
- The clearance level of your object (e.g., hostname or IP address) is at least the required scan level of the plugin

Administrators can view all available plugins and their configurations in the web interface.

Plugin Overview
---------------

The Plugins page shows all available plugins with the following information:

- **Name**: The plugin's display name
- **Description**: What the plugin does
- **Scan Level**: Minimum clearance level required to run this plugin
- **Status**: Whether the plugin is available

Each plugin has a details page with information about:

- The scan level required
- Which object types the plugin can scan ("Consumes")
- What kind of data or findings it produces
- Recent tasks that used this plugin
- Objects that match the required clearance level

How Plugins Work
----------------

Plugins run automatically based on your objects' clearance levels:

1. You add an object (like a hostname) and set its clearance level
2. Plugins that match the clearance level are automatically scheduled
3. Plugins run in isolated containers and perform their tasks
4. Some plugins scan objects directly (e.g., DNS lookups, port scans)
5. Some plugins process files from other plugins and create new objects
6. Results appear as new objects and findings in OpenKAT

Example Plugins
***************

**Direct Scanning Plugins:**

- **DNS**: Discovers DNS records for hostnames
- **Nmap**: Scans IP addresses for open ports and services
- **DNSSEC**: Validates DNSSEC signatures

**File Processing Plugins:**

- **Parse Nmap**: Processes Nmap XML output and creates port and service objects
- **Parse DNS**: Processes DNS scan output and creates DNS record objects

Both types of plugins are executed as tasks, and you can view their progress and results on the Tasks page.

For more technical details about plugins, see :doc:`../../developer-documentation/plugins`.
