import axios from "axios";

const API_URL = "/api";

export const fetchVideos = async () => {
  try {
    const response = await axios.get(`${API_URL}/videos/`);
    return response.data;
  } catch (error) {
    console.error("Error fetching videos:", error);
    throw error;
  }
};

export const fetchVideoById = async (videoId) => {
  try {
    const response = await axios.get(`${API_URL}/videos/${videoId}`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching video with ID ${videoId}:`, error);
    throw error;
  }
};

export const fetchTranscriptsByVideoId = async (videoId) => {
  try {
    const response = await axios.get(
      `${API_URL}/transcripts/?video_id=${videoId}`
    );
    return response.data;
  } catch (error) {
    console.error(`Error fetching transcripts for video ID ${videoId}:`, error);
    throw error;
  }
};

export const downloadTranscript = async (transcriptId) => {
  try {
    const response = await axios.get(`${API_URL}/transcripts/${transcriptId}`);
    return response.data;
  } catch (error) {
    console.error(
      `Error downloading transcript with ID ${transcriptId}:`,
      error
    );
    throw error;
  }
};

export const fetchSummariesByTranscriptId = async (transcriptId) => {
  try {
    const response = await axios.get(
      `${API_URL}/summaries/?transcript_id=${transcriptId}`
    );
    return response.data;
  } catch (error) {
    console.error(
      `Error fetching summaries for transcript ID ${transcriptId}:`,
      error
    );
    throw error;
  }
};

export const fetchTranscriptionJobs = async (videoId) => {
  try {
    // This is a placeholder - the API doesn't currently have an endpoint to fetch jobs by video ID
    // You would need to add this endpoint to the API if needed
    console.warn("fetchTranscriptionJobs is not fully implemented");
    return [];
  } catch (error) {
    console.error(
      `Error fetching transcription jobs for video ID ${videoId}:`,
      error
    );
    throw error;
  }
};

export const retryTranscriptionJob = async (jobId) => {
  try {
    const response = await axios.post(
      `${API_URL}/transcription-jobs/${jobId}/retry`
    );
    return response.data;
  } catch (error) {
    console.error(`Error retrying transcription job with ID ${jobId}:`, error);
    throw error;
  }
};
