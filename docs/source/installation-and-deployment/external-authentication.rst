=======================
External authentication
=======================

OpenKAT supports external authentication using Django's built-in `remote user
authentication <https://docs.djangoproject.com/en/4.2/howto/auth-remote-user/>`__.
Make sure that you read the warning in the Django documentation before you
configure this.

Configuration of this can be done using two environments variables. The
``REMOTE_USER_HEADER`` variable specifies the header that has the e-mail address
that is used as username in OpenKAT. Setting this variable will also enable the
remote user backend. The ``REMOTE_USER_DEFAULT_ORGANIZATIONS`` variable is
optional and is a comma separated list of "organisation:group" items and
configures which organisation every remote user get access to by default. The
value of ``REMOTE_USER_DEFAULT_ORGANIZATIONS`` will override any changes made and
if someone is removed from a group that is listed they will automatically be
added back the next time they use OpenKAT using remote user authentication.

Example configuration:

.. code-block:: sh

    REMOTE_USER_HEADER=HTTP_X_EMAIL
    REMOTE_USER_DEFAULT_ORGANIZATIONS=org1:admin,org2:client

This will use the value of ``X-Email`` HTTP header as the e-mail address for the
user account. Every user will be added to org1 with admin permissions and to org
with client permissions.

An easy solution for configuring single-sign on using OAuth is `oauth2-proxy
<https://oauth2-proxy.github.io/oauth2-proxy/>`__.
