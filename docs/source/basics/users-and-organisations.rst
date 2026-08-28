.. _users-and-organizations:

Users and organizations
=======================

OpenKAT has a superuser, several usertypes and organizations.

Organizations
-------------

Organizations own the systems for which KAT is deployed. From KAT, multiple organizations can be monitored simultaneously, each with its own settings. The superuser can add new organizations and each organization has its own users.

.. _users-and-organisations_users:

Users
-----

OpenKAT knows four types of users: the client, the red team user, the admin and the superuser. In OpenKAT, permissions utilise a stacked model. This means that a higher permission level includes all lower permissions of the lower levels. The client is a 'read only' type of user, the red teamer is a researcher who can start scans. The admin is an administrative user who can do user management etc, the superuser has the ability to do everything.

Rights and functions per user type
----------------------------------

+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Action                                                                                              | USER | RED TEAM | ADMIN | SUPERUSER |
+=====================================================================================================+======+==========+=======+===========+
| Login                                                                                               | x    | x        | x     | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Can start scans on objects with enough clearance                                                    | x    | x        | x     | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Can view reports                                                                                    | x    | x        | x     | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Can start scans on objects with not enough clearance, but the user has enough clearance             |      | x        | x     | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Can edit settings of scan tools                                                                     |      | x        | x     | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Can enable/disable scan tools                                                                       |      | x        | x     | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Can add objects                                                                                     |      | x        | x     | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Can give clearance to objects up to it’s own clearance level                                        |      | x        | x     | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Can give clearance to users                                                                         |      |          | x     | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Can manage organisation members                                                                     |      |          | x     | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Can create new account(s) in OpenKAT                                                                |      |          | x     | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Can create new and add, or add existing accounts, to the organisation                               |      |          | x     | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Can view users of an organisation                                                                   |      |          | x     | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Can edit users of an organisation                                                                   |      |          | x     | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Can view organisation details                                                                       |      |          | x     | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Can edit organisation details and settings                                                          |      |          | x     | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Can add organisations                                                                               |      |          |       | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Can start scans on objects regardless of clearance                                                  |      |          |       | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+
| Can access Django admin                                                                             |      |          |       | x         |
+-----------------------------------------------------------------------------------------------------+------+----------+-------+-----------+

User management
---------------

Users and organizations can be created in the on boarding flow, in the Web interface or automated. The administrator of the system can create organizations and do user management. The administrator of an organization in turn can create users within the organization. The django interface provides additional capabilities for user management via the command line, for use in an automated deployment and linkage to external user management.

Adding users through a CSV file
-------------------------------

Adding multiple users at a time to OpenKAT can be done using a CSV file. To make this work SMTP should be configured.

How does it work?
*****************

Select the organization to which the new users will be added. On the members page click the Add member(s) menu and select Upload a CSV. This takes you to the CSV upload page.

Download the template file, fill in the data of the users you want to add and upload them into the system. The new users will be added to the organization of your choice.

How should I prepare the CSV file?
**********************************

CSV files are great when they work. Edit the downloaded template file and use a plain texteditor to make sure your CSV file contains exactly what is needed for its purpose.

Each user will have its on line in the CSV file. The template has five columns: full_name, email, account_type, trusted_clearance_level, acknowledged_clearance_level.

*User details:*

A user is recognized by their full name and email address.

* full_name : the full name of the user
* email : a working emailadress of the user

*User type:*

Through the CSV upload you can add the usertypes client, admin and redteam. Read about users and roles in the :ref:`users-and-organisations_users` section.

* account_type : client, admin or redteam

*User clearance:*

Clearance levels are related to the scan level of the Boefjes a user is able to dispatch. Read about this in the :ref:`scan-levels-clearance-indemnities` section.

The trusted_clearance_level is the level a user receives from the organization. It is the maximum level available for this user, based on the decision of the admin or superuser. The acknowledged_clearance_level is the level accepted by the user. Both can be added in the CSV file. The accepted level can be changed by the user.

* trusted_clearance_level : between -1 and 4
* accepted_clearance_level : between -1 and 4

The ability to add the accepted clearance level allows you to copy users from one organization to another, which might be needed on larger installs. The user should have accepted this level at some point, in- or outside OpenKAT.

*Warnings*

If the CSV file contains data that cannot be parsed OpenKAT will give a warning with the data concerned.

User notification
*****************

After the CSV file has been uploaded the users receive a welcome email on their account. The link in this email allows them to create a password for their account. If SMTP is not configured on your install, this will not work.

::

 Content-Type: text/plain; charset="utf-8"
 MIME-Version: 1.0
 Content-Transfer-Encoding: 7bit
 Subject: Verify OpenKAT account on localhost:8000
 From:
 To: a@bbbb.dl
 Date: Thu, 20 Jul 2023 13:34:32 -0000
 Message-ID: <168986007241.76.14464090403674779824@af745d470510>

 Welcome to OpenKAT. You're receiving this email because you have been added to organization "test" at localhost:8000.
 Please go to the following page and choose a new password:

  http://localhost:8000/en/reset/MTY/brn1pk-914a9d550dbb2a5b0269c85f6b667e21/

 Sincerely,
 The OpenKAT team


API token authentication
------------------------

Authentication tokens can be created in the admin interface (/admin). The token is created for an user account and will have the same permissions as the user. After creating a token it will display the newly created token once. You need to copy the token immediately, because the token are stored hashed in the database and won't be visible anymore.

The token can be used by adding the Authorization header with the token to the request:

::

    Authorization: Token f2505ed4d2a51624fe1691c977789ce00dc9886d48271c6c91a25e7dd258c932

For example this will use the token to get the list of organizations:

.. code-block:: sh

    curl -H 'Authorization: Token f2505ed4d2a51624fe1691c977789ce00dc9886d48271c6c91a25e7dd258c932' http://127.0.0.1:8000/api/v1/organization/
