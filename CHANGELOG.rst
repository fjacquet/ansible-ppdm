===========================
fjacquet.ppdm Release Notes
===========================

.. contents:: Topics

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
