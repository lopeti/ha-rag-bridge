import os
from ha_rag_bridge.utils.env import env_true


def test_env_true():
    os.environ["FLAG"] = "1"
    assert env_true("FLAG")
    os.environ["FLAG"] = "yes"
    assert env_true("FLAG")
    os.environ["FLAG"] = "False"
    assert not env_true("FLAG")
    del os.environ["FLAG"]
    assert env_true("FLAG", True)
