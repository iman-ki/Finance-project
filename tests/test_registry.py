import pytest

from qrp.core.registry import Registry


def test_register_and_get():
    reg = Registry("thing")

    @reg.register("a")
    class A:
        pass

    assert reg.get("a") is A
    assert reg.names() == ["a"]


def test_duplicate_name_rejected():
    reg = Registry("thing")

    @reg.register("a")
    class A:
        pass

    with pytest.raises(ValueError):

        @reg.register("a")
        class B:
            pass


def test_unknown_name_lists_available():
    reg = Registry("thing")
    with pytest.raises(KeyError, match="unknown thing 'x'"):
        reg.get("x")
