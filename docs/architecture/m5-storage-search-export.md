# M5 Search, Storage, and Export

This milestone completes the storage/search/export modernization slice.

## Outcomes

- transcript search now supports PostgreSQL FTS and trigram ranking plus filters for language, review status, speaker, video id, and video title
- the Search modal exposes those filters directly in the UI
- transcript exports now support `txt`, `srt`, `vtt`, `json`, `ass`, and a zipped review package
- translated transcript exports now support `txt`, `srt`, `vtt`, `json`, and `ass`
- storage identity is now backend-agnostic:
  - `local_fs` stores canonical absolute file paths
  - `s3_compatible` stores canonical `s3://bucket/key` URIs and resolves them through a mounted local object-storage root for processing
- upload, YouTube ingest, watched-folder registration, and playback resolution now preserve canonical storage URIs instead of rewriting them back to local working paths

## Watcher behavior

- the watcher now asks the active storage backend for watch roots
- when the backend does not expose watchable roots, the watcher exits cleanly instead of assuming local folders exist

## Schema

- added supporting indexes for filtered search on:
  - `videos.filename`
  - `transcripts.language_code`
  - `transcripts.review_status`
  - `transcript_segment_search.speaker`
