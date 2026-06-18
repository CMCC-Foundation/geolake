import logging

from meta import LoggableMeta


def test_loggable_meta_configures_logger(monkeypatch):
    monkeypatch.setenv("LOGGING_LEVEL", "DEBUG")

    class Foo(metaclass=LoggableMeta):
        _LOG = logging.getLogger("test.loggable.foo")

    assert Foo._LOG.level == logging.DEBUG
    assert Foo._LOG.handlers  # almeno un handler agganciato


def test_loggable_meta_without_log_attr_does_not_raise():
    class Bar(metaclass=LoggableMeta):
        pass

    assert Bar is not None
