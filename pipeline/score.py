import json
from pathlib import Path
import anthropic
from config import ANTHROPIC_API_KEY

_client = None
THESIS_PATH = Path("thesis.md")

_PROMPT = """\
You are scoring a new project against the fund's investment thesis.

THESIS DOCUMENT:
{thesis_doc}

PROJECT:
- Handle: {handle}
- Description: {description}
- Categories: {categories}
- Tweet analysis / recent activity:
{tweets_joined}

Output ONLY valid JSON, no preamble:

{{
  "thesis_fit_score": 0-100,
  "primary_thesis_match": "<name of active thesis from doc, or 'none'>",
  "category_fit": "strong" | "moderate" | "weak" | "none",
  "investment_pattern_matches": ["<names of yes-patterns from doc>"],
  "pass_pattern_matches": ["<names of pass-patterns or anti-patterns>"],
  "hard_disqualifiers": ["<any that apply, empty if none>"],
  "top_reasons": ["<3 specific reasons grounded in the tweets/description>"],
  "top_red_flags": ["<up to 3 specific concerns>"],
  "open_debate_relevance": "<name of an Open Debate from doc, or null>",
  "recommendation": "deep_dive" | "watch" | "pass",
  "one_line_summary": "<pitch in the fund's own vocabulary>"
}}

Rules:
- Ground every reason and red flag in specific tweet content or description text. No generic VC statements.
- Any hard_disqualifier => recommendation MUST be "pass".
- category_fit "none" AND primary_thesis_match "none" => recommendation MUST be "pass".
- The score should reflect both fit AND signal strength: do the tweets demonstrate the thesis-relevant traits, or just claim them? Demonstrated > claimed.
- Use the fund's vocabulary from the thesis doc.\
"""

_FALLBACK = {
    "thesis_fit_score": 0,
    "primary_thesis_match": "none",
    "category_fit": "none",
    "investment_pattern_matches": [],
    "pass_pattern_matches": [],
    "hard_disqualifiers": [],
    "top_reasons": [],
    "top_red_flags": ["scoring failed — JSON parse error"],
    "open_debate_relevance": None,
    "recommendation": "pass",
    "one_line_summary": "scoring error",
}


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _load_thesis() -> str:
    if THESIS_PATH.exists():
        return THESIS_PATH.read_text()
    return "[thesis.md not found — add it to the project root]"


def score_project(page: dict) -> dict:
    description = page.get("description", "") or page.get("one_liner", "")
    one_liner   = page.get("one_liner", "")
    # Use tweet analysis from Notion (already generated during discovery enrichment)
    # Format as bullet if non-empty so the prompt structure is preserved
    tweet_context = description or one_liner or "(no analysis available)"
    tweets_joined = f"- {tweet_context}" if tweet_context else "(no analysis available)"
    categories = ", ".join(page.get("sectors", [])) or "unknown"

    prompt = _PROMPT.format(
        thesis_doc=_load_thesis(),
        handle=page.get("username", "unknown"),
        description=one_liner or description,
        categories=categories,
        tweets_joined=tweets_joined,
    )

    resp = _get_client().messages.create(
        model="claude-haiku-4-5",
        max_tokens=1000,
        system="You are a venture capital analyst. Output only valid JSON, no markdown fences.",
        messages=[{"role": "user", "content": prompt}],
    )

    text = resp.content[0].text.strip()
    # Strip accidental markdown fences
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        result = dict(_FALLBACK)
        result["_raw"] = text[:500]
        return result
