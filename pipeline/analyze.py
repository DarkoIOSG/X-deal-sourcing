import anthropic
from tqdm import tqdm
from config import ANTHROPIC_API_KEY

_client = None

# ~3500 tokens of tweet content keeps total request well under context limits
_MAX_TWEET_CHARS = 12000


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _analyze_tweets(tweets: list[str]) -> tuple[str, list[str], str]:
    if not tweets:
        return "", [], "unknown"

    tweets_text = "\n".join(tweets)
    if len(tweets_text) > _MAX_TWEET_CHARS:
        tweets_text = tweets_text[:_MAX_TWEET_CHARS]

    prompt = f"""Analyze these tweets from a crypto/startup ecosystem account.

Return exactly this format:

TYPE:
[project or person]

DESCRIPTION:
[2-3 sentence summary of what this account focuses on — their role, key themes, perspective]

ENTITIES:
- Entity name (type)
- Entity name (type)

Rules:
- TYPE must be exactly "project" (company, protocol, DAO, fund) or "person" (individual)
- Entity types: project, token, VC, person, protocol, exchange, other

Tweets:
{tweets_text}"""

    response = _get_client().messages.create(
        model="claude-haiku-4-5",
        max_tokens=400,
        system="You analyze crypto and startup Twitter accounts for a venture capital deal-sourcing tool.",
        messages=[{"role": "user", "content": prompt}],
    )

    content = response.content[0].text.strip()

    account_type = "unknown"
    if "TYPE:" in content:
        type_section = content.split("TYPE:")[1].split("DESCRIPTION:")[0].strip().lower()
        if "project" in type_section:
            account_type = "project"
        elif "person" in type_section:
            account_type = "person"

    description = ""
    if "DESCRIPTION:" in content:
        desc_section = content.split("DESCRIPTION:")[1]
        description = desc_section.split("ENTITIES:")[0].strip()

    entities = []
    if "ENTITIES:" in content:
        for line in content.split("ENTITIES:")[1].strip().splitlines():
            line = line.strip("- ").strip()
            if line:
                entities.append(line)

    return description, entities, account_type


def analyze_accounts(accounts: list[dict]) -> list[dict]:
    for account in tqdm(accounts, desc="Analyzing tweets"):
        try:
            description, entities, account_type = _analyze_tweets(account.get("tweet_texts", []))
            account["tweet_analysis"] = description
            account["entities"] = entities
            account["account_type"] = account_type
        except Exception as e:
            print(f"  [warn] analysis failed for {account.get('username', account['id'])}: {e}")
            account["tweet_analysis"] = ""
            account["entities"] = []
            account["account_type"] = "unknown"
    return accounts
