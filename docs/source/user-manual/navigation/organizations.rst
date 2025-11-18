Organizations
=============

The Organizations page provides an overview of all organizations you are a member of and allows you to switch between them.

Organization List
-----------------

The Organizations page displays a table with the following information for each organization:

- **Name**: The full name of the organization
- **Code**: The unique identifier code for the organization
- **Tags**: Labels assigned to the organization for categorization
- **Settings**: Link to access organization configuration

Selecting an Organization
--------------------------

To work with a specific organization:

1. Navigate to the Organizations page
2. Click on an organization name or use the organization dropdown in the header
3. All other pages (Plugins, Findings, Objects, etc.) will now show data for the selected organization

The currently selected organization is displayed in the header navigation.

Creating a New Organization
----------------------------

If you have the appropriate permissions, you can create a new organization:

1. Click the "Add new organization" button on the Organizations page
2. Fill in the required information:

   - Organization name
   - Organization code (unique identifier)
   - Optional tags for categorization

3. Save the organization

After creation, you can configure the organization settings, add members, and set up indemnification.

Organization Settings
---------------------

Click the "Settings" button next to an organization to access:

- **General settings**: Organization name, code, and tags
- **Indemnification**: Set up scan level authorization
- **Members**: Manage users and their roles
- **Clearance levels**: Configure user permissions

See :doc:`settings` and :doc:`members` for detailed information about organization configuration.

Multi-Organization Support
---------------------------

OpenKAT v2 supports multiple organizations within a single installation:

- Each organization has its own isolated data
- Objects, findings, and tasks are separated by organization
- Users can be members of multiple organizations
- Switch between organizations using the header dropdown

This allows managed service providers to serve multiple clients or large organizations to separate different departments.
