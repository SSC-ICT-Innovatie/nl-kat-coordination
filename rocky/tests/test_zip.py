import zipfile

from rocky.views.bytes_raw import zip_data


def test_zip_data():
    raws = {"id1": b"1234", "id3": b"4321", "id5": b"asd                ss"}
    raw_metas = [
        {"id": "id1", "mime_types": [], "secure_hash": "sha256:test", "boefje_meta": {}},
        {"id": "id3", "mime_types": [{"value": "error/test"}], "secure_hash": "sha256:test", "boefje_meta": {}},
        {"id": "id5", "mime_types": []},
    ]

    z_file = zip_data(raws, raw_metas)
    assert zipfile.is_zipfile(z_file)

    with zipfile.ZipFile(z_file, "r") as zf:
        for raw_meta in raw_metas:
            assert zf.read(raw_meta["id"]) == raws[raw_meta["id"]]
