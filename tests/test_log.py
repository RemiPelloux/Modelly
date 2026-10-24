"""Unit tests for log."""

import logging

import pytest

from modelly import log


@pytest.fixture(autouse=True)
def tear_down():
    """Pytest fixture to ensure all logging state is reset after testing."""
    yield
    log._logger = None
    log._rootlogger = None
    modelly_logger = logging.getLogger(log.LOGGER_NAME)
    modelly_logger.handlers = []
    modelly_logger.propagate = True


def test_get_logger():
    """Test get_logger."""
    log._rootlogger = None
    logger = log.get_rootlogger()
    assert logger == logging.getLogger(log.LOGGER_NAME)
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.NullHandler)

    logger = log.get_rootlogger()
    assert logger, logging.getLogger(log.LOGGER_NAME)
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.NullHandler)


def test_log_to_stderr():
    """Test log_to_stderr."""
    log._rootlogger = None
    logger = log.log_to_stderr(log.DEBUG)
    assert len(logger.handlers) == 2
    assert logger.level == log.DEBUG

    log._rootlogger = None
    logger = log.log_to_stderr()
    assert len(logger.handlers) == 2
    assert logger.level == log.DEFAULT_LEVEL

    logger = log.log_to_stderr()
    assert len(logger.handlers) == 2
    assert logger.level == log.DEFAULT_LEVEL


def test_log_to_stderr_propagation():
    """Test log_to_stderr with propagate parameter."""
    log._rootlogger = None
    logger = log.log_to_stderr(propagate=True)
    assert logger.propagate is True

    log._rootlogger = None
    logger = log.log_to_stderr(propagate=False)
    assert logger.propagate is False


def test_caplog_capture_after_teardown(caplog):
    """Verify that logger propagation allows caplog to capture records."""
    logger = log.get_module_logger("test_propagation")
    logger.setLevel(logging.INFO)
    logger.info("testing caplog propagation")
    assert "testing caplog propagation" in caplog.text


def test_create_module_logger_defaults_to_caller_module():
    """Without a name, the logger is named after the calling module."""
    logger = log.create_module_logger()
    assert logger.name == f"{log.LOGGER_NAME}.{__name__}"
    assert log.get_module_logger(__name__) is logger


def test_method_logger_names_the_enclosing_class(caplog):
    """method_logger picks up the class it is applied in."""

    class Greeter:
        @log.method_logger(__name__)
        def greet(self, who):
            return f"hi {who}"

    with caplog.at_level(logging.DEBUG, logger=log.LOGGER_NAME):
        assert Greeter().greet("you") == "hi you"
    assert "calling Greeter.greet with ('you',) and {}" in caplog.text
