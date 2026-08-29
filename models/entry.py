from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class GrowthEntry(BaseModel):
    date: str = Field(..., description="ISO date string, e.g. 2024-01-15")
    entry_type: Literal["mistake", "win", "learning", "reflection", "insight"] = Field(
        ..., description="Nature of the experience"
    )
    context: str = Field(..., description="Situation or circumstances surrounding the experience")
    skill_area: str = Field(..., description="Skill or domain involved — gap to close or strength to build on")
    insight: str = Field(..., description="Key takeaway: what you learned, realized, or want to remember")
    emotion: str = Field(..., description="How you felt during or after the experience")
    project: str = Field(..., description="Project, role, or life area where this occurred")
    impact: Optional[str] = Field(None, description="What changed or what you did differently as a result")
    tags: List[str] = Field(default_factory=list, description="Free-form tags for filtering and grouping")
