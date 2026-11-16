from ansible_collections.fjacquet.ppdm.plugins.module_utils.ppdm import is_subset


def test_subset_basics():
    assert is_subset({"a": 1}, {"a": 1, "b": 2})
    assert not is_subset({"a": 1}, {"a": 2})
    assert not is_subset([1], [1, 2])


def test_same_instant_with_or_without_milliseconds():
    # PPDM stores 2026-01-01T20:00:00.000Z as 2026-01-01T20:00:00Z (seen on a live lab)
    assert is_subset({"startTime": "2026-01-01T20:00:00.000Z"}, {"startTime": "2026-01-01T20:00:00Z"})


def test_different_instants_and_non_timestamps_differ():
    assert not is_subset("2026-01-01T20:00:00Z", "2026-01-01T21:00:00Z")
    assert not is_subset("Tuesday", "Thursday")
    assert not is_subset("2026-01-01T20:00:00", "2026-01-01T20:00:00Z")  # naive against aware: never equal
