import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  Transcript,
  TranslatedTranscript,
  TranslationJob,
} from "../types/domain";
import TranscriptList from "./TranscriptList";

const GERMAN_PATTERN = /german/i;
const TRANSLATE_BUTTON_PATTERN = /translate/i;
const TRANSLATE_MODAL_BUTTON_PATTERN = /^Translate$/i;

const apiMocks = vi.hoisted(() => ({
  createTranslationJob: vi.fn(),
  fetchTranslatedTranscripts: vi.fn(),
  fetchTranslationJobs: vi.fn(),
  updateTranscriptSegments: vi.fn(),
  updateTranslatedTranscriptSegments: vi.fn(),
}));

vi.mock("../api/videoService", () => ({
  createTranslationJob: apiMocks.createTranslationJob,
  fetchTranslatedTranscripts: apiMocks.fetchTranslatedTranscripts,
  fetchTranslationJobs: apiMocks.fetchTranslationJobs,
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
  status: "completed",
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
  transcript_id: "transcript-1",
  source_language: "en",
  target_language: "de",
  status: "pending",
  created_at: "2026-03-11T10:06:00Z",
  started_at: null,
  completed_at: null,
  processing_time_seconds: null,
  error_details: null,
};

const completedTranslationJob: TranslationJob = {
  id: "translation-job-2",
  transcript_id: "transcript-1",
  source_language: "en",
  target_language: "de",
  status: "completed",
  created_at: "2026-03-11T10:09:00Z",
  started_at: "2026-03-11T10:08:50Z",
  completed_at: "2026-03-11T10:09:00Z",
  processing_time_seconds: 0.4,
  error_details: {
    metrics: {
      cache_hit: true,
      persist_seconds: 0.03,
      segment_count: 2,
      total_processing_seconds: 0.4,
      translation_seconds: 0,
      translation_strategy: "cache_hit",
    },
  },
};

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
    apiMocks.fetchTranslationJobs.mockResolvedValue([]);
    apiMocks.fetchTranslatedTranscripts.mockResolvedValue([]);
    apiMocks.createTranslationJob.mockResolvedValue(pendingTranslationJob);
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

    expect(apiMocks.createTranslationJob).toHaveBeenCalledWith(
      "transcript-1",
      "de"
    );
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
  });
});
