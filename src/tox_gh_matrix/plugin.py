import json
import os
import pathlib
import re
import uuid
from typing import Dict, Iterable, List

import pluggy
import tox.config
from tox import reporter as report
from tox.exception import ConfigError, MissingDependency
from tox.interpreters import InterpreterInfo

from .version_utils import (
    basepython_to_gh_python_version,
    interpreter_info_to_version,
    python_version_to_prerelease_spec,
)

hookimpl = pluggy.HookimplMarker("tox")


@hookimpl
def tox_addoption(parser):
    parser.add_argument(
        "--gh-matrix",
        action="store",
        nargs="?",
        const="envlist",
        metavar="VAR",
        help="set GitHub workflow output %(metavar)s (default: '%(const)s') to workflow matrix",
    )
    parser.add_argument(
        "--gh-matrix-dump",
        action="store_true",
        help="output JSON formatted GitHub workflow matrix",
    )


@hookimpl(trylast=True)
def tox_configure(config: tox.config.Config):
    # Tox's --showconfig and --list (showenvs) options are handled as special
    # cases in tox.session.Session.runcommand, but it's unclear how a plugin
    # could add to or override runcommand. Instead, just hook in here (after
    # parsing config, but before the session runs) and exit early. (This is
    # roughly how --version is handled in tox.config.parse_cli.)
    if config.option.gh_matrix or config.option.gh_matrix_dump:
        matrix = tox_config_to_gh_matrix(config)
        if config.option.gh_matrix_dump:
            # Dump formatted json (useful for debugging).
            report.line(json.dumps(matrix, indent=2))
        if config.option.gh_matrix:
            # Set a GitHub workflow output parameter.
            set_gh_output(config.option.gh_matrix, json.dumps(matrix))
        # Exit without executing any tox environments.
        raise SystemExit(0)


def tox_config_to_gh_matrix(config: tox.config.Config) -> List[Dict]:
    """Construct a GitHub workflow matrix from a tox config"""
    try:
        envlist: Iterable[str] = config.envlist
    except AttributeError:  # pragma: no cover
        raise ConfigError(
            "tox-gh-matrix is not compatible with this version of tox (missing Config.envlist)"
        )

    # Filter out explicitly-requested-but-not-available envnames.
    envlist = [name for name in envlist if name in config.envconfigs]

    # Duplicate TOX_SKIP_ENV logic from tox.session.Session._evaluated_env_list,
    # because tox (as of at least 3.24) doesn't process that until after config,
    # during actual test session initialization.
    tox_env_filter = os.environ.get("TOX_SKIP_ENV")
    if tox_env_filter is not None:
        tox_env_filter_re = re.compile(tox_env_filter)
        envlist = [name for name in envlist if not tox_env_filter_re.match(name)]

    return [tox_testenv_to_gh_config(config.envconfigs[name]) for name in envlist]


def tox_testenv_to_gh_config(env: tox.config.TestenvConfig) -> Dict:
    """Construct a GitHub workflow matrix item from a tox TestenvConfig"""
    gh_config = {
        "name": env.envname,
        # Converting set env.factors to a list doesn't result
        # in consistent ordering, so just re-split the envname.
        # "factors": list(env.factors),
        "factors": env.envname.split("-"),
    }

    try:
        basepython = env.basepython
    except AttributeError:  # pragma: no cover
        raise ConfigError(
            "tox-gh-matrix is not compatible with this version of tox"
            " (missing TestenvConfig.basepython)"
        )

    python = basepython_to_gh_python_version(basepython)
    if python:
        gh_config["python"] = {
            "version": python,
            "spec": python_version_to_prerelease_spec(python),
        }
        if isinstance(env.python_info, InterpreterInfo):
            # Some version of basepython is installed on this system.
            gh_config["python"]["installed"] = interpreter_info_to_version(env.python_info)

    if env.ignore_outcome:
        gh_config["ignore_outcome"] = env.ignore_outcome
    return gh_config


def set_gh_output(name: str, value: str):
    """Append an output parameter to the GITHUB_OUTPUT file"""
    gh_output = os.getenv("GITHUB_OUTPUT")
    if not gh_output:
        raise MissingDependency("GITHUB_OUTPUT environment variable not set")

    if "\n" in value:
        # Use multiline syntax, with a random terminator
        eof = f"EOF-{uuid.uuid4()}"
        encoded = f"{name}<<{eof}\n{value}\n{eof}\n"
    else:
        encoded = f"{name}={value}\n"

    with pathlib.Path(gh_output).open("a") as f:
        f.write(encoded)
