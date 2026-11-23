# logging

This provides logging functionality for MODELLY.

It is modeled on the default [logging approach that comes with Python](https://docs.python.org/library/logging.html).

#### `function_logger(name: str) → Callable[[Callable[[...], Any]], Callable[[...], Any]]`

Decorator for adding logging to a Function.

**Parameters:**

**name** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – The name of the module in which the function being decorated is located

#### `get_module_logger(name: str) → Logger`

Helper function for getting the module logger.

**Parameters:**

**name** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – The name of the module in which the method being decorated is located

#### `get_rootlogger() → Logger`

Returns root logger used by MODELLY.

**Returns:**

the root logger of MODELLY

#### `log_to_stderr(level: int | None = None, pass_root_logger_level: bool = False, propagate: bool = False) → Logger`

Turn on logging and add a handler which prints to stderr.

**Parameters:**

- **level** – minimum level of the messages that will be logged
- **pass_root_logger_level** – bool, optional. Default False if True, all module loggers will be set to the same logging level as the root logger.
- **propagate** – bool, optional. Default False if True, all module loggers will continue propagating records to ancestor loggers.

#### `method_logger(name: str) → Callable[[Callable[[...], Any]], Callable[[...], Any]]`

Decorator for adding logging to a method.

**Parameters:**

**name** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – The name of the module in which the method being decorated is located
