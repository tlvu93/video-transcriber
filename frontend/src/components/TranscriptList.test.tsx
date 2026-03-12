import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  Transcript,
  TranscriptRevision,
  TranslatedTranscript,
  TranslationJob,
} from "../types/domain";
import TranscriptList from "./TranscriptList";

const GERMAN_PATTERN = /german/i;
const TRANSLATE_BUTTON_PATTERN = /translate/i;
const TRANSLATE_MODAL_BUTTON_PATTERN = /^Translate$/i;

const apiMocks = vi.hoisted(() => ({
  createTranscriptComment: vi.fn(),
  createTranslationJob: vi.fn(),
  deleteTranscriptComment: vi.fn(),
  downloadTranscriptExport: vi.fn(),
  downloadTranslatedTranscriptExport: vi.fn(),
  fetchTranscriptComments: vi.fn(),
  fetchTranscriptRevisions: vi.fn(),
  fetchTranslatedTranscripts: vi.fn(),
  fetchTranslationJobs: vi.fn(),
  restoreTranscriptRevision: vi.fn(),
  updateTranscriptReview: vi.fn(),
  updateTranscriptSpeakerAliases: vi.fn(),
  updateTranscriptSegments: vi.fn(),
  updateTranslatedTranscriptSegments: vi.fn(),
}));

vi.mock("../api/videoService", () => ({
  createTranscriptComment: apiMocks.createTranscriptComment,
  createTranslationJob: apiMocks.createTranslationJob,
  deleteTranscriptComment: apiMocks.deleteTranscriptComment,
  downloadTranscriptExport: apiMocks.downloadTranscriptExport,
  downloadTranslatedTranscriptExport: apiMocks.downloadTranslatedTranscriptExport,
  fetchTranscriptComments: apiMocks.fetchTranscriptComments,
  fetchTranscriptRevisions: apiMocks.fetchTranscriptRevisions,
  fetchTranslatedTranscripts: apiMocks.fetchTranslatedTranscripts,
  fetchTranslationJobs: apiMocks.fetchTranslationJobs,
  restoreTranscriptRevision: apiMocks.restoreTranscriptRevision,
  updateTranscriptReview: apiMocks.updateTranscriptReview,
  updateTranscriptSpeakerAliases: apiMocks.updateTranscriptSpeakerAliases,
  updateTranscriptSegments: apiMocks.updateTranscriptSegments,
  updateTranslatedTranscriptSegments:
    apiMocks.updateTranslatedTranscriptSegments,
}));

const baseTranscript: Transcript = {
  id: "transcript-1",
  video_id: "video-1",
  source_type: "video",
  content: "Hello world Another segment",
  format: "txt",
  status: "completed",
  language_code: "en",
  review_assignee: null,
  review_status: "draft",
  speaker_aliases: null,
  created_at: "2026-03-11T10:00:00Z",
  segments: [
    {
      id: 1,
      start_time: 0,
      end_time: 2,
      text: "Hello world",
      speaker: "SPEAKER_00",
    },
    {
      id: 2,
      start_time: 3,
      end_time: 5,
      text: "Another segment",
      speaker: "SPEAKER_01",
    },
  ],
};

const germanTranslation: TranslatedTranscript = {
  id: "translated-1",
  transcript_id: "transcript-1",
  language: "de",
  content: "Hallo Welt Noch ein Abschnitt",
  glossary_terms: [
    {
      source_term: "API",
      target_term: "Schnittstelle",
    },
  ],
  qa_metrics: {
    high_cps_warnings: 1,
    long_line_warnings: 0,
    missing_speaker_warnings: 0,
    overlap_warnings: 0,
    segment_count: 2,
  },
  status: "completed",
  style_guide: "Keep technical wording concise.",
  created_at: "2026-03-11T10:05:00Z",
  segments: [
    {
      id: 1,
      start_time: 0,
      end_time: 2,
      text: "Hallo Welt",
      speaker: null,
    },
    {
      id: 2,
      start_time: 3,
      end_time: 5,
      text: "Noch ein Abschnitt",
      speaker: null,
    },
  ],
};

const pendingTranslationJob: TranslationJob = {
  id: "translation-job-1",
  glossary_terms: null,
  transcript_id: "transcript-1",
  source_language: "en",
  target_language: "de",
  status: "pending",
  style_guide: null,
  created_at: "2026-03-11T10:06:00Z",
  started_at: null,
  completed_at: null,
  processing_time_seconds: null,
  error_details: null,
};

const completedTranslationJob: TranslationJob = {
  id: "translation-job-2",
  glossary_terms: germanTranslation.glossary_terms,
  transcript_id: "transcript-1",
  source_language: "en",
  target_language: "de",
  status: "completed",
  style_guide: germanTranslation.style_guide,
  created_at: "2026-03-11T10:09:00Z",
  started_at: "2026-03-11T10:08:50Z",
  completed_at: "2026-03-11T10:09:00Z",
  processing_time_seconds: 0.4,
  error_details: {
    metrics: {
      cache_hit: true,
      glossary_term_count: 1,
      persist_seconds: 0.03,
      qa_metrics: germanTranslation.qa_metrics ?? undefined,
      segment_count: 2,
      style_guide_used: true,
      total_processing_seconds: 0.4,
      translation_seconds: 0,
      translation_strategy: "cache_hit",
    },
  },
};

