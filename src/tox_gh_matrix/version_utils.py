import re
import sys

from tox.interpreters import InterpreterInfo

# tox sets TestenvConfig.basepython to sys.executable
# if the testenv doesn't ask for something more specific.
TOX_DEFAULT_BASEPYTHON = sys.executable


def basepython_to_gh_python_version(basepython: str) -> str:
    """
    Map a tox TestenvConfig basepython string to a
    GitHub actions/setup-python python-version string.

    E.g.: "python3.10" --> "3.10" or "pypy3.8" --> "pypy-3.8"
    """
    # (See `basepython_default` in tox.config for potential values
    # of basepython, from tox factors like py310 or pypy38.)
    # ??? Maybe use tox.interpreters.py_spec.PythonSpec.from_name instead?
    if basepython == TOX_DEFAULT_BASEPYTHON:
        return ""

    match = re.fullmatch(r"(python|pypy|jython)(\d+(\.\d+)?)?", basepython)
    if not match:
        raise ValueError(f"Unexpected basepython format {basepython!r}")

    implementation = match[1]
    version = match[2] or ""
    if implementation == "python":
        return version
    elif version:
        return f"{implementation}-{version}"
    else:
        return implementation


def python_version_to_prerelease_spec(python: str) -> str:
    """
    Expand a python-version string to allow prerelease Python,
    using SemVer ranges. (Doesn't currently handle pypy.)

    >>> python_version_to_prerelease_spec("3.7")
    '3.7.0-alpha - 3.7'

    Only handles tox-factor-generated N.M versions
    (not N and not N.M.P):
    >>> python_version_to_prerelease_spec("3")
    '3'
    >>> python_version_to_prerelease_spec("3.5.7")
    '3.5.7'
    """
    match = re.fullmatch(r"^(|pypy-|jython-)(\d+\.\d+)$", python)
    if match:
        implementation = match[1]
        version = match[2]
        if implementation == "":
            python = f"{implementation}{version}.0-alpha - {version}"
    return python


def interpreter_info_to_version(python_info: InterpreterInfo) -> str:
    """Format a GH python-version string from tox InterpreterInfo"""
    version = format_version_info(python_info.version_info)
    if python_info.extra_version_info:
        extra_version = format_version_info(python_info.extra_version_info)
        version = f"{version}-{extra_version}"
    implementation = python_info.implementation.lower()
    if implementation != "cpython":
        version = f"{implementation}-{version}"
    return version


def format_version_info(version_info: (int, int, int, str, int)) -> str:
    """Format a sys.version_info-style Python version tuple to a string"""
    (major, minor, micro, releaselevel, serial) = version_info
    version = f"{major}.{minor}.{micro}"
    if releaselevel != "final" or serial != 0:
        version += f"-{releaselevel}.{serial}"
    return version
