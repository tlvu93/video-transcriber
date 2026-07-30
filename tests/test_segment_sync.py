from backend.app.persistence.models import (
    GlossaryTerm,
    Speaker,
    Transcript,
    TranscriptSegmentRow,
    TranslatedTranscript,
    Video,
)
from backend.app.persistence.segment_sync import (
    sync_transcript_segment_rows,
    sync_transcript_speaker_rows,
    sync_translated_transcript_localization_rows,
)


def test_transcript_segment_and_speaker_sync_updates_rows_in_place(db_session):
    video = Video(filename="sync-test.mp4", status="pending")
    transcript = Transcript(
        video=video,
        content="Hello world Goodbye",
        segments=[
            {"id": 1, "start_time": 0, "end_time": 2, "text": "Hello", "speaker": "spk_1"},
            {"id": 2, "start_time": 2, "end_time": 4, "text": "Goodbye", "speaker": "spk_2"},
        ],
        speaker_aliases={"spk_1": "Host"},
    )
    db_session.add_all([video, transcript])
    db_session.flush()

    sync_transcript_segment_rows(db_session, transcript)
    sync_transcript_speaker_rows(db_session, transcript)
    db_session.commit()

    original_segment_row = (
        db_session.query(TranscriptSegmentRow)
        .filter(TranscriptSegmentRow.transcript_id == transcript.id, TranscriptSegmentRow.segment_id == 1)
        .first()
    )
    original_speaker_row = (
        db_session.query(Speaker)
        .filter(Speaker.transcript_id == transcript.id, Speaker.speaker_key == "spk_1")
        .first()
    )

    transcript.segments = [
        {"id": 1, "start_time": 0, "end_time": 3, "text": "Hello there", "speaker": "spk_1"},
        {"id": 3, "start_time": 3, "end_time": 5, "text": "New speaker", "speaker": "spk_3"},
    ]
    transcript.speaker_aliases = {"spk_1": "Lead host", "spk_3": "Guest"}

    sync_transcript_segment_rows(db_session, transcript)
    sync_transcript_speaker_rows(db_session, transcript)
    db_session.commit()

    updated_segment_row = (
        db_session.query(TranscriptSegmentRow)
        .filter(TranscriptSegmentRow.transcript_id == transcript.id, TranscriptSegmentRow.segment_id == 1)
        .first()
    )
    updated_rows = (
        db_session.query(TranscriptSegmentRow)
        .filter(TranscriptSegmentRow.transcript_id == transcript.id)
        .order_by(TranscriptSegmentRow.segment_id.asc())
        .all()
    )
    updated_speaker_row = (
        db_session.query(Speaker)
        .filter(Speaker.transcript_id == transcript.id, Speaker.speaker_key == "spk_1")
        .first()
    )
    speaker_keys = {
        row.speaker_key
        for row in db_session.query(Speaker).filter(Speaker.transcript_id == transcript.id).all()
    }

    assert original_segment_row is not None
    assert updated_segment_row is not None
    assert original_segment_row.id == updated_segment_row.id
    assert updated_segment_row.text == "Hello there"
    assert [row.segment_id for row in updated_rows] == [1, 3]

    assert original_speaker_row is not None
    assert updated_speaker_row is not None
    assert original_speaker_row.id == updated_speaker_row.id
    assert updated_speaker_row.display_name == "Lead host"
    assert speaker_keys == {"spk_1", "spk_3"}


def test_translation_localization_sync_updates_glossary_rows_in_place(db_session):
    video = Video(filename="translation-sync.mp4", status="pending")
    transcript = Transcript(video=video, content="Hello", segments=[{"id": 1, "text": "Hello"}])
    translated_transcript = TranslatedTranscript(
        transcript=transcript,
        language="de",
        content="Hallo",
        style_guide="Keep it formal",
        glossary_terms=[
            {"source_term": "Hello", "target_term": "Hallo"},
            {"source_term": "Team", "target_term": "Mannschaft"},
        ],
    )
    db_session.add_all([video, transcript, translated_transcript])
    db_session.flush()

    sync_translated_transcript_localization_rows(db_session, translated_transcript)
    db_session.commit()

    original_first_row = (
        db_session.query(GlossaryTerm)
        .filter(GlossaryTerm.translated_transcript_id == translated_transcript.id, GlossaryTerm.sort_order == 1)
        .first()
    )

    translated_transcript.style_guide = "Keep it concise"
    translated_transcript.glossary_terms = [
        {"source_term": "Hello", "target_term": "Guten Tag"},
        {"source_term": "Review", "target_term": "Prufung"},
    ]

    sync_translated_transcript_localization_rows(db_session, translated_transcript)
    db_session.commit()

    updated_first_row = (
        db_session.query(GlossaryTerm)
        .filter(GlossaryTerm.translated_transcript_id == translated_transcript.id, GlossaryTerm.sort_order == 1)
        .first()
    )
    updated_rows = (
        db_session.query(GlossaryTerm)
        .filter(GlossaryTerm.translated_transcript_id == translated_transcript.id)
        .order_by(GlossaryTerm.sort_order.asc())
        .all()
    )

    assert original_first_row is not None
    assert updated_first_row is not None
    assert original_first_row.id == updated_first_row.id
    assert updated_first_row.target_term == "Guten Tag"
    assert translated_transcript.style_guide == "Keep it concise"
    assert [(row.sort_order, row.source_term, row.target_term) for row in updated_rows] == [
        (1, "Hello", "Guten Tag"),
        (2, "Review", "Prufung"),
    ]
