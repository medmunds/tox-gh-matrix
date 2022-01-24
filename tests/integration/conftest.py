# Fixtures for our integration tests.

from typing import Dict, Tuple

import pytest
from tox.interpreters import InterpreterInfo, Interpreters, NoInterpreterInfo
from tox.interpreters.py_spec import PythonSpec


@pytest.fixture
def tox_ini(initproj):
    """
    Initialize a project with a tox.ini having the given contents.

    def test_tox_something(tox_ini, cmd):
        tox_ini("[tox]\nenvlist=py{27,34}\n")
        result = cmd("-l")
    """

    def init(contents):
        initproj("pkg123-0.7", filedefs={"tox.ini": contents})

    yield init


@pytest.fixture
def mock_interpreter(monkeypatch):
    """
    Override the Python interpreters that tox discovers.

    Merely including this fixture in a test will prevent tox from finding
    any system interpreters. Call mock_interpreter to "install" each
    desired interpreter. (The resulting interpreters aren't real,
    so can't be used to execute a testenv.)

    def test_tox_thing(cmd, mock_interpreter):
        # If run at this point, cmd() won't find _any_) Python interpreters.
        mock_interpreter("python3.5")
        # Now cmd() will find CPython 3.5.0-final.0, only.
        mock_interpreter("python3.6", version_info=(3, 6, 2, 'alpha', 1))
        # Now cmd() will _also_ find CPython 3.6.2-alpha.1.
        mock_interpreter("pypy3.8", extra_version=(3, 7, 0, 'final', 0)).
        # Now cmd() will _also_ find PyPy 3.8.0-final.0-3.7.0.final.0
    """

    # basepython --> InterpreterInfo
    interpreter_infos: Dict[str, InterpreterInfo] = {}

    def mock_get_info(_self, envconfig):
        name = envconfig.basepython
        try:
            return interpreter_infos[name]
        except KeyError:
            return NoInterpreterInfo(name=name)

    monkeypatch.setattr(Interpreters, "get_info", mock_get_info)

    def mock_get_executable(_self, envconfig):
        name = envconfig.basepython
        try:
            return interpreter_infos[name].executable
        except KeyError:
            return None

    monkeypatch.setattr(Interpreters, "get_executable", mock_get_executable)

    def install(
        name: str,
        *,
        version_info: Tuple[int, int, int, str, int] = None,
        extra_version_info: Tuple[int, int, int, str, int] = None,
        platform=None,
    ):
        spec = PythonSpec.from_name(name)
        if version_info is None:
            version_info = (spec.major, spec.minor, 0, "final", 0)
        if version_info[:2] != (spec.major, spec.minor):
            raise ValueError(f"{name} couldn't have version_info={version_info!r}")

        implementation = {
            "python": "CPython",
            "pypy": "PyPy",
            "jython": "Jython",
            "ipython": "IronPython",
        }.get(spec.name, spec.name)

        if extra_version_info is None and implementation == "PyPy":
            # PyPy always has extra_version_info.
            extra_version_info = (3, 7, 0, "final", 0)

        interpreter_infos[name] = InterpreterInfo(
            implementation=implementation,
            executable=f"/mock_interpreter/{name}/python",
            version_info=version_info,
            sysplatform=platform if platform is not None else "linux",
            is_64=True,
            os_sep={"win32": "\\"}.get(platform, "/"),
            extra_version_info=extra_version_info,
        )

    yield install
