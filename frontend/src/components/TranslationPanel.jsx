import { useState, useEffect } from "react";
import {
  fetchTranslatedTranscripts,
  createTranslationJob,
} from "../api/videoService";

const TranslationPanel = ({ transcript }) => {
  const [translations, setTranslations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [targetLanguage, setTargetLanguage] = useState("de"); // Default to German
  const [translationInProgress, setTranslationInProgress] = useState(false);
  const [selectedTranslation, setSelectedTranslation] = useState(null);
  const [showTranslation, setShowTranslation] = useState(false);

  // Language options
  const languageOptions = [
    { code: "de", name: "German" },
    { code: "fr", name: "French" },
    { code: "es", name: "Spanish" },
    { code: "it", name: "Italian" },
    { code: "ja", name: "Japanese" },
    { code: "zh", name: "Chinese" },
    { code: "ru", name: "Russian" },
    { code: "ar", name: "Arabic" },
    { code: "hi", name: "Hindi" },
    { code: "pt", name: "Portuguese" },
  ];

  // Fetch existing translations when transcript changes
  useEffect(() => {
    if (transcript && transcript.id) {
      fetchTranslations();
    }
  }, [transcript]);

  // Fetch translations for the current transcript
  const fetchTranslations = async () => {
    if (!transcript || !transcript.id) return;

    try {
      setLoading(true);
      const data = await fetchTranslatedTranscripts(transcript.id);
      setTranslations(data);
      setLoading(false);
    } catch (err) {
      console.error("Error fetching translations:", err);
      setError("Failed to load translations");
      setLoading(false);
    }
  };

  // Request a new translation
  const handleRequestTranslation = async () => {
    if (!transcript || !transcript.id) return;

    try {
      setTranslationInProgress(true);
      setError(null);

      // Check if translation already exists
      const existingTranslation = translations.find(
        (t) => t.language === targetLanguage
      );

      if (existingTranslation) {
        setError(
          `A translation in ${getLanguageName(targetLanguage)} already exists`
        );
        setTranslationInProgress(false);
        return;
      }

      // Create a new translation job
      await createTranslationJob(transcript.id, targetLanguage);

      // Show success message
      alert(
        `Translation to ${getLanguageName(
          targetLanguage
        )} requested. This may take a few minutes.`
      );

      // Refresh translations after a delay to allow time for processing
      setTimeout(() => {
        fetchTranslations();
        setTranslationInProgress(false);
      }, 5000);
    } catch (err) {
      console.error("Error requesting translation:", err);
      setError("Failed to request translation");
      setTranslationInProgress(false);
    }
  };

  // Get language name from code
  const getLanguageName = (code) => {
    const language = languageOptions.find((lang) => lang.code === code);
    return language ? language.name : code;
  };

  // Handle translation selection
  const handleTranslationSelect = (translation) => {
    setSelectedTranslation(translation);
    setShowTranslation(true);
  };

  // Render translation content
  const renderTranslationContent = () => {
    if (!selectedTranslation) return null;

    if (
      selectedTranslation.segments &&
      selectedTranslation.segments.length > 0
    ) {
      return (
        <div className="mt-4 max-h-96 overflow-y-auto">
          {selectedTranslation.segments.map((segment) => (
            <div key={segment.id} className="mb-2 p-2 bg-gray-50 rounded">
              <p>{segment.text}</p>
              {segment.start_time !== undefined && (
                <span className="text-xs text-gray-500">
                  {formatTime(segment.start_time)} -{" "}
                  {formatTime(segment.end_time)}
                </span>
              )}
            </div>
          ))}
        </div>
      );
    } else {
      return (
        <div className="mt-4 p-4 bg-gray-50 rounded">
          <p>{selectedTranslation.content}</p>
        </div>
      );
    }
  };

  // Format time in seconds to MM:SS format
  const formatTime = (seconds) => {
    if (seconds === undefined || seconds === null) return "00:00";

    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, "0")}:${secs
      .toString()
      .padStart(2, "0")}`;
  };

  if (!transcript) {
    return null;
  }

  return (
    <div className="bg-white shadow rounded-lg p-4 mt-4">
      <h2 className="text-xl font-semibold mb-4">Translations</h2>

      {/* Translation request form */}
      <div className="mb-4 p-3 bg-gray-50 rounded">
        <h3 className="text-md font-medium mb-2">Request Translation</h3>
        <div className="flex flex-col sm:flex-row gap-2">
          <select
            className="border rounded p-2 flex-grow"
            value={targetLanguage}
            onChange={(e) => setTargetLanguage(e.target.value)}
            disabled={translationInProgress}
          >
            {languageOptions.map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.name}
              </option>
            ))}
          </select>
          <button
            className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded"
            onClick={handleRequestTranslation}
            disabled={translationInProgress}
          >
            {translationInProgress ? "Processing..." : "Translate"}
          </button>
        </div>
        {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
      </div>

      {/* Available translations */}
      <div>
        <h3 className="text-md font-medium mb-2">Available Translations</h3>
        {loading ? (
          <p className="text-gray-500">Loading translations...</p>
        ) : translations.length > 0 ? (
          <div>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 mb-4">
              {translations.map((translation) => (
                <button
                  key={translation.id}
                  className={`p-2 border rounded hover:bg-gray-100 ${
                    selectedTranslation?.id === translation.id
                      ? "bg-blue-100 border-blue-300"
                      : ""
                  }`}
                  onClick={() => handleTranslationSelect(translation)}
                >
                  {getLanguageName(translation.language)}
                </button>
              ))}
            </div>

            {/* Show selected translation */}
            {showTranslation && selectedTranslation && (
              <div className="mt-4">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="text-md font-medium">
                    {getLanguageName(selectedTranslation.language)} Translation
                  </h3>
                  <button
                    className="text-sm text-gray-500 hover:text-gray-700"
                    onClick={() => setShowTranslation(false)}
                  >
                    Hide
                  </button>
                </div>
                {renderTranslationContent()}
              </div>
            )}
          </div>
        ) : (
          <p className="text-gray-500">No translations available</p>
        )}
      </div>
    </div>
  );
};

export default TranslationPanel;
