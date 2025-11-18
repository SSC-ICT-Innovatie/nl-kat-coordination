Schedules
=========

The Schedules page allows you to create and manage recurring tasks that run automatically on a schedule. This enables continuous scanning and report generation without manual intervention.

Overview
--------

Schedules can automate two types of tasks:

- **Plugin scans**: Run a specific plugin on a set of objects at regular intervals
- **Report generation**: Automatically generate reports on a recurring basis

Each schedule consists of:

- The plugin or report to run
- An object set defining which objects to scan
- A recurrence pattern (daily, weekly, etc.)
- Enable/disable state

Creating a Schedule
-------------------

To create a new schedule:

1. Click the "Add schedule" button on the Schedules page
2. Select what to schedule:

   - **Plugin**: Choose a scanning plugin to run automatically
   - **Report**: Choose to generate a report automatically

3. Select an object set:

   - Object sets define which objects will be scanned or reported on
   - See :doc:`../basic-concepts/objects-and-recursion` for more information about object sets

4. Configure the recurrence:

   - **Daily**: Run every day at a specific time
   - **Weekly**: Run on specific days of the week
   - **Monthly**: Run on specific days of the month
   - **Custom**: Define a custom recurrence pattern using recurrence rules

5. Save the schedule

The schedule will start running automatically at the configured times.

Schedule List
-------------

The Schedules page displays a table with the following columns:

- **Plugin or Report**: What will be executed
- **Object set**: Which objects will be processed
- **Organization**: Which organization this schedule belongs to
- **Schedule**: The recurrence pattern (e.g., "DAILY at 02:00")
- **State**: Whether the schedule is enabled or disabled
- **Actions**: Options to view tasks, rerun, edit, or delete

Filtering Schedules
*******************

Use the filter form to narrow down the list:

- Filter by organization
- Filter by enabled/disabled state
- Filter by plugin or report type

Managing Schedules
------------------

Enabling/Disabling
******************

To temporarily stop a schedule without deleting it:

1. Click the "Disable" button next to the schedule
2. The schedule will stop creating new tasks
3. Click "Enable" to resume automatic execution

This is useful for maintenance periods or when you want to pause scanning temporarily.

Rerunning a Schedule
********************

To manually trigger a schedule immediately:

1. Click the "Open details" button on a schedule row
2. Click the "Rerun now" button
3. The schedule will create tasks immediately, regardless of the recurrence pattern

Editing a Schedule
******************

To modify a schedule:

1. Click the "Open details" button on a schedule row
2. Click the "Edit" button
3. Modify the object set or recurrence pattern
4. Save the changes

Deleting a Schedule
*******************

To permanently remove a schedule:

1. Click the "Open details" button on a schedule row
2. Click the "Delete" button
3. Confirm the deletion

**Note**: Deleting a schedule does not delete the tasks or results it has already created.

Viewing Schedule Tasks
**********************

To see all tasks created by a schedule:

1. Click the "Open details" button on a schedule row
2. Click the "View tasks" button
3. You'll be redirected to the Tasks page filtered by this schedule

This allows you to monitor the execution history and troubleshoot any issues.

Use Cases
---------

Continuous Scanning
*******************

Set up daily schedules to continuously scan your infrastructure:

- DNS plugin on all declared hostnames (daily at 2:00 AM)
- Port scan plugin on all IP addresses (weekly on Sundays)
- SSL certificate plugin on all web services (daily at 3:00 AM)

Regular Reporting
*****************

Automatically generate reports for stakeholders:

- Weekly security report for management (every Monday at 9:00 AM)
- Daily findings summary for security team (every day at 8:00 AM)
- Monthly compliance report (first day of each month)

Scheduled Rescans
*****************

Recheck specific findings or objects:

- Rerun vulnerability scans after patch deployment (monthly)
- Verify security headers after configuration changes (daily)
- Monitor TLS cipher suites for compliance (weekly)

Best Practices
--------------

**Spread out scan times**: Avoid scheduling many heavy scans at the same time to prevent system overload.

**Use appropriate intervals**: Match the schedule frequency to how often the data changes:

- DNS records: Daily is usually sufficient
- Port scans: Weekly for stable infrastructure, daily for dynamic environments
- SSL certificates: Daily to catch upcoming expirations

**Monitor task results**: Regularly check the Tasks page to ensure schedules are completing successfully.

**Disable unused schedules**: Rather than deleting schedules you may need later, disable them to preserve the configuration.

**Use object sets effectively**: Create specific object sets for scheduled scans rather than scanning all objects, to reduce task volume and focus on priority assets.

Related Pages
-------------

- :doc:`tasks` - View and monitor task execution
- :doc:`objects` - Manage object sets for scheduling
- :doc:`plugins` - Configure plugins to schedule
- :doc:`reports` - Configure reports to schedule
