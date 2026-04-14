from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class JobStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalyzeRequest(BaseModel):
    target_role: Optional[str] = Field(
        default=None,
        description="Optional target role to focus the job search (e.g. 'Data Engineer')"
    )


class AnalyzeResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class ResumeProfile(BaseModel):
    skills: list[str]
    inferred_skills: list[str] = []
    seniority: str
    years_of_experience: Optional[int] = None
    summary: str
    raw_text: str


class JobPosting(BaseModel):
    title: str
    company: str
    url: str
    description: str
    required_skills: list[str]
    source: str  # remoteok / adzuna


class GapAnalysis(BaseModel):
    missing_skills: list[str]
    keyword_gaps: list[str]
    strengths: list[str]
    match_score: float = Field(..., ge=0.0, le=1.0)


class Report(BaseModel):
    gap_analysis: GapAnalysis
    recommendations: list[str]
    jobs_analyzed: int
    top_jobs: list[JobPosting]


class ResultsResponse(BaseModel):
    job_id: str
    status: JobStatus
    resume_profile: Optional[ResumeProfile] = None
    report: Optional[Report] = None
    error: Optional[str] = None


# LangGraph agent state — the dict that flows through every node
class AgentState(BaseModel):
    job_id: str
    target_role: Optional[str] = None
    resume_bytes: bytes = b""
    resume_profile: Optional[ResumeProfile] = None
    job_postings: list[JobPosting] = []
    gap_analysis: Optional[GapAnalysis] = None
    report: Optional[Report] = None
    error: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
