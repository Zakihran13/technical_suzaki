from projects.transform.data_quality import serializable_record, validate_source_document


def test_validate_source_document_rejects_missing_required_fields():
    issues = validate_source_document({"CODE": None, "SONG TITLE": " "})

    assert {(issue.severity, issue.rule_name) for issue in issues} == {
        ("error", "required_code"),
        ("error", "required_song_title"),
    }


def test_validate_source_document_rejects_non_integer_codes():
    issues = validate_source_document({"CODE": "not-a-code", "SONG TITLE": "Song"})

    assert issues[0].rule_name == "valid_code"


def test_serializable_record_converts_non_json_values():
    record = serializable_record({"_id": object(), "CODE": 1})

    assert record["CODE"] == 1
    assert isinstance(record["_id"], str)