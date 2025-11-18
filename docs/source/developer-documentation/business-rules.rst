Business Rules
==============

Business rules in OpenKAT v2 are SQL-based queries that detect security findings in the XTDB object database.

Overview
--------

Business rules allow you to:

- Define custom security checks
- Automatically create findings
- Run periodically via Celery
- Clean up invalid findings

Business Rule Model
-------------------

.. code-block:: python

   class BusinessRule(models.Model):
       name = models.CharField(max_length=255)
       description = models.TextField(blank=True)
       finding_type = models.CharField(max_length=100)
       query = models.TextField()  # SQL to find issues
       inverse_query = models.TextField(blank=True)  # SQL to clean up
       enabled = models.BooleanField(default=True)
       severity = models.CharField(max_length=20, default="medium")
       organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True)

Writing Business Rules
----------------------

Basic Structure
***************

A business rule consists of:

1. **Query**: SQL that returns objects with issues
2. **Inverse Query**: SQL that finds findings that are no longer valid
3. **Finding Type**: Identifier for the type of finding
4. **Severity**: How serious the issue is

Example: SSL Expiring Soon
***************************

.. code-block:: sql

   -- Query: Find hostnames with SSL certificates expiring in < 30 days
   SELECT DISTINCT
       hostname._id as object_id,
       'SSL certificate expires in less than 30 days' as description
   FROM
       public.objects_hostname as hostname
   WHERE
       hostname._id IN (
           SELECT ssl_cert.hostname_id
           FROM public.objects_sslcertificate as ssl_cert
           WHERE ssl_cert.expiry_date < NOW() + INTERVAL '30 days'
             AND ssl_cert.expiry_date > NOW()
       )

.. code-block:: sql

   -- Inverse Query: Find findings where certificates no longer expire soon
   SELECT finding._id
   FROM public.objects_finding as finding
   WHERE finding.finding_type = 'SSL_EXPIRY_WARNING'
     AND finding.object NOT IN (
         SELECT hostname._id
         FROM public.objects_hostname as hostname
         WHERE hostname._id IN (
             SELECT ssl_cert.hostname_id
             FROM public.objects_sslcertificate as ssl_cert
             WHERE ssl_cert.expiry_date < NOW() + INTERVAL '30 days'
               AND ssl_cert.expiry_date > NOW()
         )
     )

Creating Business Rules
-----------------------

Via Django Admin
****************

1. Navigate to ``/admin/business_rules/businessrule/``
2. Click "Add Business Rule"
3. Fill in fields:

   - **Name**: Descriptive name
   - **Finding Type**: Unique identifier (e.g., "SSL_EXPIRY_WARNING")
   - **Query**: SQL to find issues
   - **Inverse Query**: SQL to clean up
   - **Enabled**: Check to activate
   - **Severity**: critical/high/medium/low

4. Save

Via Code
********

.. code-block:: python

   BusinessRule.objects.create(
       name="Weak SSL Ciphers",
       finding_type="WEAK_SSL_CIPHER",
       description="Detects hostnames using weak SSL ciphers",
       query="""
           SELECT DISTINCT
               hostname._id as object_id,
               'Weak SSL cipher detected: ' || cipher.name as description
           FROM
               public.objects_hostname as hostname
               JOIN public.objects_sslcipher as cipher
                   ON cipher.hostname_id = hostname._id
           WHERE
               cipher.strength < 128
       """,
       inverse_query="""
           SELECT finding._id
           FROM public.objects_finding as finding
           WHERE finding.finding_type = 'WEAK_SSL_CIPHER'
             AND finding.object NOT IN (
                 SELECT hostname._id
                 FROM public.objects_hostname as hostname
                 JOIN public.objects_sslcipher as cipher
                     ON cipher.hostname_id = hostname._id
                 WHERE cipher.strength < 128
             )
       """,
       severity="high",
       enabled=True,
       organization=org
   )

Execution
---------

Business rules run via Celery on a schedule:

.. code-block:: python

   # In celerybeat schedule
   CELERY_BEAT_SCHEDULE = {
       "run-business-rules": {
           "task": "business_rules.tasks.run_business_rules",
           "schedule": crontab(minute="*/15"),  # Every 15 minutes
       },
   }

Manual Execution
****************

Run all rules for an organization:

.. code-block:: bash

   python manage.py run_business_rules --organization=myorg

Run a specific rule:

.. code-block:: bash

   python manage.py run_business_rule --id=42

How Rules Execute
*****************

.. code-block:: python

   @shared_task
   def run_business_rules():
       for org in Organization.objects.all():
           for rule in BusinessRule.objects.filter(enabled=True, organization=org):
               # Execute query
               with connections["xtdb"].cursor() as cursor:
                   cursor.execute(rule.query)
                   results = cursor.fetchall()

                   # Create findings
                   for row in results:
                       Finding.objects.get_or_create(
                           finding_type=rule.finding_type,
                           object=row[0],  # object_id from query
                           defaults={
                               "description": row[1] if len(row) > 1 else rule.description,
                               "severity": rule.severity,
                           }
                       )

               # Run inverse query to clean up
               if rule.inverse_query:
                   with connections["xtdb"].cursor() as cursor:
                       cursor.execute(rule.inverse_query)
                       to_delete = cursor.fetchall()

                       for row in to_delete:
                           Finding.objects.filter(pk=row[0]).delete()

