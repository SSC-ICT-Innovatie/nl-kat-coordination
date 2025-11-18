Tasks
=====

All tasks can be found on the Tasks page. A task is created for each job that needs to be performed, such as running a plugin or generating a report. Plugins are executed on objects (such as hostnames, IP addresses, DNS records, etc.) or on files produced by other plugins.

Tasks have a status to show if the task is completed, scheduled, queued, failed, etc.
Each task contains metadata and can produce output files that can be downloaded.
Tasks can also be rescheduled and filtered to find specific tasks.

Task List
---------

The Tasks page displays a table with information about all tasks:

- **Plugin**: Which plugin was executed
- **Input**: The object or file that was scanned
- **Status**: Current state (completed, failed, queued, running)
- **Created**: When the task was created
- **Organization**: Which organization the task belongs to

.. image:: img/tasks-boefjes.png
  :alt: overview of tasks

Task Details
------------

Click on a task to view its details:

- **Task information**: Plugin, input, status, timestamps
- **Output files**: Raw scan data produced by the plugin
- **Created objects**: Objects created by the plugin (if any)
- **Error messages**: If the task failed, the error details

Created Objects
***************

When a plugin processes data, it may create new objects in OpenKAT. For example:

**Example:**
  The DNS plugin scans the hostname `mispo.es` and discovers DNS records.
  The plugin creates objects for each identified DNS record (A, NS, MX, SOA).
  These objects are now available in OpenKAT and can be scanned by other plugins.

.. image:: img/tasks-normalizer-yielded-objects.png
  :alt: objects created by plugins

Filtering Tasks
---------------

Use the filter form to narrow down the task list:

- Filter by plugin
- Filter by status (completed, failed, etc.)
- Filter by organization
- Filter by date range
- Filter by schedule (if the task was created by a schedule)

Task Status
-----------

Tasks can have the following statuses:

- **Queued**: Task is waiting to be executed
- **Running**: Task is currently being processed
- **Completed**: Task finished successfully
- **Failed**: Task encountered an error
- **Cancelled**: Task was manually cancelled

Downloading Task Output
-----------------------

Tasks may produce output files containing raw scan data:

1. Click on a task to view its details
2. Navigate to the "Output files" section
3. Click the download button to save the raw output

These files contain the unprocessed data from the plugin and can be useful for:

- Debugging plugin issues
- Manual analysis of scan results
- Reprocessing with different plugins

Rescheduling Tasks
------------------

If a task failed or you want to rerun it:

1. Click on the task to view details
2. Click the "Reschedule" button
3. The task will be added back to the queue

This creates a new task with the same plugin and input.

Task Errors
-----------

When a task fails, the error message is displayed in the task details.
Common causes of task failures:

- Network timeouts or connection errors
- Invalid input data
- Plugin crashed or exceeded resource limits
- Permission errors

Check the error message and task output for debugging information.

Related Pages
-------------

- :doc:`plugins` - Configure and manage plugins
- :doc:`schedules` - Set up recurring tasks
- :doc:`files` - View output files from tasks
- :doc:`objects` - View objects created by tasks
