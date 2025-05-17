import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import VideoPlayer from "../components/VideoPlayer";
import VideoMetadata from "../components/VideoMetadata";
import TranscriptList from "../components/TranscriptList";
import VideoSummary from "../components/VideoSummary";
import { fetchVideoById, fetchTranscriptsByVideoId } from "../api/videoService";

const VideoDetailPage = () => {
  const { id } = useParams();
  const [video, setVideo] = useState(null);
  const [transcript, setTranscript] = useState(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [seekTime, setSeekTime] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch video and transcript data
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);

        // Fetch video data
        const videoData = await fetchVideoById(id);
        setVideo(videoData);

        // Fetch transcript data
        const transcripts = await fetchTranscriptsByVideoId(id);
        if (transcripts && transcripts.length > 0) {
          const transcript = transcripts[0]; // Use the first transcript

          // Log transcript data for debugging
          console.log("Transcript data:", transcript);

          // Ensure segments exist or create empty array
          if (!transcript.segments) {
            transcript.segments = [];

            // If content exists but no segments, create a simple segment from content
            if (transcript.content) {
              transcript.segments.push({
                id: 1,
                start_time: 0,
                end_time: 0,
                text: transcript.content,
              });
            }
          } else {
            // Log the first segment to help with debugging
            if (transcript.segments.length > 0) {
              console.log("First segment:", transcript.segments[0]);
            }

            // Ensure all segments have the expected properties
            transcript.segments = transcript.segments.map((seg, index) => ({
              id: seg.id || index + 1,
              start_time: seg.start_time || 0,
              end_time: seg.end_time || 0,
              text: seg.text || "",
            }));
          }

          setTranscript(transcript);
        }

        setLoading(false);
      } catch (err) {
        console.error("Error fetching data:", err);
        setError("Failed to load video data. Please try again later.");
        setLoading(false);
      }
    };

    if (id) {
      fetchData();
    }
  }, [id]);

  // Handle segment click to seek video
  const handleSegmentClick = (time) => {
    setSeekTime(time);
  };

  // Handle video time update
  const handleTimeUpdate = (time) => {
    setCurrentTime(time);
  };

  // Generate video URL
  const getVideoUrl = () => {
    if (!video) return "";
    return `/api/videos/${video.id}/download`;
  };

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
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <VideoPlayer
            videoUrl={getVideoUrl()}
            currentTime={seekTime}
            onTimeUpdate={handleTimeUpdate}
          />
          <div className="mt-4">
            <VideoMetadata video={video} />
            {transcript && <VideoSummary transcript={transcript} />}
          </div>
        </div>
        <div>
          <TranscriptList
            transcript={transcript}
            currentTime={currentTime}
            onSegmentClick={handleSegmentClick}
          />
        </div>
      </div>
    </div>
  );
};

export default VideoDetailPage;