Query Best Practices
--------------------

1. Return object_id and description
************************************

.. code-block:: sql

   SELECT
       hostname._id as object_id,  -- Required
       'Issue description' as description  -- Optional but recommended
   FROM ...

2. Use DISTINCT to Avoid Duplicates
************************************

.. code-block:: sql

   SELECT DISTINCT
       hostname._id as object_id,
       ...

3. Index-Friendly Queries
**************************

.. code-block:: sql

   -- Good: Uses index on _id
   WHERE hostname._id IN (SELECT ...)

   -- Bad: Full table scan
   WHERE hostname.name LIKE '%example%'

4. Handle NULL Values
*********************

.. code-block:: sql

   WHERE ssl_cert.expiry_date IS NOT NULL
     AND ssl_cert.expiry_date < NOW() + INTERVAL '30 days'

Common Patterns
---------------

Missing Security Headers
************************

.. code-block:: sql

   SELECT DISTINCT
       hostname._id as object_id,
       'Missing security header: ' || header.name as description
   FROM
       public.objects_hostname as hostname
   WHERE NOT EXISTS (
       SELECT 1
       FROM public.objects_httpheader as header
       WHERE header.hostname_id = hostname._id
         AND header.name IN ('Strict-Transport-Security', 'X-Frame-Options')
   )

Outdated Software
*****************

.. code-block:: sql

   SELECT DISTINCT
       hostname._id as object_id,
       'Outdated software: ' || software.name || ' ' || software.version as description
   FROM
       public.objects_hostname as hostname
       JOIN public.objects_software as software
           ON software.hostname_id = hostname._id
   WHERE
       software.name = 'Apache'
       AND software.version < '2.4.50'

Open Ports
**********

.. code-block:: sql

   SELECT DISTINCT
       ipaddress._id as object_id,
       'Open port: ' || port.port as description
   FROM
       public.objects_ipaddress as ipaddress
       JOIN public.objects_ipport as port
           ON port.ip_address_id = ipaddress._id
   WHERE
       port.port IN (23, 135, 139, 445)  -- Dangerous ports
       AND port.state = 'open'

Testing Business Rules
----------------------

Test in SQL Client
******************

.. code-block:: bash

   # Connect to XTDB
   psql -U xtdb -h localhost -p 5433 xtdb

   # Test query
   SELECT DISTINCT
       hostname._id as object_id,
       'Test finding' as description
   FROM
       public.objects_hostname as hostname
   LIMIT 10;

Unit Tests
**********

.. code-block:: python

   def test_ssl_expiry_rule():
       # Create test data
       hostname = Hostname.objects.create(
           network=network,
           name="test.example.com"
       )

       ssl_cert = SSLCertificate.objects.create(
           hostname=hostname,
           expiry_date=timezone.now() + timedelta(days=15)  # Expires soon
       )

       # Run business rule
       rule = BusinessRule.objects.get(finding_type="SSL_EXPIRY_WARNING")
       run_business_rule(rule, organization)

       # Check finding was created
       finding = Finding.objects.get(
           finding_type="SSL_EXPIRY_WARNING",
           object=hostname.pk
       )
       assert finding is not None

Debugging
---------

Enable SQL Logging
******************

.. code-block:: python

   # In settings.py
   LOGGING = {
       "loggers": {
           "django.db.backends": {
               "level": "DEBUG",
               "handlers": ["console"],
           },
       },
   }

Check Execution Logs
********************

.. code-block:: bash

   # View Celery logs
   docker compose logs -f worker

   # Filter for business rules
   docker compose logs -f worker | grep "business_rule"

Dry Run
*******

Test a rule without creating findings:

.. code-block:: python

   def dry_run_business_rule(rule, org):
       with connections["xtdb"].cursor() as cursor:
           cursor.execute(rule.query)
           results = cursor.fetchall()

           print(f"Would create {len(results)} findings:")
           for row in results:
               print(f"  - {row[0]}: {row[1] if len(row) > 1 else 'N/A'}")

Performance Considerations
--------------------------

1. **Limit Complexity**: Keep queries simple for faster execution
2. **Use Indexes**: Query on indexed fields (\_id, foreign keys)
3. **Batch Processing**: Process findings in batches
4. **Schedule Wisely**: Don't run too frequently for expensive queries
5. **Monitor Execution Time**: Set alerts for slow queries

Best Practices
--------------

1. **Test Thoroughly**: Test queries on real data before enabling
2. **Document Well**: Explain what the rule detects and why
3. **Version Control**: Keep rules in migration files or fixtures
4. **Organization-Specific**: Create rules per organization when needed
5. **Regular Review**: Review and update rules as threats evolve
6. **False Positive Handling**: Implement ways to mute findings
7. **Severity Accuracy**: Use appropriate severity levels
8. **Inverse Queries**: Always implement cleanup queries
