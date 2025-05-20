import { useRef, useEffect, useState } from "react";

const VideoPlayer = ({ videoUrl, currentTime, onTimeUpdate }) => {
  const videoRef = useRef(null);
  const [isPortrait, setIsPortrait] = useState(false);

  // Detect if video is portrait (vertical) when metadata is loaded
  const handleMetadataLoaded = () => {
    if (videoRef.current) {
      const { videoWidth, videoHeight } = videoRef.current;
      setIsPortrait(videoHeight > videoWidth);
    }
  };

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
    <div className="w-full bg-black rounded-lg overflow-hidden shadow-lg flex justify-center">
      <video
        ref={videoRef}
        className={isPortrait ? "max-h-[70vh] w-auto" : "w-full"}
        src={videoUrl}
        controls
        autoPlay
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleMetadataLoaded}
      >
        Your browser does not support the video tag.
      </video>
    </div>
  );
};

export default VideoPlayer;
