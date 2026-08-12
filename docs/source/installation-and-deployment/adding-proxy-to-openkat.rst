=======================
Adding NGINX to OpenKAT
=======================

Adding a proxy to OpenKAT adds an extra layer of security and creates a clear communications channel. Bas van der Linden made a guide for the installation of NGINX, the efficient OSS webserver which can be used as a proxy for OpenKAT. He suggests it as a good start for a test setup, not for production due to missing settings for security headers. We're happy to include it here.

Background
==========

OpenKAT has a number of security measures built in, including those for processing and handling cookies. One way you might notice this is during the installation. If you try to connect to a new OpenKAT installation, there is a good chance you will encounter an error message about secure cookies and CSRF (Cross-site request forgery). This can be a bit confusing.

The context of the message is that OpenKAT can't properly assess whether the communication is really clearly going from the right address to the right address and is secure. So you have to do something about that.

One option for this is a so-called proxy service, a service that handles communication with the outside world on behalf of OpenKAT. There are several options for that, but usual practice is to use a web server for that. In this example, we use nginx, an efficient and fast open source web server, for this purpose.

Installation
============

We will use nginx and certbot to facilitate https connections.

Install the appropriate packages for this:

.. code-block:: sh

    $ sudo apt-get install nginx certbot python3-certbot-nginx

Next, we will build a basic configuration for nginx. In the example below, we use the server name openkat.example.com, obviously change this to the name of your own server.

By default, on Ubuntu systems, nginx puts its configurations in the directory /etc/nginx/sites-available/. We therefore also create the configuration file for our server in this directory:

.. code-block:: sh

    $ nano /etc/nginx/sites-available/openkat.example.com

Then put the following content in there, but replace the domain name `openkat.example.com` with the domain name you are using for this OpenKAT install:

.. code-block:: sh

    server {
        listen 80;
        server_name  openkat.example.com;
        access_log   /var/log/nginx/openkat.example.com-access.log;
        error_log	/var/log/nginx/openkat.example.com-error.log;
        location / {
            proxy_set_header HOST $host;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_pass http://localhost:8000;
        }
    }

With this, we have set up minimal things for OpenKAT. Much more is possible, but this is the minimum we need to use OpenKAT properly.
we assume that OpenKAT listens on the server to port 8000, you could check this by doing ``wget -O- localhost:8000`` it should show you some html output.

Logging
=======

We write the log files in the directory ``/var/log/nginx/``.
If you rename the log files (in particular, give them an extension other than .log) or put them in a different place, you will have to reconfigure Logrotate for this as well, otherwise, the log files will continue to grow indefinitely.
For this, see the configuration in the file ``/etc/logrotate.d/nginx``

Activation
==========

Now that we have the configuration, we need to activate it. To do this, use the following command:

.. code-block:: sh

    $ ln -sf /etc/nginx/sites-available/openkat.example.com /etc/nginx/sites-enabled/

(Obviously adjust the file names to what you have used yourself)

You can check that the configuration is correct with the following command:

.. code-block:: sh

    $ nginx -t

If everything is okay, it will report it that way. If there is an error in the configuration (because you forgot an ; somewhere, for example), it will show you the line number where the problem is near. Note: So you might need to add an ; on the previous line.

.. code-block:: sh

    $ service nginx reload

SSL certificates
================

With this basic configuration, we can then let Certbot arrange an SSL certificate; Certbot itself will also take care of setting this up in your web server configuration.
Before we can setup a certificate, you need to make sure the domain name you used in the earlier config points to the external IP address for the host running nginx.

This is very simple: you just need to start Certbot and answer the questions. Starting Certbot is done with the following command:

.. code-block:: sh

    $ certbot

If all went well, you now have an nginx configuration containing an SSL certificate configured.

Restart NGINX and go
====================

Restart nginx to load all the configurations and you can use OpenKAT! The command for that is:

.. code-block:: sh

    $ service nginx restart

Once everything has rebooted, you can access your installation via the hostname you set up, e.g. https://openkat.example.com/

Security settings
=================

Certbot takes care of several settings and you can find more relevant headers in the 'hardening' section of this manual.
