from typing import Annotated, Literal

from pydantic import BaseModel, Field


TaskType = Literal["task_1", "task_2"]
BandScore = Annotated[float, Field(ge=0.0, le=9.0, multiple_of=0.5)]


class ImageInput(BaseModel):
    data_base64: str = Field(min_length=1)
    media_type: Literal["image/jpeg", "image/png", "image/webp"]


class EvaluationRequest(BaseModel):
    student_id: str = Field(min_length=1, max_length=100)
    task_type: TaskType
    essay_text: str = Field(min_length=1)
    images: list[ImageInput] = Field(default_factory=list)


class DiagnosticItem(BaseModel):
    error_pattern: str
    example_from_text: str
    how_to_fix_it: str


class DimensionEvaluation(BaseModel):
    dimension_name: str
    band_score: BandScore
    diagnostics: list[DiagnosticItem] = Field(default_factory=list)


class FullEvaluationPayload(BaseModel):
    task_type: TaskType
    overall_band: BandScore
    total_tokens: int = Field(ge=0)
    evaluations: list[DimensionEvaluation] = Field(min_length=4, max_length=4)
