import json

import httpx
import pytest

from swiss_rail.http import download, sha256


def test_conditional_download_and_cache_integrity(tmp_path):
    dest = tmp_path / "source.csv"
    calls = []

    def handler(request):
        calls.append(request)
        if request.headers.get("If-None-Match") == "v1":
            return httpx.Response(304)
        return httpx.Response(200, content=b"a,b\n1,2\n", headers={"etag": "v1"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        download("https://example.test/source", dest, http=http)
        download("https://example.test/source", dest, http=http)
        assert len(calls) == 1
        download("https://example.test/source", dest, refresh=True, http=http)
        assert len(calls) == 2
        dest.write_bytes(b"corrupted")
        download("https://example.test/source", dest, http=http)
        assert calls[-1].headers.get("If-None-Match") is None
        assert dest.read_bytes() == b"a,b\n1,2\n"


def test_access_denied_is_not_retried(tmp_path):
    calls = []

    def denied(request):
        calls.append(request)
        return httpx.Response(403)

    with httpx.Client(transport=httpx.MockTransport(denied)) as http:
        with pytest.raises(httpx.HTTPStatusError):
            download("https://example.test/source", tmp_path / "file", http=http)
    assert len(calls) == 1
    assert not (tmp_path / "file").exists()


def test_oversized_refresh_retains_existing_file(tmp_path):
    dest = tmp_path / "file"
    dest.write_bytes(b"old")
    dest.with_suffix(".meta.json").write_text(
        json.dumps(
            {
                "url": "https://example.test/source",
                "sha256": sha256(dest),
            }
        )
    )
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"way too large"))
    ) as http:
        with pytest.raises(ValueError, match="limit"):
            download("https://example.test/source", dest, refresh=True, max_bytes=4, http=http)
    assert dest.read_bytes() == b"old"
    assert not dest.with_suffix(".part").exists()
