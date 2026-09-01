from projects.transform.metadata_ingestion import _select_tracks


def test_artistless_song_keeps_only_similar_tracks():
    document = {"SONG TITLE": "BERTAHAN HIDUP", "ORIGINAL ARTIST": None}
    tracks = [
        {"id": "match", "name": "Bertahan Hidup"},
        {"id": "wrong", "name": "An Unrelated Song"},
    ]

    assert _select_tracks(document, tracks) == [(0, tracks[0])]


def test_artistless_song_keeps_one_result_without_similarity_check():
    document = {"SONG TITLE": "BERTAHAN HIDUP", "ORIGINAL ARTIST": None}
    tracks = [{"id": "only", "name": "Different Title"}]

    assert _select_tracks(document, tracks) == [(0, tracks[0])]


def test_artistless_song_keeps_best_fallback_when_no_titles_are_similar():
    document = {"SONG TITLE": "BERTAHAN HIDUP", "ORIGINAL ARTIST": None}
    tracks = [
        {"id": "less-similar", "name": "Another Song"},
        {"id": "best", "name": "Bertahan"},
    ]

    assert _select_tracks(document, tracks) == [(1, tracks[1])]