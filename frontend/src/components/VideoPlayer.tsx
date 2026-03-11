import { useEffect, useRef, useState } from "react";

interface VideoPlayerProps {
  currentTime: number | null;
  onTimeUpdate: (time: number) => void;
  subtitleText?: string | null;
  videoUrl: string;
}

export default function VideoPlayer({
  videoUrl,
  currentTime,
  onTimeUpdate,
  subtitleText,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [isPortrait, setIsPortrait] = useState(false);
  const [showSubtitles, setShowSubtitles] = useState(true);

  function handleMetadataLoaded(): void {
    if (videoRef.current) {
      const { videoWidth, videoHeight } = videoRef.current;
      setIsPortrait(videoHeight > videoWidth);
    }
  }

  useEffect(() => {
    if (videoRef.current && currentTime !== null && currentTime !== undefined) {
      videoRef.current.currentTime = currentTime;
    }
  }, [currentTime]);

  function handlePlayerTimeUpdate(): void {
    if (videoRef.current) {
      onTimeUpdate(videoRef.current.currentTime);
    }
  }

  return (
    <div className="relative flex w-full justify-center overflow-hidden rounded-lg bg-black shadow-lg">
      <video
        className={isPortrait ? "max-h-[70vh] w-auto" : "w-full"}
        controls
        onLoadedMetadata={handleMetadataLoaded}
        onTimeUpdate={handlePlayerTimeUpdate}
        preload="metadata"
        ref={videoRef}
        src={videoUrl}
      >
        Your browser does not support the video tag.
      </video>
      <button
        className="absolute top-3 right-3 rounded-full bg-black/60 px-3 py-1 text-white text-xs backdrop-blur transition hover:bg-black/75"
        onClick={() => setShowSubtitles(!showSubtitles)}
        type="button"
      >
        {showSubtitles ? "Subtitles On" : "Subtitles Off"}
      </button>
      {showSubtitles && subtitleText && (
        <div className="pointer-events-none absolute right-4 bottom-4 left-4 flex justify-center">
          <div className="max-w-3xl rounded-xl bg-black/70 px-4 py-3 text-center text-base text-white shadow-lg backdrop-blur sm:text-lg">
            {subtitleText}
          </div>
        </div>
      )}
    </div>
  );
}
