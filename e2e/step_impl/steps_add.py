from __future__ import annotations

from getgauge.python import data_store, step


@step("A preview is shown")
def assert_preview_shown():
    result = data_store.scenario["last_result"]
    assert result.returncode == 0, (
        f"exit code {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "This is a preview" in result.stdout, (
        f"preview marker not found in stdout:\n{result.stdout}"
    )
