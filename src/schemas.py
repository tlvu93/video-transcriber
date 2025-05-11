from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
import uuid

# Base schemas
class VideoBase(BaseModel):
    filename: str
    status: Optional[str] = "pending"
    duration_seconds: Optional[float] = None
    language: Optional[str] = None
    file_type: Optional[str] = None
    resolution_width: Optional[int] = None
    resolution_height: Optional[int] = None

class TranscriptBase(BaseModel):
    source_type: str = "video"
    format: str = "txt"
    status: Optional[str] = "pending"

class SummaryBase(BaseModel):
    status: Optional[str] = "pending"

class JobBase(BaseModel):
    status: str = "pending"
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None

# Create schemas
class VideoCreate(VideoBase):
    file_hash: str

class TranscriptCreate(TranscriptBase):
    video_id: Optional[uuid.UUID] = None
    content: str

class SummaryCreate(SummaryBase):
    transcript_id: uuid.UUID
    content: str

# Update schemas
class VideoUpdate(BaseModel):
    status: Optional[str] = None
    video_metadata: Optional[Dict[str, Any]] = None  # Renamed from 'metadata'
    language: Optional[str] = None

class TranscriptUpdate(BaseModel):
    content: Optional[str] = None
    status: Optional[str] = None

class SummaryUpdate(BaseModel):
    content: Optional[str] = None
    status: Optional[str] = None

# Response schemas
class TranscriptionJobResponse(JobBase):
    id: uuid.UUID
    video_id: uuid.UUID

    class Config:
        orm_mode = True

class SummarizationJobResponse(JobBase):
    id: uuid.UUID
    transcript_id: uuid.UUID

    class Config:
        orm_mode = True

class TranscriptResponse(TranscriptBase):
    id: uuid.UUID
    video_id: Optional[uuid.UUID] = None
    content: str
    created_at: datetime
    updated_at: datetime
    summarization_jobs: List[SummarizationJobResponse] = []

    class Config:
        orm_mode = True

class SummaryResponse(SummaryBase):
    id: uuid.UUID
    transcript_id: uuid.UUID
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class VideoResponse(VideoBase):
    id: uuid.UUID
    file_hash: str
    created_at: datetime
    updated_at: datetime
    video_metadata: Optional[Dict[str, Any]] = None  # Renamed from 'metadata'
    transcription_jobs: List[TranscriptionJobResponse] = []

    class Config:
        orm_mode = True

class VideoDetailResponse(VideoResponse):
    transcripts: List[TranscriptResponse] = []

    class Config:
        orm_mode = True

# Analytics schemas
class AnalyticsOverview(BaseModel):
    total_videos: int
    successful_videos: int
    failed_videos: int
    success_rate: float
    avg_transcription_time: float
    avg_summarization_time: float
    avg_total_time: float

class TranscriptionStats(BaseModel):
    total_transcriptions: int
    successful_transcriptions: int
    failed_transcriptions: int
    success_rate: float
    avg_processing_time: float
    processing_time_by_duration: Dict[str, float]  # e.g. {"0-60s": 10.5, "60-300s": 30.2, ...}

class SummarizationStats(BaseModel):
    total_summarizations: int
    successful_summarizations: int
    failed_summarizations: int
    success_rate: float
    avg_processing_time: float

class ProcessingTrend(BaseModel):
    date: str
    transcription_count: int
    summarization_count: int
    avg_transcription_time: float
    avg_summarization_time: float

class AnalyticsTrends(BaseModel):
    trends: List[ProcessingTrend]
