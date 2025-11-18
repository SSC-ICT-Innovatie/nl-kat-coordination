Task System
===========

OpenKAT v2 uses **Celery** with **Redis** as the message broker for asynchronous task execution.

Overview
--------

Tasks are the unit of work in OpenKAT. They represent:

- Plugin execution
- Business rule evaluation
- Report generation
- Scheduled scans

Task Model
----------

Tasks are stored in PostgreSQL:

.. code-block:: python

   class Task(models.Model):
       id = models.UUIDField(primary_key=True, default=uuid.uuid4)
       organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
       type = models.CharField(max_length=32, default="plugin")
       data = models.JSONField(default=dict)
       status = models.CharField(max_length=16, choices=TaskStatus)
       created_at = models.DateTimeField(auto_now_add=True)
       ended_at = models.DateTimeField(null=True)

Task Types
----------

Plugin Tasks
^^^^^^^^^^^^

Execute a plugin on a specific object:

.. code-block:: python

   task = Task.objects.create(
       organization=org,
       type="plugin",
       data={
           "plugin_id": "dns_records",
           "input_data": "internet|example.com",
       }
   )

Business Rule Tasks
^^^^^^^^^^^^^^^^^^^

Evaluate business rules to find security issues:

.. code-block:: python

   task = Task.objects.create(
       organization=org,
       type="business_rule",
       data={
           "rule_id": "check_ssl_expiry",
       }
   )

Report Tasks
^^^^^^^^^^^^

Generate reports:

.. code-block:: python

   task = Task.objects.create(
       organization=org,
       type="report",
       data={
           "report_type": "findings_summary",
           "object_set_id": object_set.pk,
       }
   )

Task Status
-----------

Tasks progress through the following states:

- ``PENDING``: Task created, waiting to be picked up
- ``RUNNING``: Currently being executed
- ``COMPLETED``: Successfully finished
- ``FAILED``: Execution failed

Celery Tasks
------------

Celery tasks are defined in ``tasks/tasks.py``:

.. code-block:: python

   from celery import shared_task
   from tasks.models import Task

   @shared_task
   def run_plugin_task(task_id):
       task = Task.objects.get(pk=task_id)
       task.status = "RUNNING"
       task.save()

       try:
           plugin_id = task.data["plugin_id"]
           input_data = task.data["input_data"]

           # Execute plugin
           result = execute_plugin(plugin_id, input_data, task.organization)

           task.status = "COMPLETED"
           task.ended_at = timezone.now()
           task.save()

       except Exception as e:
           task.status = "FAILED"
           task.ended_at = timezone.now()
           task.data["error"] = str(e)
           task.save()
           raise

Scheduling Tasks
----------------

Schedule Model
^^^^^^^^^^^^^^

Recurring scans are defined via ``Schedule``:

.. code-block:: python

   schedule = Schedule.objects.create(
       organization=org,
       plugin=plugin,
       object_set=object_set,
       interval=timedelta(hours=24),
       enabled=True
   )

How Scheduling Works
^^^^^^^^^^^^^^^^^^^^

1. **Periodic Task**: A Celery beat task runs every minute
2. **Check Schedules**: Finds enabled schedules
3. **Find Objects**: Queries object set for matching objects
4. **Create Tasks**: Creates plugin tasks for objects that haven't been scanned recently
5. **Queue Tasks**: Celery workers pick up and execute tasks

.. code-block:: python

   @periodic_task(run_every=timedelta(minutes=1))
   def create_scheduled_tasks():
       for schedule in Schedule.objects.filter(enabled=True):
           # Get objects matching the object set
           objects = get_objects_for_set(schedule.object_set)

           for obj in objects:
               # Check if object was scanned recently
               last_task = Task.objects.filter(
                   organization=schedule.organization,
                   type="plugin",
                   data__plugin_id=schedule.plugin.plugin_id,
                   data__input_data=obj.pk,
                   created_at__gte=timezone.now() - schedule.interval
               ).first()

               if not last_task:
                   # Create new task
                   Task.objects.create(
                       organization=schedule.organization,
                       type="plugin",
                       data={
                           "plugin_id": schedule.plugin.plugin_id,
                           "input_data": obj.pk,
                       }
                   )

Running Tasks Manually
----------------------

Via Admin Interface
^^^^^^^^^^^^^^^^^^^

Tasks can be triggered manually from the Django admin:

1. Navigate to ``/admin/tasks/task/``
2. Click "Run task" on any pending task

Via REST API
^^^^^^^^^^^^

Create a task via the API:

.. code-block:: http

   POST /api/v1/tasks/
   {
     "type": "plugin",
     "data": {
       "plugin_id": "dns_records",
       "input_data": "internet|example.com"
     }
   }

