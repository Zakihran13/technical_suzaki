from projects.utils.helper import construct_youtube_search_params


def test_construct_youtube_search_params_prioritizes_song_title():
    assert construct_youtube_search_params(
        [{"ORIGINAL ARTIST": "The Artist", "SONG TITLE": "The Song"}]
    ) == [
        {
            "q": "The Song The Artist",
            "part": "snippet",
            "type": "video",
            "maxResults": 10,
            "order": "relevance",
        }
    ]


def test_construct_youtube_search_params_uses_title_when_artist_missing():
    assert construct_youtube_search_params(
        [{"ORIGINAL ARTIST": None, "SONG TITLE": "The Song"}]
    )[0]["q"] == "The Song"