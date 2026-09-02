from dags.pipeline import music_catalog_pipeline


def test_music_catalog_pipeline_has_expected_quality_gate_dependencies():
    workflow = music_catalog_pipeline()

    assert workflow.dag_id == "music_catalog_pipeline"
    assert set(workflow.task_ids) == {
        "initialize_schema",
        "ingest_spotify_raw",
        "ingest_youtube_raw",
        "normalize_spotify",
        "normalize_youtube",
        "match_platforms",
        "enforce_quality_gate",
        "build_catalog",
    }
    assert set(workflow.get_task("build_catalog").upstream_task_ids) == {
        "match_platforms",
        "enforce_quality_gate",
    }