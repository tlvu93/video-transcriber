import { useState, useEffect } from "react";
import TranscriptSegment from "./TranscriptSegment";
import {
  fetchTranslatedTranscripts,
  createTranslationJob,
} from "../api/videoService.js";

// Language globe icon
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
      d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418"
    />
  </svg>
);

// Check mark icon for available translations
const CheckMarkIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 24 24"
    strokeWidth={1.5}
    stroke="currentColor"
    className="w-5 h-5 text-green-500"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
    />
  </svg>
);

// Loading spinner icon
const LoadingIcon = () => (
  <svg
    className="animate-spin h-5 w-5 text-blue-500"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 24 24"
  >
    <circle
      className="opacity-25"
      cx="12"
      cy="12"
      r="10"
      stroke="currentColor"
      strokeWidth="4"
    ></circle>
    <path
      className="opacity-75"
      fill="currentColor"
      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
    ></path>
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

const TranscriptList = ({
  transcript,
  currentTime,
  onSegmentClick,
  videoId,
}) => {
  // Added videoId prop
  const [showTimestamps, setShowTimestamps] = useState(true);
  const [showSpeaker, setShowSpeaker] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [translateMenuOpen, setTranslateMenuOpen] = useState(false); // State for translation dropdown
  const [selectedLanguage, setSelectedLanguage] = useState(null); // E.g., 'es'
  const [translations, setTranslations] = useState({}); // Stores fetched translations, e.g., { es: { ...transcript } }
  const [isLoadingTranslation, setIsLoadingTranslation] = useState(false);
  const [showTranslationModal, setShowTranslationModal] = useState(false);
  const [pendingLanguage, setPendingLanguage] = useState(null);
  const [translatingLanguage, setTranslatingLanguage] = useState(null);

  // Effect to fetch all available translations when component mounts
  useEffect(() => {
    if (transcript && transcript.id) {
      const fetchAllTranslations = async () => {
        try {
          const allTranslations = await fetchTranslatedTranscripts(
            transcript.id
          );
          const translationsMap = {};

          if (Array.isArray(allTranslations)) {
            allTranslations.forEach((translation) => {
              translationsMap[translation.language] = translation;
            });
          }

          setTranslations(translationsMap);
        } catch (error) {
          console.error("Error fetching all translations:", error);
        }
      };

      fetchAllTranslations();
    }
  }, [transcript]);

  // Effect to fetch translation when selectedLanguage changes
  useEffect(() => {
    if (
      selectedLanguage &&
      !translations[selectedLanguage] &&
      transcript &&
      transcript.id
    ) {
      const fetchTranslation = async () => {
        setIsLoadingTranslation(true);
        try {
          const translatedTranscript = await fetchTranslatedTranscripts(
            transcript.id,
            selectedLanguage
          );
          if (translatedTranscript) {
            console.log(
              "Received translated transcript:",
              translatedTranscript
            );

            // Ensure the translated transcript has the correct structure
            if (!translatedTranscript.segments) {
              console.warn(
                "Translated transcript has no segments, creating empty array"
              );
              translatedTranscript.segments = [];
            }

            setTranslations((prev) => ({
              ...prev,
              [selectedLanguage]: translatedTranscript,
            }));
          } else {
            // Handle case where translation is not available
            console.log(`Translation for ${selectedLanguage} not found.`);
          }
        } catch (error) {
          console.error("Error fetching translation:", error);
        }
        setIsLoadingTranslation(false);
      };
      fetchTranslation();
    }
  }, [selectedLanguage, transcript, translations]);

  // Handle translation request
  const handleRequestTranslation = async (language) => {
    if (!videoId || !transcript) return;

    try {
      setTranslatingLanguage(language);

      // First get the transcript ID from the transcript object
      // In some cases, videoId might be passed as the transcript ID
      const transcriptId = transcript.id || videoId;

      console.log(
        `Requesting translation for transcript ${transcriptId} to ${language}`
      );
      const jobResponse = await createTranslationJob(transcriptId, language);
      console.log("Translation job created:", jobResponse);

      // Poll for the translation result multiple times with increasing delays
      const checkTranslation = async (attempt = 1, maxAttempts = 5) => {
        if (attempt > maxAttempts) {
          console.log("Max polling attempts reached");
          setTranslatingLanguage(null);
          return;
        }

        const delay = Math.min(attempt * 2000, 10000); // Increasing delay, max 10 seconds
        console.log(
          `Waiting ${delay}ms before checking translation (attempt ${attempt}/${maxAttempts})`
        );

        setTimeout(async () => {
          try {
            console.log(
              `Checking for translation of transcript ${transcriptId} to ${language}`
            );
            const translatedTranscript = await fetchTranslatedTranscripts(
              transcriptId,
              language
            );

            if (translatedTranscript) {
              console.log(`Translation received:`, translatedTranscript);

              // Ensure the translated transcript has the correct structure
              if (!translatedTranscript.segments) {
                console.warn(
                  "Translated transcript has no segments, creating empty array"
                );
                translatedTranscript.segments = [];
              }

              setTranslations((prev) => ({
                ...prev,
                [language]: translatedTranscript,
              }));
              setTranslatingLanguage(null);
            } else {
              // If no translation yet, try again
              console.log(`No translation available yet, trying again...`);
              checkTranslation(attempt + 1, maxAttempts);
            }
          } catch (error) {
            console.error("Error checking translation status:", error);
            if (attempt < maxAttempts) {
              checkTranslation(attempt + 1, maxAttempts);
            } else {
              setTranslatingLanguage(null);
            }
          }
        }, delay);
      };

      // Start polling
      checkTranslation();
    } catch (error) {
      console.error("Error requesting translation:", error);
      setTranslatingLanguage(null);
    }
  };

  const currentTranscriptData =
    selectedLanguage && translations[selectedLanguage]
      ? translations[selectedLanguage]
      : transcript;

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
  const segments = currentTranscriptData
    ? currentTranscriptData.segments || []
    : [];

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
    const currentSegments = currentTranscriptData
      ? currentTranscriptData.segments || []
      : [];
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
    const currentSegments = currentTranscriptData
      ? currentTranscriptData.segments || []
      : [];
    const textContent = currentSegments
      .map((segment) => {
        let line = "";
        if (
          showTimestamps &&
          showSpeaker &&
          segment.speaker &&
          !selectedLanguage
        ) {
          // Speaker info might not be in translated data
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
          Transcript{" "}
          {selectedLanguage
            ? `(${
                AVAILABLE_LANGUAGES.find((l) => l.code === selectedLanguage)
                  ?.name
              })`
            : ""}
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
                  {transcript &&
                    transcript.language_code && ( // Show original language if available
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
                    const isOriginalLanguage =
                      lang.code === transcript?.language_code;
                    const isSelected = selectedLanguage === lang.code;
                    const translationExists = !!translations[lang.code];

                    return (
                      <button
                        key={lang.code}
                        onClick={() => {
                          if (isOriginalLanguage) {
                            setSelectedLanguage(null);
                            setTranslateMenuOpen(false);
                          } else if (translationExists) {
                            setSelectedLanguage(lang.code);
                            setTranslateMenuOpen(false);
                          } else {
                            // Show confirmation modal for translation request
                            setPendingLanguage(lang.code);
                            setShowTranslationModal(true);
                            setTranslateMenuOpen(false);
                          }
                        }}
                        disabled={
                          isLoadingTranslation ||
                          (isSelected && !isOriginalLanguage)
                        }
                        className={`block w-full text-left px-4 py-2 text-sm flex items-center justify-between ${
                          (isSelected && !isOriginalLanguage) ||
                          (!selectedLanguage && isOriginalLanguage)
                            ? "bg-gray-100 dark:bg-gray-600 text-gray-900 dark:text-white"
                            : "text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                        } ${
                          isLoadingTranslation
                            ? "opacity-50 cursor-not-allowed"
                            : ""
                        }`}
                        role="menuitem"
                      >
                        <span>
                          {lang.flag} {lang.name}
                        </span>
                        {translationExists &&
                          lang.code !== transcript?.language_code && (
                            <CheckMarkIcon />
                          )}
                        {translatingLanguage === lang.code && <LoadingIcon />}
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
        {isLoadingTranslation && (
          <p className="text-gray-500 dark:text-gray-400 text-center py-4">
            Loading translated transcript...
          </p>
        )}
        {!isLoadingTranslation &&
          segments.length === 0 &&
          currentTranscriptData &&
          currentTranscriptData.content && (
            <p className="text-gray-500 dark:text-gray-400 text-center py-4">
              <span className="text-gray-800 dark:text-gray-200">
                {currentTranscriptData.content}
              </span>
            </p>
          )}
        {!isLoadingTranslation &&
          segments.length === 0 &&
          (!currentTranscriptData || !currentTranscriptData.content) && (
            <p className="text-gray-500 dark:text-gray-400 text-center py-4">
              No transcript segments available for the selected language.
            </p>
          )}
        {!isLoadingTranslation &&
          filteredSegments.length > 0 &&
          filteredSegments.map((segment, index) => (
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

      {/* Translation confirmation modal */}
      {showTranslationModal && pendingLanguage && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md mx-auto">
            <h3 className="text-lg font-semibold mb-4 text-gray-800 dark:text-white">
              Translate Transcript
            </h3>
            <p className="mb-4 text-gray-700 dark:text-gray-300">
              The transcript will be translated to{" "}
              {
                AVAILABLE_LANGUAGES.find((l) => l.code === pendingLanguage)
                  ?.name
              }
              . This may take a few moments.
            </p>
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => {
                  setShowTranslationModal(false);
                  setPendingLanguage(null);
                }}
                className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded hover:bg-gray-300 dark:hover:bg-gray-600"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  handleRequestTranslation(pendingLanguage);
                  setShowTranslationModal(false);
                  setSelectedLanguage(pendingLanguage);
                  setPendingLanguage(null);
                }}
                className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
              >
                Translate
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TranscriptList;
