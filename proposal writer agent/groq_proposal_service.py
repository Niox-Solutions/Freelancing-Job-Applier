import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from textwrap import dedent
from typing import Any


MAIN_DIR = Path(__file__).resolve().parent.parent
if str(MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_DIR))

from config import (  # noqa: E402
    DEFAULT_PROPOSAL_COST_USD,
    DEFAULT_PROPOSAL_PERIOD_DAYS,
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_CALL_INTERVAL_SECONDS,
    PROPOSAL_MODEL,
)

_groq_call_lock = threading.Lock()
_last_groq_call_at = 0.0


def build_proposal_prompt(project: dict) -> str:
    return dedent(
        f"""
        Write a strong freelance proposal for this Nafezly project and choose
        practical offer form values.

        Project title:
        {project.get("project_title") or "Not provided"}

        Project description:
        {project.get("project_description") or "Not provided"}

        Requirements:
        - Return ONLY a valid JSON object.
        - The JSON object must have exactly these keys:
          "proposal": string,
          "period": integer from 1 to 90,
          "cost": integer from 10 to 100.
        - Write in Arabic unless the project description is clearly in another language.
        - Keep it professional, direct, and human.
        - Start with a short greeting.
        - Mention that you understood the client's exact need.
        - Explain briefly how you will solve it.
        - Include 3 concise bullet points for what you will deliver.
        - End with a confident call to action.
        - Do not invent portfolio links, prices, timelines, or personal facts.
        - Do not use markdown headings.
        - Choose period and cost based on the project scope. If uncertain, use
          period={DEFAULT_PROPOSAL_PERIOD_DAYS} and cost={DEFAULT_PROPOSAL_COST_USD}.
        """
    ).strip()


def generate_proposal_data_sync(project: dict) -> dict:
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Set it in your environment before running the agent."
        )

    payload = {
        "model": PROPOSAL_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert freelance proposal writer. "
                    "Your proposals are specific, concise, and persuasive."
                ),
            },
            {"role": "user", "content": build_proposal_prompt(project)},
        ],
        "temperature": 0.7,
        "max_tokens": 700,
        "response_format": {"type": "json_object"},
    }

    start_time = time.perf_counter()
    response = groq_chat_completion_with_retry(payload)
    elapsed_ms = round((time.perf_counter() - start_time) * 1000)
    print(f"Groq proposal generated in {elapsed_ms}ms using {PROPOSAL_MODEL}.")

    raw_content = (
        response.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    if not raw_content.strip():
        raise RuntimeError("Groq returned an empty proposal.")

    return normalize_proposal_data(raw_content)


def generate_proposal_sync(project: dict) -> str:
    return generate_proposal_data_sync(project)["proposal"]


def normalize_proposal_data(raw_content: str) -> dict:
    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Groq returned invalid JSON: {raw_content[:300]}") from exc

    proposal = str(data.get("proposal", "")).strip()
    if not proposal:
        raise RuntimeError("Groq JSON did not include a proposal.")

    return {
        "proposal": proposal,
        "period": clamp_int(
            data.get("period"),
            minimum=1,
            maximum=90,
            default=DEFAULT_PROPOSAL_PERIOD_DAYS,
        ),
        "cost": clamp_int(
            data.get("cost"),
            minimum=10,
            maximum=100,
            default=DEFAULT_PROPOSAL_COST_USD,
        ),
    }


def clamp_int(value, *, minimum: int, maximum: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default

    return max(minimum, min(maximum, number))


def groq_chat_completion_with_retry(
    payload: dict,
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> dict[str, Any]:
    for attempt in range(max_retries):
        try:
            return groq_chat_completion(payload)
        except urllib.error.HTTPError as exc:
            if attempt == max_retries - 1 or exc.code not in {429, 500, 502, 503}:
                raise

            delay = base_delay * (2**attempt)
            print(
                "Groq API call failed, retrying "
                f"attempt={attempt + 1}/{max_retries} delay={delay:.1f}s "
                f"status={exc.code}"
            )
            time.sleep(delay)
        except urllib.error.URLError:
            if attempt == max_retries - 1:
                raise

            delay = base_delay * (2**attempt)
            print(
                "Groq API connection failed, retrying "
                f"attempt={attempt + 1}/{max_retries} delay={delay:.1f}s"
            )
            time.sleep(delay)

    raise RuntimeError("Groq API call failed.")


def groq_chat_completion(payload: dict) -> dict[str, Any]:
    wait_for_groq_call_interval()
    url = f"{GROQ_BASE_URL.rstrip('/')}/chat/completions"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "OpenAI/Python 1.0",
        },
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_groq_call_interval() -> None:
    global _last_groq_call_at

    with _groq_call_lock:
        elapsed = time.monotonic() - _last_groq_call_at
        delay = max(0.0, GROQ_CALL_INTERVAL_SECONDS - elapsed)
        if delay:
            print(f"Waiting {delay:.1f}s before the next Groq API call.")
            time.sleep(delay)
        _last_groq_call_at = time.monotonic()
