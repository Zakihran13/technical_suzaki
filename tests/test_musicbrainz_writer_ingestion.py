from projects.transform.musicbrainz_writer_ingestion import _writer_credits


def test_writer_credits_extracts_supported_work_relations():
    work = {
        "relations": [
            {"type": "composer", "artist": {"id": "writer-1", "name": "Composer"}},
            {"type": "lyricist", "artist": {"id": "writer-2", "name": "Lyricist"}},
            {"type": "producer", "artist": {"id": "producer-1", "name": "Producer"}},
        ]
    }

    assert _writer_credits(work) == [
        {"id": "writer-1", "name": "Composer", "role": "composer"},
        {"id": "writer-2", "name": "Lyricist", "role": "lyricist"},
    ]