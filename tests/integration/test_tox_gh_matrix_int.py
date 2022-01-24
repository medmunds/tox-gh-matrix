import json
import re
from textwrap import dedent


def parse_gh_output(result):
    """Extract a dict of GitHub Workflow set-output variables from result's output"""
    matches = re.findall(r"::set-output\s+name=(\w+)::(.*)\n", result.out)
    if matches is None:
        return dict()
    return dict(matches)


def test_gh_matrix(tox_ini, cmd, mock_interpreter):
    tox_ini(
        """
            [tox]
            envlist = django{32,40}-py{38,39},docs
        """
    )
    result = cmd("--gh-matrix")
    result.assert_success(is_run_test_env=False)
    gh_output = parse_gh_output(result)
    assert "toxenvs" in gh_output  # default output name
    toxenvs = json.loads(gh_output["toxenvs"])
    assert toxenvs == [
        {
            "name": "django32-py38",
            "factors": ["django32", "py38"],
            "python": {"version": "3.8", "spec": "3.8.0-alpha - 3.8"},
        },
        {
            "name": "django32-py39",
            "factors": ["django32", "py39"],
            "python": {"version": "3.9", "spec": "3.9.0-alpha - 3.9"},
        },
        {
            "name": "django40-py38",
            "factors": ["django40", "py38"],
            "python": {"version": "3.8", "spec": "3.8.0-alpha - 3.8"},
        },
        {
            "name": "django40-py39",
            "factors": ["django40", "py39"],
            "python": {"version": "3.9", "spec": "3.9.0-alpha - 3.9"},
        },
        {
            "name": "docs",
            "factors": ["docs"],
            # no python version specified
        },
    ]


def test_custom_var(tox_ini, cmd):
    """--gh-matrix takes optional output variable name"""
    tox_ini(
        """
            [tox]
            envlist = lint,test
        """
    )
    result = cmd("--gh-matrix=myvarname")
    result.assert_success(is_run_test_env=False)
    gh_output = parse_gh_output(result)
    assert "myvarname" in gh_output
    assert "toxenvs" not in gh_output  # default not set
    toxenvs = json.loads(gh_output["myvarname"])
    assert toxenvs == [
        {"name": "lint", "factors": ["lint"]},
        {"name": "test", "factors": ["test"]},
    ]


def test_installed_python(tox_ini, cmd, mock_interpreter):
    """--gh-matrix provides 'python_installed' versions for available interpreters"""
    mock_interpreter("python3.5", version_info=(3, 5, 6, "final", 0))
    mock_interpreter("python3.10")
    mock_interpreter("pypy3.8")
    tox_ini(
        """
            [tox]
            envlist = py{27,35,310},pypy38
        """
    )
    result = cmd("--gh-matrix")
    result.assert_success(is_run_test_env=False)
    gh_output = parse_gh_output(result)
    toxenvs = json.loads(gh_output["toxenvs"])
    assert toxenvs == [
        {
            "name": "py27",
            "factors": ["py27"],
            "python": {"version": "2.7", "spec": "2.7.0-alpha - 2.7"},
        },
        {
            "name": "py35",
            "factors": ["py35"],
            "python": {"version": "3.5", "spec": "3.5.0-alpha - 3.5", "installed": "3.5.6"},
        },
        {
            "name": "py310",
            "factors": ["py310"],
            "python": {
                "version": "3.10",
                "spec": "3.10.0-alpha - 3.10",
                "installed": "3.10.0",
            },
        },
        {
            "name": "pypy38",
            "factors": ["pypy38"],
            "python": {
                "version": "pypy-3.8",
                "spec": "pypy-3.8",
                "installed": "pypy-3.8.0-3.7.0",
            },
        },
    ]


def test_base_python(tox_ini, cmd, mock_interpreter):
    """Python version can come from an env's basepython"""
    tox_ini(
        """
            [tox]
            envlist = check,build
            [testenv:build]
            basepython = python3.9
        """
    )
    result = cmd("--gh-matrix")
    result.assert_success(is_run_test_env=False)
    gh_output = parse_gh_output(result)
    toxenvs = json.loads(gh_output["toxenvs"])
    assert toxenvs == [
        {"name": "check", "factors": ["check"]},
        {
            "name": "build",
            "factors": ["build"],
            "python": {"version": "3.9", "spec": "3.9.0-alpha - 3.9"},
        },
    ]


def test_ignore_outcome(tox_ini, cmd):
    """--gh-matrix identifies tox envs with ignore_outcome set"""
    tox_ini(
        """
            [tox]
            envlist = release,dev
            [testenv:dev]
            ignore_outcome = true
        """
    )
    result = cmd("--gh-matrix")
    result.assert_success(is_run_test_env=False)
    gh_output = parse_gh_output(result)
    toxenvs = json.loads(gh_output["toxenvs"])
    assert toxenvs == [
        {"name": "release", "factors": ["release"]},
        {"name": "dev", "factors": ["dev"], "ignore_outcome": True},
    ]


def test_limited_envlist(tox_ini, cmd):
    """Explicit -e envlist limits --gh-matrix output"""
    tox_ini(
        """
            [tox]
            envlist = py{27,35,36,37,38,39,310}
        """
    )
    result = cmd("--gh-matrix", "-e", "py35,py39,unknown-env")
    result.assert_success(is_run_test_env=False)
    gh_output = parse_gh_output(result)
    assert "toxenvs" in gh_output
    toxenvs = json.loads(gh_output["toxenvs"])
    envnames = [env["name"] for env in toxenvs]
    assert envnames == ["py35", "py39"]
    assert "unknown-env" not in envnames


def test_skip_env(tox_ini, cmd, monkeypatch):
    """--gh-matrix filters out matches for TOX_SKIPENV"""
    tox_ini(
        """
            [tox]
            envlist = py{38,39}-{unix,win,mac}
        """
    )
    # TOX_SKIPENV is a Python regular expression that must match
    # the _entire_ envname to remove that env.
    monkeypatch.setenv("TOX_SKIP_ENV", ".*-(unix|mac)")
    result = cmd("--gh-matrix")
    result.assert_success(is_run_test_env=False)
    gh_output = parse_gh_output(result)
    toxenvs = json.loads(gh_output["toxenvs"])
    envnames = [env["name"] for env in toxenvs]
    assert envnames == ["py38-win", "py39-win"]


def test_matrix_dump(tox_ini, cmd, mock_interpreter):
    tox_ini(
        """
            [tox]
            envlist = lint,test
        """
    )
    result = cmd("--gh-matrix-dump")
    result.assert_success(is_run_test_env=False)
    # Formatted JSON output:
    expected = dedent(
        """
            [
              {
                "name": "lint",
                "factors": [
                  "lint"
                ]
              },
              {
                "name": "test",
                "factors": [
                  "test"
                ]
              }
            ]
        """
    )
    assert result.out.strip() == expected.strip()
