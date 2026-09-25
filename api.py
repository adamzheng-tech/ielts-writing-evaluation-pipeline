import logging
import os

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
import uvicorn

from engine import EssayAnalyzer
from repository import TelemetryRepository
from schema import EvaluationRequest, FullEvaluationPayload


load_dotenv()
logger = logging.getLogger(__name__)
app = FastAPI(title="IELTS Evaluation Engine", version="2.1.0")
repo = TelemetryRepository(os.getenv("TELEMETRY_DB_PATH", "telemetry.db"))
_analyzer: EssayAnalyzer | None = None


def get_analyzer() -> EssayAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = EssayAnalyzer()
    return _analyzer


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/evaluate")
async def evaluate_essay(payload: EvaluationRequest, background_tasks: BackgroundTasks):
    try:
        result: FullEvaluationPayload = await get_analyzer().analyze(
            task_type=payload.task_type,
            essay_text=payload.essay_text,
            images=payload.images,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("IELTS evaluation failed")
        raise HTTPException(status_code=502, detail="Evaluation service failed") from exc

    background_tasks.add_task(
        repo.save_evaluation,
        student_id=payload.student_id,
        overall_band=result.overall_band,
        total_tokens=result.total_tokens,
        payload=result.model_dump(),
    )
    return {"status": "success", "student_id": payload.student_id, "data": result.model_dump()}


if __name__ == "__main__":
    uvicorn.run("api:app", host="127.0.0.1", port=8000)
