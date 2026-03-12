import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SummarizationJob, Summary } from "../types/domain";
import VideoSummary from "./VideoSummary";

const apiMocks = vi.hoisted(() => ({
  createSummarizationJob: vi.fn(),
  fetchSummariesByTranscriptId: vi.fn(),
  fetchSummarizationJobs: vi.fn(),
}));

vi.mock("../api/videoService", () => ({
  createSummarizationJob: apiMocks.createSummarizationJob,
  fetchSummariesByTranscriptId: apiMocks.fetchSummariesByTranscriptId,
  fetchSummarizationJobs: apiMocks.fetchSummarizationJobs,
}));

const summaryFixture: Summary = {
  id: "summary-1",
  transcript_id: "transcript-1",
  content:
    "# Episode brief\n\n## Overview\nA thoughtful interview summary.\n\n## Key Points\n- Point one",
  content_profile: "interview",
  created_at: "2026-03-12T14:00:00Z",
  status: "completed",
  summary_metadata: {
    chapters: [
      {
        title: "Opening context",
        start_time: 0,
        end_time: 85,
        summary: "The host introduces the guest and frames the discussion.",
      },
    ],
    highlights: [
      {
        title: "Career turning point",
        detail: "The guest explains the moment they changed product strategy.",
        timestamp_seconds: 92,
      },
    ],
    keywords: ["strategy", "product", "leadership"],
    entities: [
      {
        name: "Northwind Labs",
        entity_type: "organization",
        description: "The company discussed in the interview.",
      },
    ],
    action_items: [
      {
        task: "Follow up on the hiring playbook",
        owner: "Editorial team",
        due_hint: "Next review cycle",
      },
    ],
  },
  variants: {
    default:
      "# Episode brief\n\n## Overview\nA thoughtful interview summary.\n\n## Key Points\n- Point one",
  },
};

const pendingJobFixture: SummarizationJob = {
  id: "summary-job-1",
  transcript_id: "transcript-1",
  content_profile: "podcast",
  created_at: "2026-03-12T14:05:00Z",
  status: "pending",
  started_at: null,
  completed_at: null,
  processing_time_seconds: null,
  error_details: null,
  worker_id: null,
  lease_expires_at: null,
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

describe("VideoSummary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.fetchSummariesByTranscriptId.mockResolvedValue([]);
    apiMocks.fetchSummarizationJobs.mockResolvedValue([]);
    apiMocks.createSummarizationJob.mockResolvedValue(pendingJobFixture);
  });

  it("renders structured enrichments for the latest summary", async () => {
    apiMocks.fetchSummariesByTranscriptId.mockResolvedValue([summaryFixture]);

    const view = renderWithProviders(<VideoSummary transcriptId="transcript-1" />);

    expect(await view.findByText("Episode brief")).toBeInTheDocument();
    expect(view.getByText("Chapters")).toBeInTheDocument();
    expect(view.getByText("Opening context")).toBeInTheDocument();
    expect(view.getByText("Highlights")).toBeInTheDocument();
    expect(view.getByText("Career turning point")).toBeInTheDocument();
    expect(view.getByText("Keywords")).toBeInTheDocument();
    expect(view.getByText("strategy")).toBeInTheDocument();
    expect(view.getByText("Named entities")).toBeInTheDocument();
    expect(view.getByText("Northwind Labs")).toBeInTheDocument();
    expect(view.getByText("Action items")).toBeInTheDocument();
    expect(view.getByText("Follow up on the hiring playbook")).toBeInTheDocument();
  });

  it("sends the selected summary profile when generating a new summary", async () => {
    const user = userEvent.setup();
    const view = renderWithProviders(<VideoSummary transcriptId="transcript-1" />);

    expect(await view.findByText("Ready when you are")).toBeInTheDocument();

    await user.selectOptions(
      view.getByRole("combobox", { name: /summary profile/i }),
      "podcast"
    );
    await user.click(view.getByRole("button", { name: /^generate$/i }));

    expect(apiMocks.createSummarizationJob).toHaveBeenCalledWith("transcript-1", {
      contentProfile: "podcast",
    });
  });
});
