# Random numbers

`model.random` is a `FastRandom`: a `random.Random` that gives exactly the standard library's
numbers for a seed, faster. When the compiled core is built for the interpreter (platform
wheels for Linux and macOS, or `bash scripts/build-native.sh` in a checkout), `randint`,
`choice`, `shuffle`, `sample` and `_randbelow` run in C on CPython's own Mersenne Twister state;
otherwise `FastRandom` is `PyFastRandom`, the pure-Python version. `modelly.rng.NATIVE` says
which one is in use, and `MODELLY_PURE_PYTHON=1` forces the Python one.

```{eval-rst}
.. automodule:: modelly.rng
   :members: FastRandom, PyFastRandom, NATIVE
```