const transcriptRevisions: TranscriptRevision[] = [
  {
    id: "revision-2",
    transcript_id: "transcript-1",
    revision_number: 2,
    reason: "segment_edit",
    content: "Hello world Another segment",
    speaker_aliases: null,
    created_at: "2026-03-11T10:04:00Z",
    segments: baseTranscript.segments,
  },
  {
    id: "revision-1",
    transcript_id: "transcript-1",
    revision_number: 1,
    reason: "initial_import",
    content: "Hello world Another segment",
    speaker_aliases: null,
    created_at: "2026-03-11T10:00:00Z",
    segments: baseTranscript.segments,
  },
];

function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        gcTime: 0,
        retry: false,
      },
      mutations: {
        gcTime: 0,
        retry: false,
      },
    },
  });
}

function renderWithProviders(ui: ReactNode) {
  const queryClient = createTestQueryClient();

  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

describe("TranscriptList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.createTranscriptComment.mockResolvedValue({
      id: "comment-1",
      transcript_id: "transcript-1",
      body: "Looks good",
      created_at: "2026-03-11T10:10:00Z",
    });
    apiMocks.deleteTranscriptComment.mockResolvedValue(undefined);
    apiMocks.downloadTranscriptExport.mockResolvedValue(undefined);
    apiMocks.downloadTranslatedTranscriptExport.mockResolvedValue(undefined);
    apiMocks.fetchTranscriptComments.mockResolvedValue([]);
    apiMocks.fetchTranscriptRevisions.mockResolvedValue([]);
    apiMocks.fetchTranslationJobs.mockResolvedValue([]);
    apiMocks.fetchTranslatedTranscripts.mockResolvedValue([]);
    apiMocks.createTranslationJob.mockResolvedValue(pendingTranslationJob);
    apiMocks.restoreTranscriptRevision.mockResolvedValue(baseTranscript);
    apiMocks.updateTranscriptReview.mockResolvedValue(baseTranscript);
    apiMocks.updateTranscriptSpeakerAliases.mockResolvedValue(baseTranscript);
    apiMocks.updateTranscriptSegments.mockResolvedValue(baseTranscript);
    apiMocks.updateTranslatedTranscriptSegments.mockResolvedValue(
      germanTranslation
    );
  });

  it("filters transcript segments with the search box", async () => {
    const user = userEvent.setup();

    const view = renderWithProviders(
      <TranscriptList
        currentTime={0}
        onSegmentClick={vi.fn()}
        transcript={baseTranscript}
      />
    );

    expect(await view.findByText("Hello world")).toBeInTheDocument();
    expect(view.getByText("Another segment")).toBeInTheDocument();

    await user.type(
      view.getByPlaceholderText("Search transcript..."),
      "Another"
    );

    expect(view.getByText("Another segment")).toBeInTheDocument();
    expect(view.queryByText("Hello world")).not.toBeInTheDocument();
  });

  it("switches to an existing translation from the language menu", async () => {
    const user = userEvent.setup();
    apiMocks.fetchTranslatedTranscripts.mockResolvedValue([germanTranslation]);

    const view = renderWithProviders(
      <TranscriptList
        currentTime={0}
        onSegmentClick={vi.fn()}
        transcript={baseTranscript}
      />
    );

    expect(await view.findByText("Hello world")).toBeInTheDocument();

    await user.click(
      view.getByRole("button", { name: TRANSLATE_BUTTON_PATTERN })
    );
    await user.click(view.getByRole("menuitem", { name: GERMAN_PATTERN }));

    expect(view.getByText("Transcript (German)")).toBeInTheDocument();
    expect(view.getByText("Hallo Welt")).toBeInTheDocument();

    expect(view.queryByText("Hello world")).not.toBeInTheDocument();
  });

  it("requests a new translation when the selected language is missing", async () => {
    const user = userEvent.setup();

    const view = renderWithProviders(
      <TranscriptList
        currentTime={0}
        onSegmentClick={vi.fn()}
        transcript={baseTranscript}
      />
    );

    expect(await view.findByText("Hello world")).toBeInTheDocument();

    await user.click(
      view.getByRole("button", { name: TRANSLATE_BUTTON_PATTERN })
    );
    await user.click(view.getByRole("menuitem", { name: GERMAN_PATTERN }));

    expect(view.getByText("Translate Transcript")).toBeInTheDocument();

    await user.click(
      view.getByRole("button", { name: TRANSLATE_MODAL_BUTTON_PATTERN })
    );

    await Promise.resolve();

    expect(apiMocks.createTranslationJob).toHaveBeenCalledWith("transcript-1", "de", {
      glossaryTerms: [],
      styleGuide: null,
    });
  });

  it("sends glossary and style guide controls with a translation request", async () => {
    const user = userEvent.setup();

    const view = renderWithProviders(
      <TranscriptList
        currentTime={0}
        onSegmentClick={vi.fn()}
        transcript={baseTranscript}
      />
    );

    expect(await view.findByText("Hello world")).toBeInTheDocument();

    await user.click(
      view.getByRole("button", { name: TRANSLATE_BUTTON_PATTERN })
    );
    await user.click(view.getByRole("menuitem", { name: GERMAN_PATTERN }));

    await user.type(
      view.getByPlaceholderText(
        /optional instructions like tone, terminology preferences, or subtitle style/i
      ),
      "Prefer concise subtitles."
    );
    await user.type(
      view.getByPlaceholderText(/one term per line/i),
      "API => Schnittstelle{enter}GPU => GPU"
    );
    await user.click(
      view.getByRole("button", { name: TRANSLATE_MODAL_BUTTON_PATTERN })
    );

    await Promise.resolve();

    expect(apiMocks.createTranslationJob).toHaveBeenCalledWith("transcript-1", "de", {
      glossaryTerms: [
        { source_term: "API", target_term: "Schnittstelle" },
        { source_term: "GPU", target_term: "GPU" },
      ],
      styleGuide: "Prefer concise subtitles.",
    });
  });

  it("shows cached translation metrics for the selected language", async () => {
    const user = userEvent.setup();
    apiMocks.fetchTranslatedTranscripts.mockResolvedValue([germanTranslation]);
    apiMocks.fetchTranslationJobs.mockResolvedValue([completedTranslationJob]);

    const view = renderWithProviders(
      <TranscriptList
        currentTime={0}
        onSegmentClick={vi.fn()}
        transcript={baseTranscript}
      />
    );

    expect(await view.findByText("Hello world")).toBeInTheDocument();

    await user.click(
      view.getByRole("button", { name: TRANSLATE_BUTTON_PATTERN })
    );
    await user.click(view.getByRole("menuitem", { name: GERMAN_PATTERN }));

    expect(view.getByText("German translation ready")).toBeInTheDocument();
    expect(view.getByText("Cached")).toBeInTheDocument();
    expect(view.getByText("Reused cached translation")).toBeInTheDocument();
    expect(view.getByText("400 ms")).toBeInTheDocument();
    expect(view.getByText("Style guide")).toBeInTheDocument();
    expect(view.getByText("1 glossary term")).toBeInTheDocument();
    expect(view.getByText("1 fast cues")).toBeInTheDocument();
  });

  it("persists renamed speakers through the API", async () => {
    const user = userEvent.setup();

    const view = renderWithProviders(
      <TranscriptList
        currentTime={0}
        onSegmentClick={vi.fn()}
        transcript={baseTranscript}
      />
    );

    expect(await view.findByText("Hello world")).toBeInTheDocument();

    await user.click(view.getByRole("button", { name: "Speaker 1" }));

    const renameInput = view.getByDisplayValue("Speaker 1");
    await user.clear(renameInput);
    await user.type(renameInput, "Host{enter}");

    expect(apiMocks.updateTranscriptSpeakerAliases).toHaveBeenCalledWith(
      "transcript-1",
      {
        SPEAKER_00: "Host",
        SPEAKER_01: "Speaker 2",
      }
    );
  });

  it("restores an earlier transcript revision from history", async () => {
    const user = userEvent.setup();
    apiMocks.fetchTranscriptRevisions.mockResolvedValue(transcriptRevisions);

    const view = renderWithProviders(
      <TranscriptList
        currentTime={0}
        onSegmentClick={vi.fn()}
        transcript={baseTranscript}
      />
    );

    expect(await view.findByText("Hello world")).toBeInTheDocument();

    await user.click(view.getByRole("button", { name: /history/i }));
    await user.click(
      await view.findByRole("button", { name: /restore revision 1/i })
    );

    expect(apiMocks.restoreTranscriptRevision).toHaveBeenCalledWith(
      "transcript-1",
      "revision-1"
    );
  });

  it("shows backend export download state while a transcript export is preparing", async () => {
    const user = userEvent.setup();
    let resolveDownload: (() => void) | undefined;

    apiMocks.downloadTranscriptExport.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveDownload = resolve;
        })
    );

    const view = renderWithProviders(
      <TranscriptList
        currentTime={0}
        onSegmentClick={vi.fn()}
        transcript={baseTranscript}
      />
    );

    expect(await view.findByText("Hello world")).toBeInTheDocument();

    await user.click(view.getByRole("button", { name: /export/i }));
    await user.click(view.getByRole("menuitem", { name: /download as txt/i }));

    expect(apiMocks.downloadTranscriptExport).toHaveBeenCalledWith(
      "transcript-1",
      {
        format: "txt",
        includeSpeakers: true,
        includeTimestamps: true,
      }
    );
    expect(
      view.getByRole("button", { name: /preparing txt/i })
    ).toBeInTheDocument();

    if (resolveDownload) {
      resolveDownload();
    }

    await waitFor(() => {
      expect(view.getByRole("button", { name: /^export$/i })).toBeInTheDocument();
    });
  });
});
