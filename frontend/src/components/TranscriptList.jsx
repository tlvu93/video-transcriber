import { useState, useEffect } from "react";
import TranscriptSegment from "./TranscriptSegment";
import { fetchTranslatedTranscripts, createTranslationJob } from "../api/videoService.js";
import TranslationPanel from "./TranslationPanel"; // Import TranslationPanel

// Placeholder for globe icon, replace with actual icon library if available
const GlobeIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 24 24"
    strokeWidth={1.5}
    stroke="currentColor"
    className="w-5 h-5 inline-block"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M10.5 21L5.25 15.75M10.5 21V5.25M10.5 21H13.5M10.5 5.25L5.25 10.5M10.5 5.25H13.5M5.25 10.5L10.5 15.75M5.25 10.5H2.25M13.5 5.25L18.75 10.5M13.5 5.25H16.5M18.75 10.5L13.5 15.75M18.75 10.5H21.75M13.5 15.75V21M13.5 15.75H10.5"
    />
  </svg>
);

// Define available languages (can be moved to a config file or fetched from an API)
const AVAILABLE_LANGUAGES = [
  { code: "en", name: "English", flag: "🇺🇸" },
  { code: "es", name: "Spanish", flag: "🇪🇸" },
  { code: "fr", name: "French", flag: "🇫🇷" },
  { code: "de", name: "German", flag: "🇩🇪" },
  { code: "ja", name: "Japanese", flag: "🇯🇵" },
];

