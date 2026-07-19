import os

import pytest


@pytest.mark.skipif(
    os.environ.get("LOOPFLOW_INJECT_GATE_FAILURE") != "1",
    reason="only enabled while proving that the MR gate rejects failures",
)
def test_intentional_gate_failure():
    pytest.fail("intentional MR gate failure fixture")
