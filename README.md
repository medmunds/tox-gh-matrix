# tox-gh-matrix

A [tox][] plugin that generates a JSON version of your tox.ini envlist,
which can be used in a GitHub workflow [build matrix][build-matrix]
(or potentially with other CI systems).

[![Latest version on PyPi](https://img.shields.io/pypi/v/tox-gh-matrix.svg)][pypi-release]
[![Build status](https://github.com/medmunds/tox-gh-matrix/workflows/test/badge.svg?branch=main)][build-status]

This plugin is useful when:
* Your tox.ini envlist covers a complex set of factors
  (e.g., all supported combinations of Django and Python versions).
* You use GitHub actions and want to run each tox testenv
  in a separate workflow job, so that tests run in parallel and so
  GitHub's actions log breaks out the result for each testenv.
* You're tired of manually syncing your workflow build matrix and
  your tox.ini envlist.

tox-gh-matrix adds a new `tox --gh-matrix` command line option that
outputs a JSON representation of your tox envlist:

```json5
[
  {
    "name": "py35-django22",
    "factors":  ["py35", "django22"],
    "python": { "version": "3.5", "spec": "3.5.0-alpha - 3.5" }
  },
  {
    "name": "py36-django22",
    "factors":  ["py36", "django22"],
    "python": { "version": "3.6", "spec": "3.6.0-alpha - 3.6" }
  },
  // ...
  {
    "name": "py310-django40",
    "factors":  ["py310", "django40"],
    "python": { "version": "3.10", "spec": "3.10.0-alpha - 3.10", "installed": "3.10.2" }
  },
  {
    "name": "py311-django40",
    "factors":  ["py311", "django40"],
    "python": { "version": "3.11", "spec": "3.11.0-alpha - 3.11" },
    "ignore_outcome": true
  },
  // ...
  { "name": "docs", "factors": ["docs"] },
  { "name": "lint", "factors": ["lint"] }
]
```

Your workflow can use this to define a build matrix from the tox envlist:

```yaml
jobs:
  get-envlist:
    outputs:
      envlist: ${{ steps.generate-envlist.outputs.envlist }}
    steps:
      # ... (details omitted; see complete example below)
      - id: generate-envlist
        run: python -m tox --gh-matrix

  test:
    needs: get-envlist
    strategy:
      matrix:
        tox: ${{ fromJSON(needs.get-envlist.outputs.envlist) }}
    steps:
      # ... (details omitted; see complete example below)
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.tox.python.spec }}
      - run: python -m tox -e ${{ matrix.tox.name }}
```

See the [usage](#usage) section below for a complete annotated example
and other variations.


## Contents

* [Usage](#usage)
  * [Complete example](#complete-example)
  * [Installation](#installation)
  * [Handling ignore outcome](#handling-ignore-outcome)
  * [Using setup-python](#using-setup-python)
  * [Testing PyPy and older Python versions](#testing-pypy-and-older-python-versions)
  * [Filtering the tox envlist](#filtering-the-tox-envlist)
  * [Examining tox factors](#examining-tox-factors)
  * [Matrix output names and multiple envlists](#matrix-output-names-and-multiple-envlists)
  * [Additional build matrix dimensions](#additional-build-matrix-dimensions)
  * [Debugging the matrix](#debugging-the-matrix)
* [Contributing, issues, help](#contributing-issues-help)
* [Similar projects](#similar-projects)
* [License](#license)


## Usage

The basic approach to running GitHub workflow jobs based on
your tox envlist is:

1. Run `tox --gh-matrix` in a preliminary job, to generate a
   JSON version of your tox envlist.

2. In your main test job, define a workflow [build matrix][build-matrix]
   property that iterates that list, using [`fromJSON()`][expression-fromJSON].


### Complete example

Here's a complete, annotated example workflow:

```yaml
name: test
on: push
jobs:
  # First, use tox-gh-matrix to construct a build matrix
  # from your tox.ini:
  get-envlist:
    runs-on: ubuntu-latest
    # Make the JSON envlist available to the test job:
    outputs:
      envlist: ${{ steps.generate-envlist.outputs.envlist }}
    steps:
      # Checkout project code to get tox.ini:
      - uses: actions/checkout@v3
      # Install tox and tox-gh-matrix:
      - run: python -m pip install tox tox-gh-matrix
      # Run `tox --gh-matrix` to generate the JSON list:
      - id: generate-envlist
        run: python -m tox --gh-matrix

  # Now run your tests using that matrix:
  test:
    # Pull in the JSON generated in the previous job:
    needs: get-envlist
    strategy:
      # Define a build matrix property `tox` that iterates
      # the envlist:
      matrix:
        tox: ${{ fromJSON(needs.get-envlist.outputs.envlist) }}
      # Run all matrix jobs, even if some fail:
      fail-fast: false
    # The workflow treats everything below as a template
    # to run a separate job for each build matrix item.
    name: Test ${{ matrix.tox.name }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      # Install the required Python version if necessary:
      - name: Setup Python ${{ matrix.tox.python.version }}
        if: matrix.tox.python.spec && ! matrix.tox.python.installed
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.tox.python.spec }}
      # Install tox (you don't need tox-gh-matrix at this point):
      - run: python -m pip install tox
      # Run `tox -e {name}` to test the single tox environment
      # for this matrix entry:
      - run: python -m tox -e ${{ matrix.tox.name }}
```

Some other variations are covered below. Also, see this project's
own [workflow definition](./.github/workflows/test.yml).


### Installation

Install tox-gh-matrix from PyPI using pip:

`python -m pip install tox-gh-matrix`

(Typically you'd do this in a GitHub workflow as shown above,
but that's not required. You can run tox-gh-matrix in your local
development environment to examine its output.)

tox-gh-matrix requires Python 3.6 or later and tox 3.5.12 or later.
(It is not currently compatible with tox 4 alpha.)

The minimum Python version only applies to running the `tox --gh-matrix`
command itself. (tox can generate virtual environments with *any* version
of Python to run your tests.)


### Handling ignore outcome

If you use tox's [`ignore_outcome`][ignore-outcome] setting to
allow failures in certain testenvs, those jobs will always appear
successful in GitHub's actions log.

You may prefer to hoist the failure handling up to the workflow level,
so you can see which environments have failed in the actions log.

tox-gh-matrix adds `"ignore_outcome": true` to each matrix
item where your tox.ini specifies that option. You can check this
in the workflow's [`continue-on-error`][continue-on-error] job step setting.

You'll also need prevent tox from *actually* ignoring failures during
those workflow runs. Tox doesn't have a built-in way to "ignore
*ignore_outcome*", but we can simulate it with an environment variable.
This example calls it `TOX_OVERRIDE_IGNORE_OUTCOME` (but the exact name
doesn't matter).

First, update your workflow to set the workflow's `continue-on-error`
from the matrix and set the environment variable to `false` (meaning
we want tox to pretend `ignore_outcome = false` everywhere, regardless
of what tox.ini says):

```yaml
jobs:
  test:
    steps:
      # ...
      - run: python -m tox -e ${{ matrix.tox.name }}
        continue-on-error: ${{ matrix.tox.ignore_outcome == true }}
        env:
          TOX_OVERRIDE_IGNORE_OUTCOME: false
```

(Only add this variable in the *test* job, not the *get-envlist* job.)

Then, in your tox.ini change every `ignore_outcome = true` to use the
environment variable (using tox's [environment variable substitution][tox-envvar-sub]
syntax with a default value of `true`):

```ini
[testenv:experimental]
ignore_outcome = {env:TOX_OVERRIDE_IGNORE_OUTCOME:true}

# This also works with factor-conditional settings:
[testenv]
ignore_outcome =
    djangoDev = {env:TOX_OVERRIDE_IGNORE_OUTCOME:true}
    py322 = {env:TOX_OVERRIDE_IGNORE_OUTCOME:true}
```

Now when tox is run from the GitHub workflow, it *won't* ignore failures,
so the workflow will catch and report them (and then continue). But when
you run tox locally (or anywhere the environment variable isn't set),
tox *will* ignore failures in those testenvs.


### Using setup-python

The tox-gh-matrix JSON includes `python` objects providing version
data that works with GitHub's [actions/setup-python][].

For example, if your tox.ini has `envlist = py36,py38,docs`,
the `tox --gh-matrix` JSON might look something like this:

```json5
[
  {
    "name": "py36",
    "python": {
      "version": "3.6",
      "spec": "3.6.0-alpha - 3.6",
    },
  },
  {
    "name": "py38",
    "python": {
      "version": "3.8",
      "spec": "3.8.0-alpha - 3.8",
      "installed": "3.8.10"
    },
  },
  { "name": "docs" }
]
```

The `python` field is only present if the tox testenv calls for
a specific Python version–either implied with a `py*` factor or
explicitly via the testenv's [`basepython`][basepython]
setting. (So in this example, there's no `python` field
for the "docs" testenv. If you wanted a specific Python there,
you could add something like `basepython = py310` in your
tox.ini's `[testenv:docs]` section .)

When present, `python` is an object with two or three fields:

* `python.version` is a Python version compatible with setup-python's
  `python-version` parameter. E.g., `"3.10"` or `"2.7"` or `"pypy-3.8"`.
* `python.spec` is a version *range* specifier, also compatible
  with setup-python's `python-version` parameter, which allows
  pre-release versions. E.g., `"3.22.0-alpha - 3.22"`.
* `python.installed` is only present if tox found a compatible
  Python version already available on the runner instance. If so, it is
  the actual version reported by that interpreter. (This is useful for
  skipping setup-python if tox can already find a compatible interpreter
  on the runner.)

Putting this all together, the recommended way to call setup-python
for most workflows is:

```yaml
    steps:
      - name: Setup Python ${{ matrix.tox.python.version }}
        if: matrix.tox.python.spec && ! matrix.tox.python.installed
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.tox.python.spec }}
```

If you don't want to use pre-release Python interpreters, change
`python.spec` to `python.version` in both places.

If your *get-envlist* job (that runs `tox --gh-matrix`) has a different
`runs-on` runner type than the *test* job (`tox -e ${{matrix.tox.name}}`),
you will have different Python versions available on your test runners.
In that case, you should ignore `python.installed` change the check
to just `if: matrix.tox.python.spec`.


### Testing PyPy and older Python versions

If your tox envlist includes PyPy or outdated Python versions, you may need
an extra build step to ensure tox runs under a Python version it supports.

For example, say your tox envlist includes `py34`. Tox dropped Python 3.4
support in 2019. It can still generate a Python 3.4 virtualenv and run
tests in it, but you must run tox itself on a newer version of Python.

To make that work, run [actions/setup-python][] twice: once to install
the (possibly old) version of Python needed for the test environment,
and a second time to change back to a newer version of Python to run tox:

```yaml
    steps:
      - uses: actions/checkout@v3
      # Install the required Python version if necessary:
      - name: Setup Python ${{ matrix.tox.python.version }}
        if: matrix.tox.python.spec && ! matrix.tox.python.installed
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.tox.python.spec }}
      # Now restore the default Python to something newer for tox:
      - name: Restore modern Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.8"
      # Install and run tox with that newer Python:
      - run: python -m pip install tox
      - run: python -m tox -e ${{ matrix.tox.name }}
```

You can choose any `python-version` that makes sense for the second setup-python.
(If you use the version that comes pre-installed on your runner platform,
it will be nearly instantaneous because there's nothing to install;
it's just changing some paths to alter the default.)


### Filtering the tox envlist

Your tox envlist may include environments you don't want to test
in your workflow. You can either restrict the envlist when
you call `tox --gh-matrix` to generate it, or you can use workflow
conditionals to skip jobs based on tox factors or other information.

By default, tox-gh-matrix includes your entire tox.ini `envlist`
in its JSON output. You can limit this with tox command line options
or environment variables that [filter the envlist][tox-conf-envlist],
such as `-e envlist`, `TOXENV` or `TOX_SKIP_ENV`.

For example, if you wanted the matrix to omit all tox testenvs
containing `win` or `mac`, you could use:

```yaml
  get-envlist:
    steps:
      # ...
      - id: generate-envlist
        env:
          # (TOX_SKIP_ENV is a Python regular expression)
          TOX_SKIP_ENV: ".*(win|mac).*"
        run: python -m tox --gh-matrix
```

tox-gh-matrix should also work with other tox plugins that
manipulate the envlist, such as [tox-factor][] and [tox-envlist][].


### Examining tox factors

The tox-gh-matrix JSON includes a list of tox [factors][] for each tox
environment. You can use this with GitHub workflow [conditional execution][]
to skip or include steps for certain factors.

For example, you might use `if: contains(matrix.tox.factors, "pre")`
to only execute a particular job step for tox environments containing a "pre"
factor. Contrast that with `contains(matrix.tox.name, "pre")`
which would do something similar but also match environments containing
factors like "prep" or "present", which may or may not be what you want.

(`factors` is a list of strings; `name` is a single string. In workflow
expression syntax, `matrix.tox.name` is equivalent to `join(matrix.tox.factors, '-')`.)


### Matrix output names and multiple envlists

Running `tox --gh-matrix` sets a GitHub workflow [output parameter][]
to the JSON build matrix. (It appends to the `GITHUB_OUTPUT` file;
you'll get an error if that environment variable isn't set properly.)

The default output name is `envlist`, but you change this with `tox --gh-matrix=VAR`.
You can use this to (in combination with filtering) to create multiple matrices.

Here's an example that uses custom output names, along with the [tox-factor][]
filtering plugin, to construct separate matrices for Mac- and Windows specific
tests (environments with `mac` or `win` factors, respectively):

```yaml
jobs:
  get-envlist:
    runs-on: ubuntu-latest
    outputs:
      mac-envlist: ${{ steps.generate-envlist.outputs.mac-envlist }}
      win-envlist: ${{ steps.generate-envlist.outputs.win-envlist }}
    steps:
      - uses: actions/checkout@v3
      # Also install the tox-factor plugin:
      - run: python -m pip install tox tox-factor tox-gh-matrix
      # Run --gh-matrix twice with different filters and output names:
      - id: generate-envlist
        run: |
          python -m tox -f mac --gh-matrix=mac-envlist
          python -m tox -f win --gh-matrix=win-envlist

  test-mac:
    runs-on: macos-latest
    needs: get-envlist
    strategy:
      matrix:
        tox: ${{ fromJSON(needs.get-envlist.outputs.mac-envlist) }}
    # ...

  test-win:
    runs-on: windows-latest
    needs: get-envlist
    strategy:
      matrix:
        tox: ${{ fromJSON(needs.get-envlist.outputs.win-envlist) }}
    # ...
```


### Additional build matrix dimensions

Your workflow can define additional [build matrix][build-matrix]
properties alongside the tox envlist. GitHub will run all combinations
of properties.

For example, your workflow could repeat the entire tox envlist
on macOS, Windows, and Ubuntu by adding in an `os` property:

```yaml
jobs:
  # ...
  test:
    strategy:
      matrix:
        os: [macos-latest, windows-latest, ubuntu-latest]
        tox: ${{ fromJSON(needs.get-envlist.outputs.envlist) }}
    name: Test ${{ matrix.tox.name }} on ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python ${{ matrix.tox.python.version }}
        if: matrix.tox.python.spec && ! matrix.tox.python.installed
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.tox.python.spec }}
      - run: python -m pip install tox
      - run: python -m tox -e ${{ matrix.tox.name }}
```


### Debugging the matrix

Run `tox --gh-matrix-dump` to display a nicely formatted (multiline,
indented) JSON build matrix, without any GitHub-specific output parameter
syntax.

This can be helpful for debugging the generated matrix (either run in your
local development environment, or as a step in your *get-envlist* job).

It could also be useful for integrating tox with other (non-GitHub) CI systems.

(Or perhaps you were interested in
[debugging *The Matrix*](https://www.imdb.com/title/tt0133093/goofs?tab=gf) ?)


## Contributing, issues, help

Contributions of all types are very welcome, including bug reports, fixes,
documentation corrections and improvements, and new features.

If you have any questions or need help with tox-gh-matrix, please
[ask in the discussions][discussion].

If you encounter any problems, please [file an issue][tracker]
along with as much detail as possible to help reproduce the problem.

For bug fixes and other code changes, tests can be run with [tox][] (naturally).
We try to keep test coverage high before merging new code, but please don't
let incomplete tests keep you from opening a PR. (We'll be happy to work with
you to add tests, etc.)

To propose a new feature, it's often helpful to open a [discussion][] before
investing significant time or effort in code.


## Similar projects

Other tox + GitHub integrations tend to take the opposite approach:
you fully declare the build matrix in your GitHub workflow definition,
and the plugin then simplifies running the correct tox environment(s)
for each matrix job.

* [tox-gh-actions][] detects which tox environments to run based on the
  current active Python version, platform, environment variables, and other
  context, with flexible mapping to tox factors. It also improves integration
  with GitHub's actions logging.
* [tox-gh][] is a newer project with goals similar to tox-gh-actions,
  but some different design philosophies.


## License

Distributed under the terms of the MIT License, tox-gh-matrix is
free and open source software.


<!--
    external links
-->

[actions/setup-python]: https://github.com/actions/setup-python
[basepython]: https://tox.wiki/en/stable/config.html#conf-basepython
[build-matrix]: https://docs.github.com/en/actions/using-jobs/using-a-build-matrix-for-your-jobs
[build-status]: https://github.com/medmunds/tox-gh-matrix/actions?query=workflow:test+branch:main
[conditional execution]: https://docs.github.com/en/actions/using-jobs/using-conditions-to-control-job-execution
[continue-on-error]: https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#jobsjob_idstepscontinue-on-error
[discussion]: https://github.com/medmunds/tox-gh-matrix/discussions
[expression-fromJSON]: https://docs.github.com/en/actions/learn-github-actions/expressions#fromjson
[factors]: https://tox.wiki/en/latest/config.html#tox-environments
[ignore-outcome]: https://tox.wiki/en/stable/config.html#conf-ignore_outcome
[output parameter]: https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#setting-an-output-parameter
[pypi-release]: https://pypi.org/project/tox-gh-matrix/
[tox]: https://tox.wiki/en/stable/
[tox-conf-envlist]: https://tox.wiki/en/stable/config.html#conf-envlist
[tox-envlist]: https://pypi.org/project/tox-envlist/
[tox-factor]: https://pypi.org/project/tox-factor/
[tox-envvar-sub]: https://tox.wiki/en/stable/config.html#environment-variable-substitutions-with-default-values
[tox-gh-actions]: https://pypi.org/project/tox-gh-actions/
[tox-gh]: https://pypi.org/project/tox-gh/
[tracker]: https://github.com/medmunds/tox-gh-matrix/issues