const TranscriptList = ({ transcript, currentTime, onSegmentClick, videoId }) => { // Added videoId prop
  const [showTimestamps, setShowTimestamps] = useState(true);
  const [showSpeaker, setShowSpeaker] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [translateMenuOpen, setTranslateMenuOpen] = useState(false); // State for translation dropdown
  const [selectedLanguage, setSelectedLanguage] = useState(null); // E.g., 'es'
  const [translations, setTranslations] = useState({}); // Stores fetched translations, e.g., { es: { ...transcript } }
  const [isLoadingTranslation, setIsLoadingTranslation] = useState(false);

  // Effect to fetch translation when selectedLanguage changes
  useEffect(() => {
    if (selectedLanguage && !translations[selectedLanguage] && videoId) {
      const fetchTranslation = async () => {
        setIsLoadingTranslation(true);
        try {
          const translatedTranscript = await fetchTranslatedTranscripts(videoId, selectedLanguage);
          if (translatedTranscript) {
            setTranslations(prev => ({ ...prev, [selectedLanguage]: translatedTranscript }));
          } else {
            // Handle case where translation is not available (e.g., allow user to request it)
            console.log(`Translation for ${selectedLanguage} not found.`);
          }
        } catch (error) {
          console.error("Error fetching translation:", error);
          // Handle error (e.g., show a notification to the user)
        }
        setIsLoadingTranslation(false);
      };
      fetchTranslation();
    }
  }, [selectedLanguage, videoId, translations]);

  const currentTranscriptData = selectedLanguage && translations[selectedLanguage] ? translations[selectedLanguage] : transcript;

  if (!currentTranscriptData) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4">
        <p className="text-gray-500 dark:text-gray-400 text-center py-4">
          No transcript available.
        </p>
      </div>
    );
  }

  // Ensure segments array exists
  const segments = currentTranscriptData ? currentTranscriptData.segments || [] : [];

  if (segments.length === 0 && !isLoadingTranslation) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white">
            Transcript {selectedLanguage ? `(${AVAILABLE_LANGUAGES.find(l => l.code === selectedLanguage)?.name})` : ""}
          </h3>
          {/* Placeholder for where the Translate button will go - to be added in next diff block */}
        </div>
        {isLoadingTranslation && (
          <p className="text-gray-500 dark:text-gray-400 text-center py-4">
            Loading translation...
          </p>
        )}
        {!isLoadingTranslation && currentTranscriptData && currentTranscriptData.content && (
           <span className="text-gray-800 dark:text-gray-200">
             {currentTranscriptData.content}
           </span>
        )}
        {!isLoadingTranslation && (!currentTranscriptData || !currentTranscriptData.content) && (
           <p className="text-gray-500 dark:text-gray-400 text-center py-4">
            No transcript segments available.
           </p>
        )}
        </p>
      </div>
    );
  }

  // Filter segments based on search query
  const filteredSegments = searchQuery
    ? segments.filter((segment) =>
        segment.text.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : segments;

  // Find the active segment based on current video time
  const findActiveSegment = () => {
    if (!currentTime) return null;

    // Use segments from the currently displayed transcript (original or translated)
    const currentSegments = currentTranscriptData ? currentTranscriptData.segments || [] : [];
    for (let i = 0; i < currentSegments.length; i++) {
      const segment = currentSegments[i];
      const nextSegment = currentSegments[i + 1];

      // Ensure we're using the correct field names
      const segmentStart = segment.start_time;
      const nextSegmentStart = nextSegment ? nextSegment.start_time : Infinity;

      if (currentTime >= segmentStart && currentTime < nextSegmentStart) {
        return segment;
      }
    }
    return null;
  };

  const activeSegment = findActiveSegment();

  // Handle downloading transcript as text
  const handleDownloadTranscript = () => {
    const currentSegments = currentTranscriptData ? currentTranscriptData.segments || [] : [];
    const textContent = currentSegments
      .map((segment) => {
        let line = "";
        if (showTimestamps && showSpeaker && segment.speaker && !selectedLanguage) { // Speaker info might not be in translated data
          line = `[${formatTimeForDownload(segment.start_time)}] ${
            segment.speaker
          }: ${segment.text}`;
        } else if (showTimestamps) {
          line = `[${formatTimeForDownload(segment.start_time)}] ${
            segment.text
          }`;
        } else if (showSpeaker && segment.speaker) {
          line = `${segment.speaker}: ${segment.text}`;
        } else {
          line = segment.text;
        }
        return line;
      })
      .join("\n\n");

    // Create and trigger download
    const blob = new Blob([textContent], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "transcript.txt";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Format time for download (HH:MM:SS)
  const formatTimeForDownload = (seconds) => {
    if (seconds === undefined || seconds === null) return "00:00:00";

    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainingSeconds = Math.floor(seconds % 60);

    return `${hours.toString().padStart(2, "0")}:${minutes
      .toString()
      .padStart(2, "0")}:${remainingSeconds.toString().padStart(2, "0")}`;
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-white">
          Transcript {selectedLanguage ? `(${AVAILABLE_LANGUAGES.find(l => l.code === selectedLanguage)?.name})` : ""}
        </h3>
        <div className="flex items-center space-x-2">
          {/* Translate Button and Dropdown */}
          <div className="relative inline-block text-left">
            <button
              onClick={() => setTranslateMenuOpen(!translateMenuOpen)}
              className="px-3 py-1 text-sm bg-blue-500 hover:bg-blue-600 text-white rounded flex items-center transition-colors"
            >
              <GlobeIcon />
              <span className="ml-2">Translate</span>
            </button>
            {translateMenuOpen && (
              <div className="origin-top-right absolute right-0 mt-2 w-64 rounded-md shadow-lg bg-white dark:bg-gray-700 ring-1 ring-black ring-opacity-5 focus:outline-none z-20">
                <div
                  className="py-1"
                  role="menu"
                  aria-orientation="vertical"
                  aria-labelledby="translate-options-menu"
                >
                  <div className="px-4 py-2 text-sm text-gray-700 dark:text-gray-200 font-semibold">
                    Select Language
                  </div>
                  {transcript && transcript.language_code && ( // Show original language if available
                    <button
                      onClick={() => {
                        setSelectedLanguage(null);
                        setTranslateMenuOpen(false);
                      }}
                      className={`block w-full text-left px-4 py-2 text-sm ${
                        !selectedLanguage
                          ? "bg-gray-100 dark:bg-gray-600 text-gray-900 dark:text-white"
                          : "text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                      }`}
                      role="menuitem"
                    >
                      Show Original ({transcript.language_code.toUpperCase()})
                    </button>
                  )}
                  {AVAILABLE_LANGUAGES.map((lang) => {
                    const isOriginalLanguage = lang.code === (transcript?.language_code);
                    const isSelected = selectedLanguage === lang.code;
                    const translationExists = !!translations[lang.code];

                    return (
                      <button
                        key={lang.code}
                        onClick={() => {
                          if (isOriginalLanguage) {
                            setSelectedLanguage(null);
                          } else {
                            setSelectedLanguage(lang.code);
                          }
                          setTranslateMenuOpen(false);
                        }}
                        disabled={isLoadingTranslation || (isSelected && !isOriginalLanguage)}
                        className={`block w-full text-left px-4 py-2 text-sm flex items-center justify-between ${
                          (isSelected && !isOriginalLanguage) || (!selectedLanguage && isOriginalLanguage)
                            ? "bg-gray-100 dark:bg-gray-600 text-gray-900 dark:text-white"
                            : "text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                        } ${isLoadingTranslation ? "opacity-50 cursor-not-allowed" : ""}`}
                        role="menuitem"
                      >
                        <span>
                          {lang.flag} {lang.name}
                        </span>
                        {translationExists && lang.code !== transcript?.language_code && (
                          <span className="text-green-500">✓</span> // Checkmark if translated and not original
                        )}
                        {!translationExists && lang.code !== transcript?.language_code && (
                          <span className="text-xs text-gray-400 dark:text-gray-500">(Request via panel below)</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Existing Menu Button */}
          <div className="relative inline-block text-left">
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="px-3 py-1 text-sm bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
            >
              Menu
            </button>
            {menuOpen && (
              <div className="origin-top-right absolute right-0 mt-2 w-56 rounded-md shadow-lg bg-white dark:bg-gray-700 ring-1 ring-black ring-opacity-5 focus:outline-none z-10">
                <div
                  className="py-1"
                  role="menu"
                aria-orientation="vertical"
                aria-labelledby="options-menu"
              >
                <div className="px-4 py-2 text-sm text-gray-700 dark:text-gray-200 font-semibold">
                  Category Options
                </div>
                <button
                  onClick={() => {
                    setShowTimestamps(!showTimestamps);
                    // setMenuOpen(false); // Optionally close menu on selection
                  }}
                  className="block w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                  role="menuitem"
                >
                  {showTimestamps ? "Hide Timestamps" : "Show Timestamps"}
                </button>
                <button
                  onClick={() => {
                    setShowSpeaker(!showSpeaker);
                    // setMenuOpen(false); // Optionally close menu on selection
                  }}
                  className="block w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                  role="menuitem"
                >
                  {showSpeaker ? "Hide Speaker" : "Show Speaker"}
                </button>
                <hr className="my-1 border-gray-200 dark:border-gray-600" />
                <button
                  onClick={() => {
                    handleDownloadTranscript();
                    setMenuOpen(false); // Close menu after action
                  }}
                  className="block w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                  role="menuitem"
                >
                  Download Transcript
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="mb-4">
        <input
          type="text"
          placeholder="Search transcript..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200"
        />
      </div>

      <div className="max-h-[500px] overflow-y-auto pr-2">
        {isLoadingTranslation && segments.length === 0 && (
          <p className="text-gray-500 dark:text-gray-400 text-center py-4">
            Loading translated transcript...
          </p>
        )}
        {!isLoadingTranslation && segments.length === 0 && currentTranscriptData && currentTranscriptData.content && (
            <p className="text-gray-500 dark:text-gray-400 text-center py-4">
                <span className="text-gray-800 dark:text-gray-200">
                    {currentTranscriptData.content} {/* Display single content if no segments */}
                </span>
            </p>
        )}
        {!isLoadingTranslation && segments.length === 0 && (!currentTranscriptData || !currentTranscriptData.content) && (
             <p className="text-gray-500 dark:text-gray-400 text-center py-4">
                No transcript segments available for the selected language.
                {/* TODO: Add button/logic to request translation if not available */}
             </p>
        )}
        {segments.map((segment, index) => (
          <TranscriptSegment
            key={index}
            segment={segment}
            isActive={
              activeSegment && activeSegment.start_time === segment.start_time
            }
            showTimestamps={showTimestamps}
            showSpeaker={showSpeaker && !selectedLanguage} // Show speaker only for original transcript
            onClick={onSegmentClick}
          />
        ))}
      </div>

      {/* Integrated TranslationPanel */}
      {videoId && (
      <div className="mt-6">
        <TranslationPanel transcript={{ id: videoId, language_code: transcript?.language_code }} />
      </div>
      )}
    </div>
  );
};

export default TranscriptList;
