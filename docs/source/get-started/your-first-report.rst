Your first report
=================

Your first report is the final step of the OpenKAT onboarding process.

During onboarding, you add an object, choose how OpenKAT may scan it, and enable plugins to collect information. OpenKAT then uses the collected information to create your first report.

For the onboarding flow, OpenKAT creates a DNS report. This gives you a simple first look at information OpenKAT has discovered about your object.

Before you generate your report
-------------------------------

Your object needs to have been scanned before the report can contain useful information.

During onboarding, OpenKAT takes care of the initial setup:

You add an object, such as a hostname or URL.
You choose a clearance level for the object.
You enable the plugins used to collect information.
OpenKAT starts the scan.
The collected information is used to generate your report.

The plugins need some time to complete their work. You do not have to wait on the same page while this happens.

What is a DNS report?
---------------------

A DNS report provides an overview of the DNS information OpenKAT has discovered for your hostname.

Depending on the information available, this can include things such as DNS records and the IP addresses associated with the hostname.

The DNS report is a simple example of how OpenKAT turns the information it collects into something that is easier to understand and use.

Generate your first report
--------------------------

At the end of the onboarding flow, OpenKAT starts generating your **DNS report**.

The scan runs in the background. The plugins, also called Boefjes, collect information about your object and OpenKAT processes the results.

.. note::

    **The report is not available immediately. The plugins need time to collect and process the information.**

While you wait, you can explore the rest of OpenKAT. You can return to the report later through **Report History**.

View your report
----------------

After the plugins have finished, your DNS report will be available in **Report History**.

Open **Report History** and select your newly generated report.

Congratulations — you have created your first OpenKAT report!

What does the report tell me?
-----------------------------

Your report is a summary of information that OpenKAT has collected.

It is important to remember that a report does not necessarily contain everything OpenKAT knows about an object. What appears in a report depends on:

- the type of report;
- the object you selected;
- the plugins that were enabled;
- the clearance level of the object; and
- the information those plugins were able to collect.

As you use OpenKAT, you can create different types of reports for different purposes.

What happens after my first report?
-----------------------------------

Your first report is only the beginning.

OpenKAT can continue scanning your objects and updating the information it has collected. New information can lead to new objects and findings.

Once you are comfortable with the onboarding flow, you can:

add more objects to monitor;
enable additional plugins;
review findings;
create different types of reports; and
schedule reports to be generated periodically.

The :doc:`../user-manual/start-scanning` page explains how to add and scan objects outside of the onboarding flow.

To learn more about reports, including the different report types and how to create them, see :doc:`../user-manual/generate-report`.

A note about timing
-------------------

It can take some time before a report contains all the information you expect.

OpenKAT performs scans and data collection in the background. If you generate a report immediately after enabling a plugin, that plugin may not have finished collecting and processing its information yet.

For the most complete results, allow the relevant tasks to finish before generating or reviewing a report.

You can check the progress of running tasks on the **Tasks** page.
