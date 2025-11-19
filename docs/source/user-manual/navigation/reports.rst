Reports
=======

The Reports page provides access to security reports generated from OpenKAT's scanning results.
Reports present findings, metrics, and insights in a structured PDF format suitable for sharing with stakeholders.

.. image:: img/report.jpg
  :alt: Report

Report Overview
---------------

OpenKAT v2 generates comprehensive PDF reports that summarize:

- Security findings discovered during scanning
- DNS configuration and infrastructure
- Open ports and network services
- IPv6 adoption metrics
- General asset statistics

Reports are useful for:

- Executive summaries of security posture
- Compliance documentation
- Tracking security improvements over time
- Sharing results with external parties

Reports Page
------------

The Reports page displays all generated reports with the following information:

- **Report Name**: The name given to the report during generation
- **Description**: Optional description of the report's purpose
- **Generated At**: Date and time the report was created
- **Organizations**: Which organizations' data is included
- **Actions**: Download PDF or delete report

Generating a Report
-------------------

Click the "Generate Report" button to create a new report.

You'll be prompted to configure:

1. **Report Name**: A descriptive name for identification
2. **Description**: Optional details about the report
3. **Filters** (all optional):

   - **Organizations**: Limit to specific organizations
   - **Finding Types**: Focus on specific security issues
   - **Object Set**: Use a saved object set to define scope

See :doc:`../getting-started/generate-report` for step-by-step instructions.

Report Contents
---------------

Generated reports include the following sections:

Findings Analysis
*****************

The findings section provides a comprehensive view of security issues:

- **Summary Statistics**: Total findings count
- **Findings by Type**: Grouped by finding type with:

  - Finding name and code
  - Severity score (0-10 scale)
  - Number of occurrences
  - Affected assets count and percentage
  - Detailed description
  - Risk assessment
  - Remediation recommendations

- **Top Offenders**: The 10 assets (hostnames and IP addresses) with the most findings

DNS Metrics
***********

DNS information discovered during scanning:

- Total hostnames
- Root domains identified
- Name servers in use

Port Analysis
*************

Network service information:

- Total open ports discovered
- Unique IP addresses with open ports
- Top 20 most common ports
- Protocol distribution (TCP vs UDP)

IPv6 Adoption
*************

IPv6 deployment metrics:

- IPv4 address count
- IPv6 address count
- IPv6 adoption percentage

General Statistics
******************

Overall asset counts:

- Total networks
- Total hostnames
- Total IP addresses
- Organizations included

Filtering Reports
-----------------

Reports can be filtered during generation to focus on specific areas:

Organization Filter
*******************

Limit the report to one or more organizations. Useful for:

- Multi-tenant deployments
- Generating organization-specific reports
- Comparing different business units

Finding Types Filter
********************

Focus the report on specific finding types. Useful for:

- Creating focused reports (e.g., only TLS issues)
- Tracking specific compliance requirements
- Highlighting critical findings

Object Set Filter
*****************

Use a saved object set to define the report scope. Useful for:

- Reporting on specific infrastructure segments
- Creating consistent recurring reports
- Focusing on priority assets

Downloading Reports
-------------------

To download a report as PDF:

1. Click on the report in the Reports list
2. Click the "Download" button
3. The PDF will be saved to your downloads folder

Reports can be:

- Opened in any PDF viewer
- Printed for physical distribution
- Shared via email or document management systems
- Archived for compliance purposes

Report Data Accuracy
--------------------

Reports reflect the current state of data in OpenKAT at the time of generation.

For accurate and complete reports:

**Ensure Adequate Scanning**

- Objects have appropriate clearance levels
- Required plugins have been enabled
- Sufficient time has elapsed for scans to complete
- Check the Tasks page to verify completion

**Use Appropriate Filters**

- Verify organization filters are correct
- Ensure finding type filters aren't too restrictive
- Test object set filters before generating large reports

**Regular Regeneration**

Since OpenKAT continuously scans and updates data:

- Regenerate reports periodically to capture new findings
- Old reports may not reflect current security posture
- Consider deletion of outdated reports to avoid confusion

Managing Reports
----------------

Deleting Reports
****************

To delete a report:

1. Click on the report in the Reports list
2. Click the "Delete" button
3. Confirm the deletion

Deleted reports cannot be recovered. Download important reports before deletion.

Report Storage
**************

Reports are stored as files in the OpenKAT database. Consider:

- Regular cleanup of old reports to save disk space
- Archiving important reports externally
- Setting up automated cleanup policies if needed

Troubleshooting
---------------

Report is Empty
***************

If a generated report contains no data:

- Verify objects have been added to OpenKAT
- Check that objects have clearance levels set (L1 or higher)
- Ensure scans have completed (check Tasks page)
- Verify filters aren't excluding all data

Missing Expected Findings
*************************

If findings you expect are missing:

- Ensure the relevant plugins are enabled
- Verify object clearance levels are sufficient for the plugin scan level
- Check the Tasks page for failed tasks
- Confirm objects are associated with the correct organization

Report Generation Fails
***********************

If report generation fails:

- Check application logs for error messages
- Verify database connectivity
- Ensure sufficient disk space for PDF generation
- Contact your OpenKAT administrator

Next Steps
----------

- :doc:`../getting-started/generate-report` - Step-by-step report generation guide
- :doc:`findings` - Understanding and managing findings
- :doc:`tasks` - Monitoring scan completion
- :doc:`objects` - Managing scanned objects
