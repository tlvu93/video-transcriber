import { isAxiosError } from "axios";
import type { ChangeEvent, DragEvent, FormEvent } from "react";
import { useRef, useState } from "react";
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

  if (!isOpen) {
    return null;
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
          throw new Error("Please enter a YouTube URL.");
        }
        // For YouTube, we just wait for the backend to finish downloading/queueing
        setProgress(50); // fake progress just to show it's doing something
        await downloadYoutubeVideo(youtubeUrl);
        setProgress(100);
      }

      onUploadSuccess();
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
      setTimeout(() => {
        setFile(null);
        setYoutubeUrl("");
        setProgress(0);
      }, 500);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 transition-opacity">
      <div className="mx-4 w-full max-w-md overflow-hidden rounded-lg bg-white shadow-xl dark:bg-gray-800">
        <div className="flex items-center justify-between border-b px-6 py-4 dark:border-gray-700">
          <h2 className="font-bold text-gray-800 text-xl dark:text-white">
            Add New Video
          </h2>
          <button
            className="text-gray-500 hover:text-gray-700 focus:outline-none dark:text-gray-400 dark:hover:text-white"
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

        <div className="px-6 py-4">
          <div className="mb-4 flex rounded-lg bg-gray-100 p-1 dark:bg-gray-700">
            <button
              className={`flex-1 rounded-md py-2 font-medium text-sm transition-colors ${
                activeTab === "file"
                  ? "bg-white text-gray-800 shadow dark:bg-gray-600 dark:text-white"
                  : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              }`}
              onClick={() => setActiveTab("file")}
              type="button"
            >
              Upload File
            </button>
            <button
              className={`flex-1 rounded-md py-2 font-medium text-sm transition-colors ${
                activeTab === "youtube"
                  ? "bg-white text-gray-800 shadow dark:bg-gray-600 dark:text-white"
                  : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
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
                className={`mt-4 flex justify-center rounded-md border-2 border-dashed px-6 pt-5 pb-6 transition-colors ${
                  file
                    ? "border-blue-500 bg-blue-50 dark:bg-blue-900/10"
                    : "border-gray-300 hover:border-blue-400 dark:border-gray-600 dark:hover:border-blue-500"
                } block w-full cursor-pointer`}
                htmlFor="fileInput"
                onDragOver={(event) => event.preventDefault()}
                onDrop={handleDrop}
              >
                <div className="space-y-1 text-center">
                  {file ? (
                    <div>
                      <svg
                        className="mx-auto h-12 w-12 text-blue-500"
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
                      <p className="mt-2 font-medium text-gray-600 text-sm dark:text-gray-300">
                        {file.name}
                      </p>
                      <p className="text-gray-500 text-xs dark:text-gray-400">
                        ({(file.size / (1024 * 1024)).toFixed(2)} MB)
                      </p>
                      <button
                        className="mt-3 text-red-500 text-sm transition hover:text-red-700"
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
                    <>
                      <svg
                        aria-hidden="true"
                        className="mx-auto h-12 w-12 text-gray-400"
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
                      <div className="flex justify-center text-gray-600 text-sm dark:text-gray-300">
                        <span className="relative rounded-md font-medium text-blue-600 focus-within:outline-none focus-within:ring-2 focus-within:ring-blue-500 focus-within:ring-offset-2 hover:text-blue-500 dark:text-blue-400">
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
                      <p className="text-gray-500 text-xs dark:text-gray-400">
                        MP4, WEBM, MKV up to 500MB
                      </p>
                    </>
                  )}
                </div>
              </label>
            ) : (
              <div className="mt-4">
                <label
                  className="mb-2 block font-medium text-gray-700 text-sm dark:text-gray-300"
                  htmlFor="youtubeUrl"
                >
                  Video URL (Vimeo, Twitter, Reddit, etc.)
                </label>
                <input
                  className="w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                  id="youtubeUrl"
                  onChange={(event) => setYoutubeUrl(event.target.value)}
                  placeholder="https://vimeo.com/12345678"
                  required
                  type="url"
                  value={youtubeUrl}
                />
                <p className="mt-2 text-gray-500 text-xs dark:text-gray-400">
                  The video will be downloaded directly by the server and
                  processed. Note: YouTube links may be unstable due to bot
                  protection.
                </p>
              </div>
            )}

            {error && (
              <div className="mt-4 text-red-600 text-sm dark:text-red-400">
                {error}
              </div>
            )}

            {uploading && (
              <div className="mt-4">
                <div className="mb-1 flex justify-between text-gray-600 text-xs dark:text-gray-400">
                  <span>
                    {activeTab === "file"
                      ? "Uploading..."
                      : "Processing URL..."}
                  </span>
                  <span>{progress}%</span>
                </div>
                <div className="h-2 w-full rounded-full bg-gray-200 dark:bg-gray-700">
                  <div
                    className="h-2 rounded-full bg-blue-600 transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            )}

            <div className="mt-6 flex justify-end space-x-3">
              <button
                className="rounded-md border border-gray-300 bg-white px-4 py-2 font-medium text-gray-700 text-sm shadow-sm hover:bg-gray-50 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
                onClick={onClose}
                type="button"
              >
                Cancel
              </button>
              <button
                className="rounded-md border border-transparent bg-blue-600 px-4 py-2 font-medium text-sm text-white shadow-sm hover:bg-blue-700 focus:outline-none disabled:cursor-not-allowed disabled:bg-blue-400"
                disabled={
                  uploading ||
                  (activeTab === "file" && !file) ||
                  (activeTab === "youtube" && !youtubeUrl)
                }
                type="submit"
              >
                {uploading ? "Processing..." : "Add Video"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
