===========================
fjacquet.ppdm Release Notes
===========================

.. contents:: Topics

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
