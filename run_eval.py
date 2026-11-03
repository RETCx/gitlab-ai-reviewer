import getpass
import os
from pathlib import Path
from time import perf_counter
import sys

from review_diff import review_diff

diff_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("evals/cases/01_buggy_average.diff")
diff = diff_path.read_text(encoding="utf-8")
api_key = os.environ.get("OPENROUTER_API_KEY") or getpass.getpass("OpenRouter API key: ")
model = os.environ.get("OPENROUTER_MODEL", "openai/gpt-5-mini")

started = perf_counter()
review = review_diff(diff, api_key, model)

print(review.model_dump_json(indent=2))
print(f"Duration: {perf_counter() - started:.2f}s")