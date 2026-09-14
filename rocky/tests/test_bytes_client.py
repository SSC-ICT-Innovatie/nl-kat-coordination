import rocky.bytes_client
from rocky.bytes_client import BytesClient


def test_token_cached_across_instances(mocker):
    """Two BytesClient instances with the same credentials share one token (#4442)."""
    rocky.bytes_client._token_cache.clear()
    mocker.patch.object(BytesClient, "_get_token", return_value="token-a")

    client1 = BytesClient("http://bytes", "user", "pass", "org")
    client2 = BytesClient("http://bytes", "user", "pass", "org")

    assert client1.token == "token-a"
    assert client2.token == "token-a"
    assert BytesClient._get_token.call_count == 1


def test_token_invalidation_refetches(mocker):
    """After invalidation the next access fetches a fresh token."""
    rocky.bytes_client._token_cache.clear()
    mocker.patch.object(BytesClient, "_get_token", side_effect=["token-a", "token-b"])

    client1 = BytesClient("http://bytes", "user", "pass", "org")
    client2 = BytesClient("http://bytes", "user", "pass", "org")

    assert client1.token == "token-a"
    client1._invalidate_token()
    assert client2.token == "token-b"
    assert BytesClient._get_token.call_count == 2


def test_different_users_cached_separately(mocker):
    rocky.bytes_client._token_cache.clear()
    mocker.patch.object(BytesClient, "_get_token", side_effect=["token-a", "token-b"])

    client_a = BytesClient("http://bytes", "user-a", "pass", "org")
    client_b = BytesClient("http://bytes", "user-b", "pass", "org")

    assert client_a.token == "token-a"
    assert client_b.token == "token-b"
    assert BytesClient._get_token.call_count == 2
