import re
import sys

import pytest
from tox.interpreters import InterpreterInfo

from tox_gh_matrix.version_utils import (
    basepython_to_gh_python_version,
    format_version_info,
    interpreter_info_to_version,
    python_version_to_prerelease_spec,
)


@pytest.mark.parametrize(
    "basepython,expected",
    [
        ("python3.8", "3.8"),
        ("python3.10", "3.10"),
        ("python2.7", "2.7"),
        ("pypy3.6", "pypy-3.6"),
        ("jython3.5", "jython-3.5"),
        ("python", ""),
        ("pypy", "pypy"),
        ("pypy3", "pypy-3"),
        (sys.executable, ""),  # tox default basepython
    ],
)
def test_basepython_to_python_version(basepython, expected):
    assert basepython_to_gh_python_version(basepython) == expected


@pytest.mark.parametrize(
    "basepython",
    [
        "python3.5.1",  # only N.M version supported
        "pypy3.7.10",  # only N.M version supported
        "/my/custom/python",  # non-sys.executable absolute path
    ],
)
def test_basepython_to_python_version_invalid(basepython):
    expected_error = rf"Unexpected basepython format {re.escape(repr(basepython))}"
    with pytest.raises(ValueError, match=expected_error):
        basepython_to_gh_python_version(basepython)


@pytest.mark.parametrize(
    "python,expected",
    [
        ("3.7", "3.7.0-alpha - 3.7"),
        # Unclear how to specify pypy range, so don't:
        ("pypy-3.7", "pypy-3.7"),
        # These forms aren't currently handled:
        ("", ""),
        ("3", "3"),
        ("3.7.3", "3.7.3"),
    ],
)
def test_python_version_to_prerelease_spec(python, expected):
    assert python_version_to_prerelease_spec(python) == expected


@pytest.mark.parametrize(
    "implementation,version_info,extra_version_info,expected",
    [
        ("CPython", (2, 7, 12, "final", 0), None, "2.7.12"),
        ("CPython", (3, 11, 0, "alpha", 0), None, "3.11.0-alpha.0"),
        ("PyPy", (3, 8, 6, "final", 0), (3, 7, 0, "final", 0), "pypy-3.8.6-3.7.0"),
        ("Jython", (3, 4, 8, "final", 0), None, "jython-3.4.8"),
    ],
)
def test_interpreter_info_to_version(
    implementation, version_info, extra_version_info, expected, ignore_extra_kwargs
):
    # (InterpreterInfo constructor has changed required kwargs
    # over time, in ways which aren't relevant to this plugin.)
    interpreter_info = ignore_extra_kwargs(
        InterpreterInfo,
        implementation=implementation,
        executable="n/a for this test",
        version_info=version_info,
        sysplatform="n/a for this test",
        is_64=False,  # n/a for this test
        os_sep="/",  # n/a for this test
        extra_version_info=extra_version_info,
    )
    assert interpreter_info_to_version(interpreter_info) == expected


@pytest.mark.parametrize(
    "info,expected",
    [
        ((2, 7, 12, "final", 0), "2.7.12"),
        ((3, 10, 4, "alpha", 0), "3.10.4-alpha.0"),
        ((3, 10, 4, "final", 3), "3.10.4-final.3"),
        ((3, 11, 0, "final", 0), "3.11.0"),
    ],
)
def test_format_version_info(info, expected):
    assert format_version_info(info) == expected
