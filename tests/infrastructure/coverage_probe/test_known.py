from tests.infrastructure.coverage_probe.known import classify


def test_nonnegative_branch():
    assert classify(0) == "nonnegative"


def test_negative_branch():
    assert classify(-1) == "negative"
