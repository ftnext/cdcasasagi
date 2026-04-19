from __future__ import annotations

from getgauge.python import data_store, step


@step("The last command succeeds")
def assert_last_command_succeeded():
    result = data_store.scenario["last_result"]
    assert result.returncode == 0, (
        f"expected zero exit, got {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


@step("stdout contains <text>")
def assert_stdout_contains(text):
    result = data_store.scenario["last_result"]
    assert text in result.stdout, (
        f"stdout does not contain {text!r}\nstdout:\n{result.stdout}"
    )


@step("stdout does not contain <text>")
def assert_stdout_does_not_contain(text):
    result = data_store.scenario["last_result"]
    assert text not in result.stdout, (
        f"stdout unexpectedly contains {text!r}\nstdout:\n{result.stdout}"
    )


@step("stdout has <earlier> listed before <later>")
def assert_stdout_order(earlier, later):
    result = data_store.scenario["last_result"]
    stdout = result.stdout
    i_earlier = stdout.find(earlier)
    i_later = stdout.find(later)
    assert i_earlier != -1, f"{earlier!r} not found in stdout:\n{stdout}"
    assert i_later != -1, f"{later!r} not found in stdout:\n{stdout}"
    assert i_earlier < i_later, (
        f"expected {earlier!r} before {later!r}, but {earlier!r} at {i_earlier} "
        f"and {later!r} at {i_later}\nstdout:\n{stdout}"
    )