Via Management Command
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   python manage.py run_task TASK_ID

Task Execution Flow
--------------------

The task execution follows this sequence:

1. **Schedule Check**: Periodic task checks enabled schedules
2. **Task Creation**: Django creates Task with PENDING status
3. **Queue Task**: Task is queued in Redis
4. **Worker Fetch**: Celery worker fetches task from Redis
5. **Status Update**: Worker updates Task to RUNNING
6. **Plugin Execution**: Worker executes the plugin container
7. **Object Creation**: Plugin creates objects via API with task_id parameter
8. **Object Storage**: API saves objects and creates ObjectTask records in XTDB
9. **Result Return**: Plugin returns result to worker
10. **Task Completion**: Worker updates Task to COMPLETED

Viewing Task Status
-------------------

In the Web Interface
^^^^^^^^^^^^^^^^^^^^

Navigate to ``/tasks/`` to see:

- All tasks for your organization
- Task status and execution time
- Error messages for failed tasks
- Plugin output and created objects

Via API Query
^^^^^^^^^^^^^

.. code-block:: http

   GET /api/v1/tasks/TASK_ID/

   {
     "id": "550e8400-e29b-41d4-a716-446655440000",
     "type": "plugin",
     "status": "COMPLETED",
     "created_at": "2025-01-15T10:30:00Z",
     "ended_at": "2025-01-15T10:30:45Z",
     "data": {
       "plugin_id": "dns_records",
       "input_data": "internet|example.com"
     }
   }

ObjectTask Tracking
-------------------

When a plugin creates objects via the API with a ``task_id`` parameter, an ``ObjectTask`` record is created:

.. code-block:: http

   # Plugin calls API
   POST /api/v1/objects/hostname/?task_id=550e8400-e29b-41d4-a716-446655440000
   {
     "network": "internet",
     "name": "subdomain.example.com"
   }

   # This creates:
   # 1. Hostname object
   # 2. ObjectTask linking task to hostname

View which objects a task created:

.. code-block:: python

   task_uuid = "550e8400-e29b-41d4-a716-446655440000"
   task = Task.objects.get(pk=task_uuid)
   object_tasks = ObjectTask.objects.filter(task_id=task_uuid)

   for object_task in object_tasks:
       print(f"Created: {object_task.output_object}")
       print(f"Plugin: {object_task.plugin_id}")
       print(f"Input: {object_task.input_object}")

Celery Configuration
--------------------

Configuration in ``settings.py``:

.. code-block:: python

   # Celery settings
   CELERY_BROKER_URL = "redis://redis:6379/0"
   CELERY_RESULT_BACKEND = "redis://redis:6379/0"
   CELERY_TASK_SERIALIZER = "json"
   CELERY_RESULT_SERIALIZER = "json"
   CELERY_ACCEPT_CONTENT = ["json"]
   CELERY_TIMEZONE = "UTC"
   CELERY_ENABLE_UTC = True

   # Beat schedule
   CELERY_BEAT_SCHEDULE = {
       "create-scheduled-tasks": {
           "task": "tasks.tasks.create_scheduled_tasks",
           "schedule": crontab(minute="*"),  # Every minute
       },
       "run-business-rules": {
           "task": "tasks.tasks.run_business_rules",
           "schedule": crontab(minute="*/15"),  # Every 15 minutes
       },
   }

Running the Worker
------------------

In development:

.. code-block:: bash

   # Start worker
   celery -A openkat worker -l info

   # Start beat scheduler
   celery -A openkat beat -l info

   # Or both together
   celery -A openkat worker -B -l info

In production (via Docker):

.. code-block:: bash

   docker compose up -d worker

Debugging Failed Tasks
----------------------

View Error Details
^^^^^^^^^^^^^^^^^^

Failed tasks store error information in the ``data`` field:

.. code-block:: python

   task = Task.objects.get(pk=task_id)
   if task.status == "FAILED":
       print(task.data.get("error"))
       print(task.data.get("traceback"))

Retry Failed Task
^^^^^^^^^^^^^^^^^

.. code-block:: python

   # Reset task status
   task.status = "PENDING"
   task.save()

   # Re-queue the task
   run_plugin_task.delay(task.id)

Worker Logs
^^^^^^^^^^^

Check worker container logs:

.. code-block:: bash

   docker compose logs -f worker

Best Practices
--------------

1. **Idempotent Tasks**: Tasks should be safe to retry
2. **Timeout Handling**: Set reasonable timeouts for long-running tasks
3. **Error Handling**: Catch and log exceptions properly
4. **Status Updates**: Update task status at each stage
5. **Resource Cleanup**: Clean up resources in finally blocks
6. **Task Chaining**: Use Celery's chain/group for complex workflows
7. **Monitoring**: Monitor task queue length and worker capacity
