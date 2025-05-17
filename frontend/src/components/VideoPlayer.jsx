import { useRef, useEffect } from "react";

const VideoPlayer = ({ videoUrl, currentTime, onTimeUpdate }) => {
  const videoRef = useRef(null);

  // Seek to the specified time when currentTime changes
  useEffect(() => {
    if (videoRef.current && currentTime !== null && currentTime !== undefined) {
      videoRef.current.currentTime = currentTime;
      videoRef.current.play().catch((error) => {
        console.error("Error playing video:", error);
      });
    }
  }, [currentTime]);

  // Handle time updates to track current position
  const handleTimeUpdate = () => {
    if (videoRef.current && onTimeUpdate) {
      onTimeUpdate(videoRef.current.currentTime);
    }
  };

  return (
    <div className="w-full bg-black rounded-lg overflow-hidden shadow-lg">
      <video
        ref={videoRef}
        className="w-full"
        src={videoUrl}
        controls
        autoPlay
        onTimeUpdate={handleTimeUpdate}
      >
        Your browser does not support the video tag.
      </video>
    </div>
  );
};

export default VideoPlayer;
