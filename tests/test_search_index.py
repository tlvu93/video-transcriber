from backend.app.persistence.models import Transcript, TranscriptSegmentSearch, Video
from backend.app.persistence.search_index import sync_transcript_search_rows
from backend.app.persistence.segment_sync import sync_transcript_segment_rows


def test_search_index_sync_updates_existing_rows_without_reinsert(db_session):
    video = Video(filename="search-sync.mp4", status="pending")
    transcript = Transcript(
        video=video,
        content="Alpha Beta",
        segments=[
            {"id": 1, "start_time": 0, "end_time": 2, "text": "Alpha", "speaker": "spk_1"},
        ],
    )
    db_session.add_all([video, transcript])
    db_session.flush()

    sync_transcript_segment_rows(db_session, transcript)
    sync_transcript_search_rows(db_session, transcript)
    db_session.commit()

    original_search_row = (
        db_session.query(TranscriptSegmentSearch)
        .filter(
            TranscriptSegmentSearch.transcript_id == transcript.id,
            TranscriptSegmentSearch.segment_id == 1,
        )
        .first()
    )

    transcript.segments = [
        {"id": 1, "start_time": 0, "end_time": 2.5, "text": "Alpha updated", "speaker": "spk_1"},
        {"id": 2, "start_time": 2.5, "end_time": 4.0, "text": "Beta", "speaker": "spk_2"},
    ]
    sync_transcript_segment_rows(db_session, transcript)
    sync_transcript_search_rows(db_session, transcript)
    db_session.commit()

    updated_search_row = (
        db_session.query(TranscriptSegmentSearch)
        .filter(
            TranscriptSegmentSearch.transcript_id == transcript.id,
            TranscriptSegmentSearch.segment_id == 1,
        )
        .first()
    )
    all_rows = (
        db_session.query(TranscriptSegmentSearch)
        .filter(TranscriptSegmentSearch.transcript_id == transcript.id)
        .order_by(TranscriptSegmentSearch.segment_id.asc())
        .all()
    )

    assert original_search_row is not None
    assert updated_search_row is not None
    assert original_search_row.id == updated_search_row.id
    assert updated_search_row.text == "Alpha updated"
    assert [row.segment_id for row in all_rows] == [1, 2]
