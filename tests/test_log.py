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
