def test_collection_package_is_importable():
    import ansible_collections.fjacquet.ppdm.plugins.module_utils as module_utils

    assert module_utils.__name__ == "ansible_collections.fjacquet.ppdm.plugins.module_utils"
