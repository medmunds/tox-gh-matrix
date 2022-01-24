import inspect
from typing import Callable

import pytest

pytest_plugins = "tox._pytestplugin"


KWARG_PARAM_TYPES = (
    inspect.Parameter.KEYWORD_ONLY,
    inspect.Parameter.POSITIONAL_OR_KEYWORD,
)


@pytest.fixture
def ignore_extra_kwargs():
    """
    Calls `func` with the kwargs that are supported by func,
    stripping away any that are not.

    Useful for test cases that need to call a function or
    construct a class instance whose kwargs have changed
    over time. (And where the kwargs that changed are not
    relevant to the test.)

    Will also pass along any positional args. (But can't
    account for changes to them over time.)

    def test_something(ignore_extra_kwargs):
        result = ignore_extra_kwargs(
            ConstructorWhoseSignatureHasChanged,
            arg="something",
            arg_that_was_added_recently="something else")
    """

    def _call(_func: Callable, *args, **kwargs):
        sig = inspect.signature(_func)
        supported_kwargs = {
            param: value
            for param, value in kwargs.items()
            if param in sig.parameters and sig.parameters[param].kind in KWARG_PARAM_TYPES
        }
        return _func(*args, **supported_kwargs)

    yield _call
