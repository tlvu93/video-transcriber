import { isAxiosError } from "axios";
import type { ChangeEvent, DragEvent, FormEvent } from "react";
import { useEffect, useRef, useState } from "react";
import { downloadYoutubeVideo, uploadVideo } from "../api/videoService";

type UploadTab = "file" | "youtube";

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess: () => void | Promise<void>;
}

export default function UploadModal({
  isOpen,
  onClose,
  onUploadSuccess,
}: UploadModalProps) {
  const [activeTab, setActiveTab] = useState<UploadTab>("file");
  const [file, setFile] = useState<File | null>(null);
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  let submitLabel = "Import video";
  if (uploading) {
    submitLabel = activeTab === "file" ? "Uploading..." : "Importing...";
  } else if (activeTab === "file") {
    submitLabel = "Start transcription";
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>): void {
    const selected = event.target.files?.[0];
    if (selected?.type?.startsWith("video/")) {
      setFile(selected);
      setError(null);
    } else {
      setFile(null);
      setError("Please select a valid video file.");
    }
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>): void {
    event.preventDefault();
    const dropped = event.dataTransfer.files?.[0];
    if (dropped?.type?.startsWith("video/")) {
      setFile(dropped);
      setError(null);
    } else {
      setError("Please drop a valid video file.");
    }
  }

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ): Promise<void> {
    event.preventDefault();
    setError(null);
    setUploading(true);
    setProgress(0);

    try {
      if (activeTab === "file") {
        if (!file) {
          throw new Error("No file selected.");
        }

        await uploadVideo(file, (progressEvent) => {
          const total = progressEvent.total ?? progressEvent.loaded;
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / total
          );
          setProgress(percentCompleted);
        });
      } else {
        if (!youtubeUrl) {
          throw new Error("Please enter a video URL.");
        }

        setProgress(50);
        await downloadYoutubeVideo(youtubeUrl);
        setProgress(100);
      }

      await onUploadSuccess();
      onClose();
    } catch (err) {
      console.error("Upload error:", err);
      if (isAxiosError<{ detail?: string }>(err)) {
        setError(
          err.response?.data?.detail || err.message || "Failed to upload video."
        );
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to upload video.");
      }
    } finally {
      setUploading(false);
      window.setTimeout(() => {
        setFile(null);
        setYoutubeUrl("");
        setProgress(0);
      }, 500);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 backdrop-blur-md transition-opacity">
      <div className="panel-elevated w-full max-w-2xl overflow-hidden border-white/10 bg-card/95">
        <div className="flex items-center justify-between border-white/10 border-b px-6 py-5">
          <div>
            <p className="font-semibold text-primary/80 text-xs uppercase tracking-[0.28em]">
              Intake
            </p>
            <h2 className="mt-1 font-semibold text-2xl text-foreground">
              Add a new video
            </h2>
          </div>
          <button
            className="rounded-full border border-white/10 bg-white/5 p-2 text-muted-foreground transition hover:bg-white/10 hover:text-foreground"
            onClick={onClose}
            type="button"
          >
            <svg
              className="h-6 w-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <title>Close</title>
              <path
                d="M6 18L18 6M6 6l12 12"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
              />
            </svg>
          </button>
        </div>

        <div className="px-6 py-6">
          <div className="mb-6 flex rounded-full border border-white/10 bg-white/5 p-1">
            <button
              className={`flex-1 rounded-full px-4 py-2.5 font-medium text-sm transition-colors ${
                activeTab === "file"
                  ? "bg-primary text-primary-foreground shadow-glow"
                  : "text-muted-foreground hover:text-foreground"
              }`}
              onClick={() => setActiveTab("file")}
              type="button"
            >
              Upload File
            </button>
            <button
              className={`flex-1 rounded-full px-4 py-2.5 font-medium text-sm transition-colors ${
                activeTab === "youtube"
                  ? "bg-primary text-primary-foreground shadow-glow"
                  : "text-muted-foreground hover:text-foreground"
              }`}
              onClick={() => setActiveTab("youtube")}
              type="button"
            >
              Import URL
            </button>
          </div>

          <form onSubmit={handleSubmit}>
            {activeTab === "file" ? (
              <label
                className={`mt-4 block w-full cursor-pointer rounded-[1.5rem] border border-dashed px-6 pt-5 pb-6 transition-colors ${
                  file
                    ? "border-primary/60 bg-primary/10"
                    : "border-white/15 bg-white/4 hover:border-primary/40 hover:bg-white/6"
                }`}
                htmlFor="fileInput"
                onDragOver={(event) => event.preventDefault()}
                onDrop={handleDrop}
              >
                <div className="flex min-h-[19rem] items-center justify-center text-center">
                  {file ? (
                    <div>
                      <svg
                        className="mx-auto h-12 w-12 text-primary"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <title>File Uploaded</title>
                        <path
                          d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                        />
                      </svg>
                      <p className="mt-3 font-medium text-foreground text-sm">
                        {file.name}
                      </p>
                      <p className="text-muted-foreground text-xs">
                        ({(file.size / (1024 * 1024)).toFixed(2)} MB)
                      </p>
                      <button
                        className="mt-4 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-muted-foreground text-sm transition hover:bg-white/10 hover:text-foreground"
                        onClick={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                          setFile(null);
                        }}
                        type="button"
                      >
                        Remove file
                      </button>
                    </div>
                  ) : (
                    <div>
                      <svg
                        aria-hidden="true"
                        className="mx-auto h-14 w-14 text-primary/80"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 48 48"
                      >
                        <title>Upload Icon</title>
                        <path
                          d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                        />
                      </svg>
                      <p className="mt-5 text-center font-medium text-foreground">
                        Drag footage here or browse locally
                      </p>
                      <div className="mt-2 flex justify-center text-muted-foreground text-sm">
                        <span className="relative rounded-md font-medium text-primary focus-within:outline-none focus-within:ring-2 focus-within:ring-primary/40">
                          <span>Upload a video</span>
                          <input
                            accept="video/*"
                            className="sr-only"
                            id="fileInput"
                            onChange={handleFileChange}
                            ref={fileInputRef}
                            type="file"
                          />
                        </span>
                        <p className="pl-1">or drag and drop</p>
                      </div>
                      <p className="mt-4 text-muted-foreground text-xs">
                        MP4, WEBM, MKV and other common formats up to 500MB
                      </p>
                    </div>
                  )}
                </div>
              </label>
            ) : (
              <div className="mt-4 rounded-[1.5rem] border border-white/10 bg-white/4 p-5">
                <label
                  className="mb-2 block font-medium text-foreground text-sm"
                  htmlFor="youtubeUrl"
                >
                  Video URL (Vimeo, Twitter, Reddit, etc.)
                </label>
                <input
                  className="w-full rounded-2xl border border-white/10 bg-background/80 px-4 py-3 text-foreground shadow-sm outline-none transition focus:border-primary/40 focus:ring-2 focus:ring-primary/30"
                  id="youtubeUrl"
                  onChange={(event) => setYoutubeUrl(event.target.value)}
                  placeholder="https://vimeo.com/12345678"
                  required
                  type="url"
                  value={youtubeUrl}
                />
                <p className="mt-3 text-muted-foreground text-sm">
                  Paste a direct video URL or supported media page and we will
                  queue it for processing.
                </p>
              </div>
            )}

            {uploading && (
              <div className="mt-5">
                <div className="overflow-hidden rounded-full bg-white/10 text-xs">
                  <div
                    className="bg-primary px-2 py-1 text-center font-medium text-primary-foreground transition-all"
                    style={{ width: `${progress}%` }}
                  >
                    {progress}%
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="mt-5 rounded-2xl border border-destructive/20 bg-destructive/10 p-4 text-destructive text-sm">
                {error}
              </div>
            )}

            <div className="mt-6 flex justify-end space-x-3">
              <button
                className="rounded-full border border-white/10 bg-white/5 px-5 py-3 text-muted-foreground transition hover:bg-white/10 hover:text-foreground"
                onClick={onClose}
                type="button"
              >
                Cancel
              </button>
              <button
                className="rounded-full bg-primary px-5 py-3 font-medium text-primary-foreground transition hover:bg-warning disabled:cursor-not-allowed disabled:opacity-50"
                disabled={
                  uploading || (activeTab === "file" ? !file : !youtubeUrl)
                }
                type="submit"
              >
                {submitLabel}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
