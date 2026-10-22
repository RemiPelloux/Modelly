"""Unit tests for modelly_logging."""

import logging

import pytest

from modelly import modelly_logging


@pytest.fixture(autouse=True)
def tear_down():
    """Pytest fixture to ensure all logging state is reset after testing."""
    yield
    modelly_logging._logger = None
    modelly_logging._rootlogger = None
    modelly_logger = logging.getLogger(modelly_logging.LOGGER_NAME)
    modelly_logger.handlers = []
    modelly_logger.propagate = True


def test_get_logger():
    """Test get_logger."""
    modelly_logging._rootlogger = None
    logger = modelly_logging.get_rootlogger()
    assert logger == logging.getLogger(modelly_logging.LOGGER_NAME)
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.NullHandler)

    logger = modelly_logging.get_rootlogger()
    assert logger, logging.getLogger(modelly_logging.LOGGER_NAME)
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.NullHandler)


def test_log_to_stderr():
    """Test log_to_stderr."""
    modelly_logging._rootlogger = None
    logger = modelly_logging.log_to_stderr(modelly_logging.DEBUG)
    assert len(logger.handlers) == 2
    assert logger.level == modelly_logging.DEBUG

    modelly_logging._rootlogger = None
    logger = modelly_logging.log_to_stderr()
    assert len(logger.handlers) == 2
    assert logger.level == modelly_logging.DEFAULT_LEVEL

    logger = modelly_logging.log_to_stderr()
    assert len(logger.handlers) == 2
    assert logger.level == modelly_logging.DEFAULT_LEVEL


def test_log_to_stderr_propagation():
    """Test log_to_stderr with propagate parameter."""
    modelly_logging._rootlogger = None
    logger = modelly_logging.log_to_stderr(propagate=True)
    assert logger.propagate is True

    modelly_logging._rootlogger = None
    logger = modelly_logging.log_to_stderr(propagate=False)
    assert logger.propagate is False


def test_caplog_capture_after_teardown(caplog):
    """Verify that logger propagation allows caplog to capture records."""
    logger = modelly_logging.get_module_logger("test_propagation")
    logger.setLevel(logging.INFO)
    logger.info("testing caplog propagation")
    assert "testing caplog propagation" in caplog.text
