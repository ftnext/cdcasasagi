import pytest

from cdcasasagi.server_name import NameDerivationError, derive_server_name


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://developers.openai.com/mcp", "developers"),
        ("https://mcp.linear.app/mcp", "linear"),
        ("https://mcp.notion.com/mcp", "notion"),
        ("https://mcp.api.getguru.com/mcp", "getguru"),
        ("https://api.devrev.ai/mcp/v1", "devrev"),
        ("https://app.circleback.ai/api/mcp", "circleback"),
        ("https://huggingface.co/mcp", "huggingface"),
        ("https://learn.microsoft.com/api/mcp", "learn"),
        ("https://bigquery.googleapis.com/mcp", "bigquery"),
        ("https://mcp-server.egnyte.com/mcp", "egnyte"),
        ("https://bindings.mcp.cloudflare.com/mcp", "bindings"),
    ],
)
def test_derive_server_name(url, expected):
    assert derive_server_name(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://localhost/mcp",
        "https://192.168.1.1/mcp",
        "https://[::1]/mcp",
    ],
)
def test_derive_fails_for_localhost_and_ip(url):
    with pytest.raises(NameDerivationError):
        derive_server_name(url)


def test_derive_fails_for_single_char():
    with pytest.raises(NameDerivationError):
        derive_server_name("https://mcp.x.com/mcp")


def test_derive_fails_for_numeric_only():
    with pytest.raises(NameDerivationError):
        derive_server_name("https://mcp.123.com/mcp")
