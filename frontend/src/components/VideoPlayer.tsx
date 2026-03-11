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
    <div className="panel-elevated relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(245,158,11,0.14),transparent_24%),linear-gradient(180deg,rgba(255,255,255,0.04),transparent_28%)]" />
      <div className="relative overflow-hidden rounded-[1.4rem] bg-black">
        <video
          className={isPortrait ? "mx-auto max-h-[70vh] w-auto" : "w-full"}
          controls
          onLoadedMetadata={handleMetadataLoaded}
          onTimeUpdate={handlePlayerTimeUpdate}
          preload="metadata"
          ref={videoRef}
          src={videoUrl}
        >
          Your browser does not support the video tag.
        </video>

        <div className="pointer-events-none absolute top-4 left-4 rounded-full border border-white/10 bg-black/45 px-3 py-1 font-semibold text-[11px] text-white/75 uppercase tracking-[0.18em] backdrop-blur-sm">
          Live player
        </div>

        <button
          className="absolute top-4 right-4 rounded-full border border-white/10 bg-black/50 px-3 py-1 text-white text-xs backdrop-blur-sm transition hover:bg-black/70"
          onClick={() => setShowSubtitles(!showSubtitles)}
          type="button"
        >
          {showSubtitles ? "Subtitles on" : "Subtitles off"}
        </button>

        {showSubtitles && subtitleText && (
          <div className="pointer-events-none absolute right-4 bottom-5 left-4 flex justify-center">
            <div className="max-w-3xl rounded-2xl border border-white/10 bg-black/70 px-4 py-3 text-center text-base text-white shadow-lg backdrop-blur-md sm:text-lg">
              {subtitleText}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
