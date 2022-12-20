from textwrap import dedent

import pytest
from tox.exception import MissingDependency

from tox_gh_matrix.plugin import set_gh_output


@pytest.fixture
def gh_output(tmp_path, monkeypatch, mocker):
    output_path = tmp_path / "github-output.env"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
    mocker.patch("uuid.uuid4", side_effect=["uuid4-1", "uuid4-2", "uuid4-3"])
    yield lambda: output_path.read_text()


def test_gh_output(gh_output):
    set_gh_output("one", "ONE")
    set_gh_output("two", "TWO")
    set_gh_output("one", "ONE AGAIN")
    set_gh_output("multiline", "this\n  value has\nmultiple lines")
    set_gh_output("also", "different\nEOF value")
    result = gh_output()
    assert result == dedent(
        """\
        one=ONE
        two=TWO
        one=ONE AGAIN
        multiline<<EOF-uuid4-1
        this
          value has
        multiple lines
        EOF-uuid4-1
        also<<EOF-uuid4-2
        different
        EOF value
        EOF-uuid4-2
        """
    )


def test_missing_env():
    with pytest.raises(MissingDependency):
        set_gh_output("one", "ONE")
