Generate a report
=================

OpenKAT can generate PDF reports to summarize findings and provide security insights.
In this section you will learn how to create a report.

Overview
--------

Reports in OpenKAT v2 are generated as PDF documents that include:

- **Findings Summary**: All security findings grouped by type with severity scores
- **DNS Metrics**: Hostnames, root domains, and name servers
- **Port Analysis**: Open ports discovered during scanning
- **IPv6 Adoption**: IPv4 vs IPv6 address distribution
- **General Statistics**: Networks, hostnames, and IP addresses

Reports can be filtered by organization, finding types, or object sets to focus on specific areas of interest.

Generating a Report
-------------------

1. **Navigate to Reports Page**

   Click on "Reports" in the main navigation.

2. **Click Generate Report**

   Click the "Generate Report" button to start creating a new report.

   .. image:: img/generate-report-01.png
     :alt: Reports page with Generate report button

3. **Configure Report**

   Provide the following information:

   - **Report Name**: A descriptive name for your report
   - **Description**: Optional details about the report's purpose
   - **Organizations**: Select which organizations to include (optional filter)
   - **Finding Types**: Select specific finding types to focus on (optional filter)
   - **Object Set**: Select a saved object set to limit scope (optional filter)

   .. image:: img/generate-report-02.png
     :alt: Report configuration page

4. **Generate**

   Click "Generate Report" to create the PDF.

   The report will be generated in the background and appear in the Reports list when complete.

Understanding Report Contents
------------------------------

Generated reports include the following sections:

Findings Summary
****************

- Total number of findings discovered
- Findings grouped by type with severity scores
- Affected assets count and percentage
- Top offenders (hostnames and IP addresses with most findings)
- Detailed descriptions and recommendations for each finding type

DNS Information
***************

- Total hostnames discovered
- Root domains count
- Name servers identified

Port Information
****************

- Total open ports discovered
- Number of unique IP addresses with open ports
- Top 20 most common ports
- Distribution by protocol (TCP/UDP)

IPv6 Adoption
*************

- IPv4 address count
- IPv6 address count
- Percentage of IPv6 adoption

General Metrics
***************

- Total networks
- Total hostnames
- Total IP addresses
- Organizations included in the report

Important Notes
---------------

**Data Collection**

Reports are generated from data that has already been collected by OpenKAT. For accurate reports:

- Ensure objects have appropriate clearance levels set
- Allow sufficient time for plugins to complete scanning
- Check the Tasks page to verify scans have finished
- Higher clearance levels enable more comprehensive scanning

**Filters**

All filters are optional:

- **No filters**: Report includes all data across all organizations
- **Organization filter**: Limit report to specific organizations
- **Finding types filter**: Focus only on specific security issues
- **Object set filter**: Use a saved object set to define scope

**Report Storage**

Generated reports are stored as files and can be:

- Downloaded as PDF
- Viewed in the browser
- Deleted when no longer needed

Viewing Generated Reports
--------------------------

After generation, reports appear in the Reports list on the Reports page.

Click on a report to:

- View report details (name, description, generation date)
- Download the PDF file
- Delete the report if no longer needed

.. image:: img/generate-report-05.png
  :alt: Generated reports list

Troubleshooting
---------------

**Report is empty or has no findings**

- Verify objects have been added and scanned
- Check that clearance levels are set (L1 or higher)
- Ensure plugins have completed (check Tasks page)
- Confirm filters aren't excluding all data

**Report generation fails**

- Check system logs for errors
- Verify database is accessible
- Ensure sufficient disk space for PDF generation
- Contact your administrator if issues persist

More Information
----------------

To read more about the Reports page and report management, see :doc:`../navigation/reports`.
