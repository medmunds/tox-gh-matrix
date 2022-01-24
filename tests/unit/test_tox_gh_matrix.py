def test_flag_help(cmd):
    result = cmd("--help")
    result.assert_success(is_run_test_env=False)
    assert "--gh-matrix [VAR]" in result.out
    assert "--gh-matrix-dump" in result.out
