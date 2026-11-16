===========================
fjacquet.ppdm Release Notes
===========================

.. contents:: Topics

v1.0.0
======

Release Summary
---------------

First stable release. The modules and playbooks were exercised against a disposable PowerProtect Data Manager 20.3.0 appliance and the bugs found there are fixed. Paths that need a vCenter, a Data Domain or protected data could not be run, the README lists what was validated and what was not.

Minor Changes
-------------

- Add the ``tls_server_name`` connection option (env ``PPDM_TLS_SERVER_NAME``) to verify the PPDM certificate, and send SNI, against a name other than ``hostname``; chain verification stays on.
- protection_rule - new ``filter_template`` option (the ``filterTemplate`` field). PPDM 20.3 builds the rule filters from a template, and for an ``ASSIGN_RESOURCE_GROUP`` rule it requires ``priority`` and ``filters`` to be unset.
- protection_rule_run - new ``all_rules_of_action`` option. PPDM 20.3 answers HTTP 400 when a single ``ASSIGN_PROTECTION_POLICY`` rule is run by ``ruleId``, it only runs every rule of the action. The module now fails before any request unless the option is set, then sends the action without ``ruleId``.

Bugfixes
--------

- Client - a short page without ``page.totalPages`` is now the last page instead of an error, the ``/api/v2/server-disaster-recovery-configurations`` endpoint of PPDM 20.3 sends none (found by running a playbook on a live lab). A full page without ``totalPages`` still fails.
- ensure (every module that updates with PATCH, for example resource_group, protection_rule, protection_group and restore_plan) - the PATCH body now carries the object ``id``, PPDM 20.3 answers HTTP 400 without it (found on a live lab).
- protection_group - a new group gets ``subtype`` ``GENERIC`` when the option is not set, PPDM 20.3 rejects a group without a subtype. An existing group keeps its subtype.
- protection_policy - timestamps such as ``window.startTime`` are compared as instants, PPDM stores ``...00.000Z`` as ``...00Z`` and every re-run reported a change (found on a live lab).

v0.4.0
======

Release Summary
---------------

Adds monitoring and operations modules (activities, alerts, copies, SMTP, users and roles, restore plans, upgrade packages) and three playbooks (66 in total), and fixes waited activities on the v3 statuses. The upgrade and restore modules are service-affecting and untested on a live appliance.

Minor Changes
-------------

- Adds the modules activity_info, activity_action, alert_info, alert_acknowledge, copy_info, smtp_info, smtp, user_info, user, role_info, restore_plan_info, restore_plan, restore_plan_run, upgrade_package_info and upgrade_package_action.
- Adds the playbooks assets.find_assets, protection.create_resource_group and protection.create_protection_group.
- The shared ``ensure`` and ``remove`` helpers handle singleton objects (for example the SMTP configuration) with ``key=None``.
- The shared info helper gains a ``name_key`` argument (the object field the ``name`` option is matched against).

Breaking Changes / Porting Guide
--------------------------------

- certificate - the option ``port`` (TLS port of the host) is renamed ``host_port``. ``port`` now means the PPDM connection port, as in every other module; use ``host_port`` for the TLS port of the host presenting the certificate.

Bugfixes
--------

- certificate - the ``port`` option shadowed the PPDM connection port, so the module connected to PPDM on the TLS port of the host; this is fixed by the ``host_port`` rename.
- discovery, protection_policy_run and protection_rule_run - with ``wait=true`` a finished activity was reported as failed because the v3 statuses ``SUCCESS`` and ``COMPLETED_WITH_EXCEPTIONS`` were not recognised (only the v2 ``OK`` and ``OK_WITH_ERRORS``). Both sets are now accepted.

Known Issues
------------

- user and user_info use the v2 users API (``/api/v2/users``), which PPDM 20.3.0 marks deprecated in favour of ``/api/v3/identity-access-provisions``.

New Modules
-----------

- activity_action - Cancel or retry an activity on PowerProtect Data Manager
- activity_info - Get activities from PowerProtect Data Manager
- alert_acknowledge - Acknowledge or unacknowledge alerts on PowerProtect Data Manager
- alert_info - Get alerts from PowerProtect Data Manager
- copy_info - Get copies (backups) from PowerProtect Data Manager
- restore_plan - Manage restore plans on PowerProtect Data Manager
- restore_plan_info - Get restore plans from PowerProtect Data Manager
- restore_plan_run - Execute a restore plan on PowerProtect Data Manager
- role_info - Get roles from PowerProtect Data Manager
- smtp - Manage the SMTP configuration of PowerProtect Data Manager
- smtp_info - Get the SMTP configuration from PowerProtect Data Manager
- upgrade_package_action - Precheck, install or revert an upgrade package on PowerProtect Data Manager
- upgrade_package_info - Get upgrade packages from PowerProtect Data Manager
- user - Manage local users of PowerProtect Data Manager
- user_info - Get users from PowerProtect Data Manager

v0.3.0
======

Release Summary
---------------

Moves the protection rule modules to the v3 rule API and adds resource group, protection group, asset and host modules.

Minor Changes
-------------

- Adds the modules resource_group, resource_group_info, protection_group, protection_group_info, asset_info and host_info.
- asset_info omits the top-level ``credentials`` field of the assets it returns; host_info omits nothing.

Breaking Changes / Porting Guide
--------------------------------

- kubernetes.add_policy_and_rule playbook - now creates or updates the rule (before, it only created it when missing) and runs only that rule (before, all Kubernetes rules). The ``protection.create_rule`` and ``protection.run_rule`` playbook variables changed accordingly.
- protection_rule - now uses the v3 rule API. The options ``conditions`` and ``condition_connector`` are replaced by ``filters`` (the object subtype goes in ``filters[].objectSubtype``, there is no ``object_subtypes`` option), ``tenant`` is removed, ``policy`` is replaced by ``action`` plus ``protection_policy`` (or ``protection_policy_id``), and ``action`` lost ``MOVE_TO_GROUP`` and takes the v3 action names. New options are ``variant``, ``scopes``, ``categories``, ``resource_group`` and ``resource_group_id``.
- protection_rule and protection_rule_info - the returned objects (``protection_rule``, ``protection_rules``) now have the v3 shape, for example ``action`` is a dict instead of a string, and ``inventorySourceType`` and ``conditions`` are gone.
- protection_rule_run - ``rule`` keeps its name but is now a required rule name or id (a string), no longer a ProtectionRule dict (the preview body). The module runs one rule per call, the old ``rules`` list ran several rules or all rules of an inventory source type. ``inventory_source_type`` is replaced by ``object_subtypes``, and ``preview_action`` is removed (``action_name`` is the run action, the preview ignores it).

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
