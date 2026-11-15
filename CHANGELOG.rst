===========================
fjacquet.ppdm Release Notes
===========================

.. contents:: Topics

v0.3.0
======

Release Summary
---------------

Moves the protection rule modules to the v3 rule API and adds resource group, protection group, asset and host modules.

Minor Changes
-------------

- Adds the modules resource_group, resource_group_info, protection_group, protection_group_info, asset_info and host_info.
- asset_info masks the top-level ``credentials`` field of the assets it returns; host_info masks nothing.

Breaking Changes / Porting Guide
--------------------------------

- protection_rule, protection_rule_info and protection_rule_run - now use the v3 rule API. The options ``conditions`` and ``condition_connector`` are replaced by ``filters``, ``inventory_source_type`` by ``object_subtypes``, ``tenant`` is removed, ``policy`` is replaced by ``action`` plus ``protection_policy`` (or ``protection_policy_id``), ``rules`` by ``rule`` (protection_rule_run), and ``preview_action`` by ``action_name`` with ``preview``. The ``protection.create_rule`` and ``protection.run_rule`` playbook variables changed accordingly.

New Modules
-----------

- asset_info - Get assets from PowerProtect Data Manager
- host_info - Get hosts from PowerProtect Data Manager
- protection_group - Manage protection groups on PowerProtect Data Manager
- protection_group_info - Get protection groups from PowerProtect Data Manager
- resource_group - Manage resource groups on PowerProtect Data Manager
- resource_group_info - Get resource groups from PowerProtect Data Manager

v0.2.0
======

Release Summary
---------------

Adds the protection modules ``protection_policy``, ``protection_policy_info``, ``protection_policy_assets``, ``protection_policy_run``, ``discovery``, ``protection_rule``, ``protection_rule_info`` and ``protection_rule_run``, and five protection playbooks (63 in total). The rule modules use the v2 rule API, which PPDM deprecated in 20.2 and removes in 20.6.

Breaking Changes / Porting Guide
--------------------------------

- protection.add_file_system_policy and protection.add_mssql_policy playbooks - now update an existing policy when it differs (PATCH, the whole objectives list is replaced) instead of leaving it unchanged.
- protection.assign_assets_to_policy playbook - now requires ``assign_confirm=true``.
- protection.run_policy playbook - now requires ``policy_run_confirm=true`` and a non-empty ``asset_filter``, and the ``backup_level`` variable is removed (every objective of the policy runs).

New Modules
-----------

- discovery - Start a discovery on PowerProtect Data Manager
- protection_policy - Manage protection policies on PowerProtect Data Manager
- protection_policy_assets - Assign or unassign assets to a protection policy on PowerProtect Data Manager
- protection_policy_info - Get protection policies from PowerProtect Data Manager
- protection_policy_run - Run a protection policy now on PowerProtect Data Manager
- protection_rule - Manage protection rules on PowerProtect Data Manager
- protection_rule_info - Get protection rules from PowerProtect Data Manager
- protection_rule_run - Run protection rules or preview their conflicts on PowerProtect Data Manager

v0.1.0
======

Release Summary
---------------

First pre-release of the unofficial fjacquet.ppdm collection for Dell PowerProtect Data Manager 20.3.0. It provides ten modules (a generic ``api`` module, info modules, and ensure-style modules), a ``bootstrap`` role and 58 playbooks grouped by use case. The ``api`` module accepts a list as well as a dictionary as request body, and the modules return the raw API response bodies (secrets masked), not reshaped data.

New Modules
-----------

- api - Call any PowerProtect Data Manager REST endpoint
- certificate - Trust or remove a host certificate on PowerProtect Data Manager
- certificate_info - Get certificates from PowerProtect Data Manager
- credential - Manage credentials on PowerProtect Data Manager
- credential_info - Get credentials from PowerProtect Data Manager
- eula - Accept an end user license agreement on PowerProtect Data Manager
- inventory_source - Manage inventory sources on PowerProtect Data Manager
- inventory_source_info - Get inventory sources from PowerProtect Data Manager
- storage_system - Update a storage system on PowerProtect Data Manager
- storage_system_info - Get storage systems from PowerProtect Data Manager
