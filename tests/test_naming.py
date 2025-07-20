import pytest

from ha_rag_bridge.bootstrap import naming


@pytest.mark.parametrize(
    "name,exp",
    [
        ("", False),
        ("123", False),
        ("_foo", False),
        ("valid", True),
    ],
)
def test_is_valid(name, exp):
    assert naming.is_valid(name) is exp
