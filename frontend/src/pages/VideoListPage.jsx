import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { fetchVideos } from "../api/videoService";

const VideoListPage = () => {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadVideos = async () => {
      try {
        setLoading(true);
        const data = await fetchVideos();
        setVideos(data);
        setLoading(false);
      } catch (err) {
        console.error("Error loading videos:", err);
        setError("Failed to load videos. Please try again later.");
        setLoading(false);
      }
    };

    loadVideos();
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 rounded">
          <p>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6 text-gray-800 dark:text-white">
        Video Transcriber
      </h1>

      {videos.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 text-center">
          <p className="text-gray-600 dark:text-gray-300">
            No videos available. Upload a video to get started.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {videos.map((video) => (
            <Link
              key={video.id}
              to={`/videos/${video.id}`}
              className="block bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow"
            >
              <div className="p-4">
                <h2 className="text-lg font-semibold text-gray-800 dark:text-white mb-2 truncate">
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
};

// Helper function to get color based on status
const getStatusColor = (status) => {
  switch (status?.toLowerCase()) {
    case "completed":
    case "transcribed":
      return "text-green-600 dark:text-green-400";
    case "pending":
    case "processing":
      return "text-yellow-600 dark:text-yellow-400";
    case "error":
    case "failed":
      return "text-red-600 dark:text-red-400";
    default:
      return "text-gray-600 dark:text-gray-400";
  }
};

export default VideoListPage;
