# Fixtures for our integration tests.
import re
import uuid
from pathlib import Path
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
def mock_interpreter(monkeypatch, ignore_extra_kwargs):
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

        # (InterpreterInfo constructor has changed required kwargs
        # over time, in ways which aren't relevant to this plugin.)
        interpreter_infos[name] = ignore_extra_kwargs(
            InterpreterInfo,
            implementation=implementation,
            executable=f"/mock_interpreter/{name}/python",
            version_info=version_info,
            sysplatform=platform if platform is not None else "linux",
            is_64=True,
            os_sep={"win32": "\\"}.get(platform, "/"),
            extra_version_info=extra_version_info,
        )

    yield install


def parse_github_action_envfile(content: str) -> dict:
    """
    Return a dict of variables parsed from a GitHub action
    environment/output/state file body. Handles single line
    and multiline variable formats.
    """
    items = {}
    for match in re.finditer(
        # name=value | name<<EOF\nvalue...\n...\nEOF
        r"(^(?P<sname>\w+)=(?P<svalue>.*)\n)"
        r"|"
        r"(^(?P<mname>\w+)<<(?P<eof>.*)\n(?P<mvalue>(?s:.*))^(?P=eof)\n)",
        content,
        re.MULTILINE,
    ):
        if match["sname"]:
            items[match["sname"]] = match["svalue"]
        elif match["mname"]:
            items[match["mname"]] = match["mvalue"]
        else:
            raise ValueError("Unexpected match object")
    return items


@pytest.fixture
def github_output(tmp_path, monkeypatch):
    """
    Fixture that implements a GITHUB_OUTPUT file as described in
    https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#setting-an-output-parameter
    """
    output_path = tmp_path / f"github-output{uuid.uuid4()}.env"
    output_path.touch()
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))

    class ActionEnvFile(dict):
        def __init__(self, path: Path):
            self.path = path
            self.content = path.read_text(encoding="utf-8")
            parsed = parse_github_action_envfile(self.content)
            super().__init__(parsed)

    def read_output():
        return ActionEnvFile(output_path)

    yield read_output
