============================
Production Deployment
============================

This guide covers deploying OpenKAT v2 in a production environment.

.. important::

   This guide provides **example configurations** for production deployment. The ``docker-compose.prod.yml`` file shown here is a reference implementation and should be adapted to your specific infrastructure needs.

   For production environments, consider:

   - Using managed database services (AWS RDS, Google Cloud SQL, Azure Database)
   - Implementing proper secrets management (Vault, AWS Secrets Manager)
   - Setting up monitoring and alerting
   - Using container orchestration platforms (Kubernetes, ECS, etc.) for larger deployments
   - Following your organization's security and compliance requirements

Overview
========

OpenKAT v2 is deployed as a set of Docker containers. This guide demonstrates Docker Compose deployment, which is suitable for smaller production environments or as a starting point.

Unlike v1, OpenKAT v2 uses a monolithic architecture with only 5 containers, making production deployment significantly simpler.

Prerequisites
=============

- Docker Engine 20.10+ and Docker Compose 2.0+
- Linux server (Ubuntu 22.04 LTS recommended)
- Domain name with DNS configured
- SSL/TLS certificates (Let's Encrypt recommended)
- Minimum 16 GB RAM, 4 CPU cores, 100 GB disk space

Pre-built Docker Images
=======================

OpenKAT provides pre-built Docker images on GitHub Container Registry:

- ``ghcr.io/minvws/openkat/openkat:latest`` - Latest stable release
- ``ghcr.io/minvws/openkat/openkat:<version>`` - Specific version

Use specific version tags in production for stability.

Production Setup
================

1. Clone Repository
*******************

.. code-block:: bash

   $ git clone https://github.com/minvws/nl-kat-coordination.git
   $ cd nl-kat-coordination
   $ git checkout VERSION_TAG  # e.g., v2.0.0

2. Configure Environment
************************

Create a ``.env`` file with production settings:

.. code-block:: bash

   # Database Configuration
   DATABASE_HOST=postgres
   DATABASE_PORT=5432
   DATABASE_NAME=openkat_prod
   DATABASE_USER=openkat_prod
   DATABASE_PASSWORD=SECURE_PASSWORD

   XTDB_HOST=xtdb
   XTDB_PORT=5433
   XTDB_DATABASE=xtdb_prod
   XTDB_USER=xtdb_prod
   XTDB_PASSWORD=SECURE_PASSWORD

   # Redis Configuration
   REDIS_URL=redis://redis:6379/0

   # Django Configuration
   DJANGO_SECRET_KEY=GENERATE_SECURE_KEY
   DJANGO_DEBUG=False
   DJANGO_ALLOWED_HOSTS=your-domain.com,www.your-domain.com

   # Superuser (for initial setup only)
   DJANGO_SUPERUSER_EMAIL=admin@your-domain.com
   DJANGO_SUPERUSER_PASSWORD=SECURE_PASSWORD

   # Security
   SECURE_SSL_REDIRECT=True
   SESSION_COOKIE_SECURE=True
   CSRF_COOKIE_SECURE=True

   # Email Configuration
   EMAIL_HOST=smtp.your-domain.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=True
   EMAIL_HOST_USER=noreply@your-domain.com
   EMAIL_HOST_PASSWORD=EMAIL_PASSWORD
   DEFAULT_FROM_EMAIL="OpenKAT <noreply@your-domain.com>"

   # Celery Configuration
   CELERY_WORKER_CONCURRENCY=4

**Important**: Generate a secure ``DJANGO_SECRET_KEY`` using:

.. code-block:: bash

   $ python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

3. Configure Docker Compose
****************************

Use the production Docker Compose configuration:

.. code-block:: yaml

   # docker-compose.prod.yml
   version: '3.8'

   services:
     openkat:
       image: ghcr.io/minvws/openkat/openkat:${VERSION:-latest}
       env_file: .env
       ports:
         - "8000:8000"
       depends_on:
         - postgres
         - xtdb
         - redis
       volumes:
         - media:/app/media
         - static:/app/static
       restart: unless-stopped

     worker:
       image: ghcr.io/minvws/openkat/openkat:${VERSION:-latest}
       env_file: .env
       command: celery -A openkat worker -l info
       depends_on:
         - postgres
         - xtdb
         - redis
       restart: unless-stopped

     postgres:
       image: postgres:15
       env_file: .env
       volumes:
         - postgres_data:/var/lib/postgresql/data
       restart: unless-stopped

     xtdb:
       image: ghcr.io/dekkers/xtdb-http-multinode:latest
       env_file: .env
       volumes:
         - xtdb_data:/var/lib/xtdb
       restart: unless-stopped

     redis:
       image: redis:7-alpine
       volumes:
         - redis_data:/data
       restart: unless-stopped

   volumes:
     postgres_data:
     xtdb_data:
     redis_data:
     media:
     static:

4. Start Services
*****************

.. code-block:: bash

   $ docker compose -f docker-compose.prod.yml up -d

5. Initialize Database
**********************

.. code-block:: bash

   $ docker compose -f docker-compose.prod.yml exec openkat python manage.py migrate
   $ docker compose -f docker-compose.prod.yml exec openkat python manage.py collectstatic --noinput
   $ docker compose -f docker-compose.prod.yml exec openkat python manage.py createsuperuser --noinput

Reverse Proxy Setup
===================

Use NGINX as a reverse proxy for SSL termination and static file serving.

NGINX Configuration
*******************

.. code-block:: nginx

   upstream openkat {
       server localhost:8000;
   }

   server {
       listen 80;
       server_name your-domain.com www.your-domain.com;
       return 301 https://$server_name$request_uri;
   }

   server {
       listen 443 ssl http2;
       server_name your-domain.com www.your-domain.com;

       ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

       client_max_body_size 100M;

       location /static/ {
           alias /var/www/openkat/static/;
       }

       location /media/ {
           alias /var/www/openkat/media/;
       }

       location / {
           proxy_pass http://openkat;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }

SSL Certificates
****************

Use Let's Encrypt for free SSL certificates:

.. code-block:: bash

   $ sudo apt install certbot python3-certbot-nginx
   $ sudo certbot --nginx -d your-domain.com -d www.your-domain.com

Scaling
=======

Horizontal Scaling
******************

Scale worker containers:

.. code-block:: bash

   $ docker compose -f docker-compose.prod.yml up -d --scale worker=5

Scale web containers (requires load balancer):

.. code-block:: bash

   $ docker compose -f docker-compose.prod.yml up -d --scale openkat=3

Database Scaling
****************

**PostgreSQL**:

- Use managed PostgreSQL service (AWS RDS, Google Cloud SQL)
- Configure read replicas for reporting
- Regular backups and point-in-time recovery

**XTDB**:

- Can be clustered for high availability
- Consider managed hosting for large installations

**Redis**:

- Use Redis Cluster or managed Redis (AWS ElastiCache)
- Configure persistence for task queue durability

Monitoring
==========

Health Checks
*************

Monitor these endpoints:

- ``/health/`` - Application health
- ``/admin/`` - Admin interface (check authentication)

Application Monitoring
**********************

Use Django logging and monitoring tools:

.. code-block:: python

   # settings.py
   LOGGING = {
       'version': 1,
       'handlers': {
           'file': {
               'class': 'logging.FileHandler',
               'filename': '/var/log/openkat/django.log',
           },
       },
       'loggers': {
           'django': {
               'handlers': ['file'],
               'level': 'INFO',
           },
       },
   }

Infrastructure Monitoring
*************************

Monitor:

- CPU, RAM, disk usage
- Database connections and query performance
- Celery queue length
- Container health and restarts

Use tools like:

- Prometheus + Grafana
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Cloud provider monitoring (CloudWatch, Stackdriver)

Backups
=======

Database Backups
****************

**PostgreSQL**:

.. code-block:: bash

   # Daily backup script
   #!/bin/bash
   DATE=$(date +%Y%m%d_%H%M%S)
   docker compose exec -T postgres pg_dump -U openkat_prod openkat_prod | gzip > /backups/openkat_${DATE}.sql.gz

   # Retention: keep last 30 days
   find /backups -name "openkat_*.sql.gz" -mtime +30 -delete

**XTDB**:

.. code-block:: bash

   # Backup XTDB data directory
   tar -czf /backups/xtdb_${DATE}.tar.gz /var/lib/docker/volumes/openkat_xtdb_data

Media Files
***********

Backup uploaded files:

.. code-block:: bash

   rsync -av /var/lib/docker/volumes/openkat_media/ /backups/media/

Restore Procedure
*****************

.. code-block:: bash

   # Restore PostgreSQL
   gunzip < openkat_backup.sql.gz | docker compose exec -T postgres psql -U openkat_prod openkat_prod

   # Restore XTDB
   docker compose down
   tar -xzf xtdb_backup.tar.gz -C /var/lib/docker/volumes/

   # Restore media
   rsync -av /backups/media/ /var/lib/docker/volumes/openkat_media/

   docker compose up -d

Security Hardening
==================

See :doc:`hardening` for detailed security configuration.

Key recommendations:

- Use strong, unique passwords
- Enable Django security middleware
- Configure firewall rules
- Regular security updates
- SSL/TLS only
- Disable DEBUG mode
- Restrict admin access by IP
- Enable audit logging

Maintenance
===========

Regular Updates
***************

Update to new releases:

.. code-block:: bash

   # Pull new images
   $ docker compose -f docker-compose.prod.yml pull

   # Restart with new images
   $ docker compose -f docker-compose.prod.yml up -d

   # Run migrations
   $ docker compose -f docker-compose.prod.yml exec openkat python manage.py migrate

Log Rotation
************

Configure logrotate:

.. code-block:: text

   /var/log/openkat/*.log {
       daily
       missingok
       rotate 30
       compress
       delaycompress
       notifempty
       create 0640 www-data www-data
   }

Troubleshooting
===============

View Logs
*********

.. code-block:: bash

   # Application logs
   $ docker compose logs -f openkat

   # Worker logs
   $ docker compose logs -f worker

   # Database logs
   $ docker compose logs -f postgres

Common Issues
*************

**502 Bad Gateway**:
  - Check if openkat container is running
  - Verify NGINX configuration
  - Check application logs

**Database connection errors**:
  - Verify DATABASE_HOST and credentials in .env
  - Check if postgres container is healthy
  - Review network connectivity

**Celery tasks not running**:
  - Check worker container status
  - Verify REDIS_URL configuration
  - Review worker logs for errors

**Out of memory**:
  - Scale down worker concurrency
  - Add more RAM
  - Optimize database queries

Support
=======

- Documentation: https://docs.openkat.nl
- GitHub Issues: https://github.com/minvws/nl-kat-coordination/issues
- Security Issues: security@openkat.nl
