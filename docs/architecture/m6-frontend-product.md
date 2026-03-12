# M6 Frontend Product Upgrade

This milestone closes the remaining frontend product gaps that were still open after the earlier review, comments, revision-history, and export work.

## Delivered

- the library page now supports a server-backed title query through `GET /videos/?q=...`
- library filters and layout mode persist between sessions in the browser
- users can save and re-apply named library views for common triage/review workflows
- transcript exports now surface backend download state in the workspace while assets are being prepared
- transcript export actions continue to use backend-generated files instead of browser-built content

## Main Files

- `frontend/src/pages/VideoListPage.tsx`
- `frontend/src/hooks/usePersistentState.ts`
- `frontend/src/components/TranscriptList.tsx`
- `frontend/src/api/videoService.ts`
- `backend/app/api/app.py`

## Remaining Work After M6

The next roadmap milestone is M7, which focuses on richer AI workflows rather than core frontend collaboration UX.
