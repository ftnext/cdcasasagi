from __future__ import annotations

from getgauge.python import data_store, step


@step("The delete preview announces removal of <name>")
def assert_delete_preview_announces(name):
    """Assert stdout is a delete preview for *name* (not a write output).

    Distinguishes the preview from the write-mode message: both quote the
    name and URL, but only the preview ends with the re-run hint.
    """
    result = data_store.scenario["last_result"]
    stdout = result.stdout
    for expected in ("Will remove", f'"{name}"', "Re-run with --write to apply"):
        assert expected in stdout, (
            f"delete preview is missing {expected!r}\nstdout:\n{stdout}"
        )
