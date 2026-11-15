def test_collection_package_is_importable():
    from ansible_collections.fjacquet.ppdm.plugins import module_utils

    assert module_utils.__name__ == "ansible_collections.fjacquet.ppdm.plugins.module_utils"
