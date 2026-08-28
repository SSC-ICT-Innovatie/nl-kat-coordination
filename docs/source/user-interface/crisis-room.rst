===========
Crisis Room
===========

In OpenKAT we differentiate two Crisis Rooms:

- **Single Organization Crisis Room:** a Crisis Room for each organization separately
- **General Crisis Room:** one general Crisis Room for all the organizations


Single Organization Crisis Room
===============================

This page shows a Crisis Room for each organization separately.
Here, a user can create it's own dashboards.

Findings Dashboard
------------------
There is always one default dashboard, the 'Findings Dashboard'.*
This section shows all the findings that have been identified for the selected organization.
These findings are shown in a table, grouped by finding types.

*\*Note: if you don't see the Findings Dashboard, please read the section 'Automatically Create Dashboards For All Organizations'.*

Custom Dashboards
-----------------
By clicking on the 'Add Dashboard' button, a new dashboard will be created.
Each dashboard can contain a maximum of 16 dashboard items.

There are three types of dashboard items:

- **Object list:** a copy of the object list, with applied filters
- **Findings list:** a copy of the findings list, with applied filters
- **Report section:** a copy of a specific part of a report

Currently, only the object list and findings list are implemented. The report section will follow soon.

The dashboard items can be moved up/downwards and can be deleted.

Adding A New Dashboard Item
---------------------------
To add a new dashboard item to a dashboard:

- Go to the Objects or Findings page
- Filter the table as you prefer (the same filters will be applied to the table in the dashboard item)
- Click on the 'Add to dashboard' button, this opens a modal
- Choose the settings as you prefer
- Click on the 'Add to dashboard' button

The following settings can be set:

- **Dashboard:** Select the dashboard to which you want to add the dashboard item.
- **Name:** Give the dashboard item a name.
- **List sorting by:** This is how the table in the dashboard item will be sorted.
- **Number of rows in list:** Choose how many objects/findings you wish to show in the dashboard item.
- **Dashboard item size:** A dashboard item can be full or half width. Two half width items will be displayed next to each other.
- **Show table columns:** Select at least one column you want to show in the dashboard item.

Permissions
-----------
There are several permissions for the crisis room.
All users have the permission to:

- View dashboards and dashboard items
- Change the position of dashboard items

Additionally, admins and redteamers have permission to:

- Create new dashboards
- Add new items to a dashboard
- Change dashboards
- Change dashboard items
- Delete dashboards
- Delete dashboard items


General Crisis Room
===================

This page shows the Crisis Room for all organizations.*
Currently, this Crisis Room only shows the Findings, but in the future it will also show dashboards,
which can be customized by the user.

*\*Note: if you don't see a general Crisis Room, please read the section 'Automatically Create Dashboards For All Organizations'.*

Findings
--------
This section shows all the findings that have been identified for all organizations.
These findings are shown in a table, grouped by organization and finding types.

Every organization has one default report recipe. This recipe is used to create an Aggregate Findings Report.
The output of this report, for each organization, is shown in this section.

The default settings for this report recipe are:

- report_name_format = ``Crisis Room Aggregate Report``
- ooi_types =  ``["IPAddressV6", "Hostname", "IPAddressV4", "URL"]``
- scan_level = ``[1, 2, 3, 4]``
- scan_type = ``["declared"]``
- report_types = ``["systems-report", "findings-report"]``
- cron_expression = ``0 * * * *`` (every hour)

It is possible to update the report recipe*. To do this:

- Go to "Reports"- Click on the tab "Scheduled"
- Look for the "Crisis Room Aggregate Report"
- Open the row
- Click on "Edit report recipe"

*\*Note: if you want to update the report recipe, you have to do this for every organization.*


Automatically Create Dashboards For All Organizations
=====================================================

OpenKAT automatically creates the default report recipe for you, as can be read in the previous section.
If you already have an OpenKAT installation, with existing organizations, you have to do this manually.
Please follow the following steps. You only have to do this once and all your organizations will be updated.

Steps to Create a Findings Dashboard in Development:
----------------------------------------------------

1. **Install OpenKAT or Add a New Organization:**
   Ensure that you have OpenKAT installed or a new organization has been added to your setup.

2. **Navigate to Your OpenKAT Installation Directory:**
   Open a terminal and change to the OpenKAT installation folder:

   .. code-block:: bash

      cd nl-kat-coordination

3. **Go to the 'rocky' Folder:**
   Within the OpenKAT directory, enter the ``rocky`` folder:

   .. code-block:: bash

      cd rocky

4. **Run the Dashboard Creation Command:**
   Execute the following command to create the findings dashboard:

   .. code-block:: bash

      make dashboards

Steps to Create a Findings Dashboard in Production:
---------------------------------------------------
1. **Run Django Migrations:**
   Run Django migrations for crisis_room app:

   .. code-block:: bash

      python manage.py makemigrations
      python manage.py migrate

2. **Re-run Django migrations:**
   If something happens and later you still want to run the migration script do:

   .. code-block:: bash

      python manage.py dashboards

What Happens After Running the Command or migrations:
-----------------------------------------------------

- The system will automatically search for all installed organizations.
- A **recipe** for the findings dashboard will be generated.
- A **scheduled task** will be created to generate findings reports every hour.
- Findings will be **added to the organization’s crisis room** for easy access and monitoring.
