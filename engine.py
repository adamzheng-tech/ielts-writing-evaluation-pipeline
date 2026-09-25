import asyncio
import json
import math
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from schema import DimensionEvaluation, FullEvaluationPayload, ImageInput, TaskType


load_dotenv()

SHARED_CRITERIA = {
    "Coherence and Cohesion": "Evaluate organisation, progression, paragraphing, cohesion and referencing.",
    "Lexical Resource": "Evaluate vocabulary range, precision, appropriacy, collocation, spelling and word formation.",
    "Grammatical Range and Accuracy": "Evaluate sentence variety, grammatical accuracy and punctuation.",
}

TASK_CRITERIA = {
    "task_1": (
        "Task Achievement",
        "Evaluate coverage of task requirements, selection of key features, sufficient detail, factual accuracy, comparisons and format.",
    ),
    "task_2": (
        "Task Response",
        "Evaluate whether all parts of the prompt are addressed, the position is clear and developed, and ideas are relevant, extended and supported.",
    ),
}


class IELTSDimensionEvaluator:
    def __init__(self, client: AsyncOpenAI, dimension_name: str, criteria: str, model: str):
        self.client = client
        self.dimension_name = dimension_name
        self.criteria = criteria
        self.model = model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def _call_llm_with_retry(self, system_prompt: str, user_content: list) -> tuple[dict, int]:
        response = await self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            temperature=0.0,
            timeout=15.0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        content = json.loads(response.choices[0].message.content)
        tokens_used = response.usage.total_tokens if response.usage else 0
        return content, tokens_used

    async def evaluate(self, essay_text: str, images: list[ImageInput] | None = None) -> tuple[dict, int]:
        schema_definition = DimensionEvaluation.model_json_schema()
        system_prompt = (
            "You are an IELTS writing evaluator. Evaluate only this dimension: "
            f"{self.dimension_name}. Criteria: {self.criteria}\n"
            "Return one JSON object matching this schema. Include only passages that require correction in diagnostics.\n"
            f"{json.dumps(schema_definition)}"
        )
        user_content = [{"type": "text", "text": f"Evaluate this response:\n{essay_text}"}]
        if images and self.dimension_name == "Task Achievement":
            for image in images:
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{image.media_type};base64,{image.data_base64}"},
                })
        raw_result, tokens = await self._call_llm_with_retry(system_prompt, user_content)
        raw_result["dimension_name"] = self.dimension_name
        validated = DimensionEvaluation.model_validate(raw_result)
        return validated.model_dump(), tokens


class EssayAnalyzer:
    def __init__(self, client: AsyncOpenAI | None = None, model: str | None = None):
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("POIXE_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.poixe.com/v1")
        if client is None and not api_key:
            raise RuntimeError("Missing OPENAI_API_KEY or POIXE_API_KEY")
        self.client = client or AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model or os.getenv("OPENAI_MODEL_NAME", "gpt-4o")

    def _build_evaluators(self, task_type: TaskType) -> list[IELTSDimensionEvaluator]:
        first_name, first_criteria = TASK_CRITERIA[task_type]
        criteria = {first_name: first_criteria, **SHARED_CRITERIA}
        return [
            IELTSDimensionEvaluator(self.client, name, description, self.model)
            for name, description in criteria.items()
        ]

    async def analyze(
        self,
        task_type: TaskType,
        essay_text: str,
        images: list[ImageInput] | None = None,
    ) -> FullEvaluationPayload:
        if task_type == "task_2" and images:
            raise ValueError("Task 2 does not accept prompt images")
        evaluators = self._build_evaluators(task_type)
        results = await asyncio.gather(*(item.evaluate(essay_text, images) for item in evaluators))
        evaluations = [DimensionEvaluation.model_validate(result) for result, _ in results]
        total_tokens = sum(tokens for _, tokens in results)
        average = sum(item.band_score for item in evaluations) / len(evaluations)
        return FullEvaluationPayload(
            task_type=task_type,
            overall_band=self._ielts_round(average),
            total_tokens=total_tokens,
            evaluations=evaluations,
        )

    @staticmethod
    def _ielts_round(score: float) -> float:
        floor_value = math.floor(score)
        remainder = score - floor_value
        if remainder < 0.25:
            return float(floor_value)
        if remainder < 0.75:
            return float(floor_value + 0.5)
        return float(floor_value + 1)
