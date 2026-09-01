from app.services.visualization_skills import generate


def test_current_reports_project_complete_character_indexes():
    ten_little = generate("work-novel-962a77c6", "character_relationship")
    guilty = generate("work-series-93c9174b", "character_relationship")

    assert len(ten_little.relationship_nodes) >= 11
    assert any(node.label == "劳伦斯·沃格雷夫" for node in ten_little.relationship_nodes)
    assert len(guilty.relationship_nodes) >= 11
    assert any(node.label == "陆鸣" for node in guilty.relationship_nodes)


def test_current_reports_use_work_specific_tracks_without_fake_dates():
    ten_little = generate("work-novel-962a77c6", "timeline")
    guilty = generate("work-series-93c9174b", "timeline")

    assert list(ten_little.timeline_tracks) == ["truth", "reader"]
    assert ten_little.timeline_scale == "ordinal"
    assert len(ten_little.timeline_events) >= 20
    assert list(guilty.timeline_tracks) == ["truth", "investigation"]
    assert guilty.timeline_scale == "year"
    assert len(guilty.timeline_events) >= 20
