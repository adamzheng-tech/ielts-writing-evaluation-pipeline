import asyncio
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest

from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# The execution environment for this test artifact does not ship the network
# client dependencies. These stubs make the local domain logic importable;
# no network call is performed.
dotenv = types.ModuleType("dotenv")
dotenv.load_dotenv = lambda: None
sys.modules.setdefault("dotenv", dotenv)

openai = types.ModuleType("openai")
openai.AsyncOpenAI = object
sys.modules.setdefault("openai", openai)

tenacity = types.ModuleType("tenacity")
tenacity.retry = lambda *args, **kwargs: lambda function: function
tenacity.stop_after_attempt = lambda *args, **kwargs: None
tenacity.wait_exponential = lambda *args, **kwargs: None
sys.modules.setdefault("tenacity", tenacity)

requests = types.ModuleType("requests")
requests.post = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("network disabled in tests"))
sys.modules.setdefault("requests", requests)

from client import parse_payload
from engine import EssayAnalyzer, IELTSDimensionEvaluator
from repository import TelemetryRepository
from schema import DimensionEvaluation, ImageInput


class PipelineTests(unittest.TestCase):
    def test_band_score_validation(self):
        DimensionEvaluation(dimension_name="Task Response", band_score=7.5)
        for invalid in (-0.5, 7.3, 9.5):
            with self.assertRaises(ValidationError):
                DimensionEvaluation(dimension_name="Task Response", band_score=invalid)

    def test_task_routing_and_images(self):
        analyzer = EssayAnalyzer(client=object(), model="fake")
        task_1 = analyzer._build_evaluators("task_1")
        task_2 = analyzer._build_evaluators("task_2")
        self.assertEqual(task_1[0].dimension_name, "Task Achievement")
        self.assertEqual(task_2[0].dimension_name, "Task Response")

        captured = []

        async def fake_call(_prompt, content):
            captured.extend(content)
            return {"band_score": 7.0, "diagnostics": []}, 12

        task_1[0]._call_llm_with_retry = fake_call
        image = ImageInput(data_base64="aW1hZ2U=", media_type="image/png")
        asyncio.run(task_1[0].evaluate("essay", [image]))
        self.assertEqual(captured[1]["type"], "image_url")
        self.assertTrue(captured[1]["image_url"]["url"].startswith("data:image/png;base64,"))

        with self.assertRaisesRegex(ValueError, "does not accept"):
            asyncio.run(analyzer.analyze("task_2", "essay", [image]))

    def test_markdown_parser_preserves_horizontal_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "essay.md"
            path.write_text(
                "---\nstudent_id: demo\ntask_type: task_2\n---\n"
                "# Prompt Text\nDiscuss both views.\n"
                "# Essay Text\nFirst paragraph.\n---\nSecond paragraph.\n",
                encoding="utf-8",
            )
            payload = parse_payload(str(path))
        self.assertEqual(payload["task_type"], "task_2")
        self.assertIn("Second paragraph.", payload["essay_text"])

    def test_repository_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "telemetry.db"
            repository = TelemetryRepository(str(db))
            payload = {"task_type": "task_1", "overall_band": 7.0}
            repository.save_evaluation("demo", 7.0, 48, payload)
            with sqlite3.connect(db) as connection:
                row = connection.execute(
                    "SELECT student_id, overall_band, total_tokens, payload FROM evaluations"
                ).fetchone()
        self.assertEqual(row[:3], ("demo", 7.0, 48))
        self.assertEqual(json.loads(row[3]), payload)

    def test_official_quarter_rounding(self):
        self.assertEqual(EssayAnalyzer._ielts_round(6.125), 6.0)
        self.assertEqual(EssayAnalyzer._ielts_round(6.25), 6.5)
        self.assertEqual(EssayAnalyzer._ielts_round(6.75), 7.0)


if __name__ == "__main__":
    unittest.main()
