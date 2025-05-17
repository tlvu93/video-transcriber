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
