from __future__ import annotations

from getgauge.python import data_store, step


@step("The delete preview announces removal of <url>")
def assert_delete_preview_announces(url):
    """Assert stdout is a delete preview for *url* (not a write output).

    Distinguishes the preview from the write-mode message: both mention the
    URL and the removed name, but only the preview ends with the re-run hint.
    """
    result = data_store.scenario["last_result"]
    stdout = result.stdout
    for expected in ("Will remove", url, "Re-run with --write to apply"):
        assert expected in stdout, (
            f"delete preview is missing {expected!r}\nstdout:\n{stdout}"
        )
