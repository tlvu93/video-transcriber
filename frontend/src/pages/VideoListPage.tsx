import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { fetchVideos } from "../api/videoService";
import UploadModal from "../components/UploadModal";
import { useVideoListLiveUpdates } from "../hooks/useLiveUpdates";
import { getStatusColor } from "../utils/status";
import { sortByNewest } from "../utils/transcript";

export default function VideoListPage() {
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const queryClient = useQueryClient();
  useVideoListLiveUpdates();
  const videosQuery = useQuery({
    queryKey: ["videos"],
    queryFn: fetchVideos,
    select: sortByNewest,
  });

  if (videosQuery.isPending) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-12 w-12 animate-spin rounded-full border-blue-500 border-t-2 border-b-2" />
      </div>
    );
  }

  if (videosQuery.isError) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="rounded border-red-500 border-l-4 bg-red-100 p-4 text-red-700">
          <p>Failed to load videos. Please try again later.</p>
        </div>
      </div>
    );
  }

  const videos = videosQuery.data ?? [];

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-bold text-2xl text-gray-800 dark:text-white">
          Video Transcriber
        </h1>
        <button
          className="flex items-center rounded-lg bg-blue-600 px-4 py-2 font-medium text-white shadow-sm transition-colors hover:bg-blue-700"
          onClick={() => setIsUploadModalOpen(true)}
          type="button"
        >
          <svg
            className="mr-2 h-5 w-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <title>Add Video</title>
            <path
              d="M12 4v16m8-8H4"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
            />
          </svg>
          Add Video
        </button>
      </div>

      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUploadSuccess={() =>
          queryClient.invalidateQueries({ queryKey: ["videos"] })
        }
      />

      {videos.length === 0 ? (
        <div className="rounded-lg bg-white p-6 text-center shadow-md dark:bg-gray-800">
          <p className="text-gray-600 dark:text-gray-300">
            No videos available. Upload a video to get started.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {videos.map((video) => (
            <Link
              className="block overflow-hidden rounded-lg bg-white shadow-md transition-shadow hover:shadow-lg dark:bg-gray-800"
              key={video.id}
              to={`/videos/${video.id}`}
            >
              <div className="p-4">
                <h2 className="mb-2 truncate font-semibold text-gray-800 text-lg dark:text-white">
                  {video.filename}
                </h2>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-300">
                    {new Date(video.created_at).toLocaleDateString()}
                  </span>
                  <span
                    className={`font-medium ${getStatusColor(video.status)}`}
                  >
                    {video.status}
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
