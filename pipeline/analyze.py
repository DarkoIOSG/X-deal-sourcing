import anthropic
from tqdm import tqdm
from config import ANTHROPIC_API_KEY

_client = None

_MAX_TWEET_CHARS = 12000


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _analyze_tweets(tweets: list[str], bio: str = "") -> dict:
    if not tweets and not bio:
        return {"description": "", "entities": [], "account_type": "unknown",
                "sector": [], "token_status": "unknown", "stage": "unknown", "one_liner": ""}

    tweets_text = "\n".join(tweets)
    if len(tweets_text) > _MAX_TWEET_CHARS:
        tweets_text = tweets_text[:_MAX_TWEET_CHARS]

    bio_section = f"Official bio: {bio}\n\n" if bio else ""

    prompt = f"""Analyze this crypto/startup ecosystem account.

{bio_section}Tweets:
{tweets_text}

Return exactly this format:

TYPE:
[project or person]

ONE-LINER:
[one sharp sentence: what this is and why it matters, max 15 words]

DESCRIPTION:
[2-3 sentence summary of what this account focuses on — their role, key themes, perspective]

SECTOR:
[comma-separated list from: DeFi, L1, L2, AI, Gaming, NFT, Infrastructure, DAO, VC, Social, RWA, Other]

TOKEN STATUS:
[exactly one of: has token / TGE planned / no token / unknown]

STAGE:
[exactly one of: pre-seed / seed / growth / unknown]

ENTITIES:
- Entity name (type)
- Entity name (type)

Rules:
- TYPE must be exactly "project" or "person"
- SECTOR: pick only relevant ones from the list, max 3
- Entity types: project, token, VC, person, protocol, exchange, other"""

    response = _get_client().messages.create(
        model="claude-haiku-4-5",
        max_tokens=600,
        system="You analyze crypto and startup Twitter accounts for a venture capital deal-sourcing tool.",
        messages=[{"role": "user", "content": prompt}],
    )

    content = response.content[0].text.strip()

    def extract_section(text: str, start: str, end: str | None) -> str:
        if start not in text:
            return ""
        section = text.split(start)[1]
        if end and end in section:
            section = section.split(end)[0]
        return section.strip()

    account_type = "unknown"
    type_raw = extract_section(content, "TYPE:", "ONE-LINER:").lower()
    if "project" in type_raw:
        account_type = "project"
    elif "person" in type_raw:
        account_type = "person"

    one_liner = extract_section(content, "ONE-LINER:", "DESCRIPTION:")
    description = extract_section(content, "DESCRIPTION:", "SECTOR:")

    sector_raw = extract_section(content, "SECTOR:", "TOKEN STATUS:")
    sector = [s.strip() for s in sector_raw.split(",") if s.strip()] if sector_raw else []

    token_status_raw = extract_section(content, "TOKEN STATUS:", "STAGE:").lower()
    if "has token" in token_status_raw:
        token_status = "has token"
    elif "tge planned" in token_status_raw:
        token_status = "TGE planned"
    elif "no token" in token_status_raw:
        token_status = "no token"
    else:
        token_status = "unknown"

    stage_raw = extract_section(content, "STAGE:", "ENTITIES:").lower()
    if "pre-seed" in stage_raw:
        stage = "pre-seed"
    elif "seed" in stage_raw:
        stage = "seed"
    elif "growth" in stage_raw:
        stage = "growth"
    else:
        stage = "unknown"

    entities = []
    entities_raw = extract_section(content, "ENTITIES:", None)
    for line in entities_raw.splitlines():
        line = line.strip("- ").strip()
        if line:
            entities.append(line)

    return {
        "description": description,
        "entities": entities,
        "account_type": account_type,
        "one_liner": one_liner,
        "sector": sector,
        "token_status": token_status,
        "stage": stage,
    }


def analyze_accounts(accounts: list[dict]) -> list[dict]:
    for account in tqdm(accounts, desc="Analyzing tweets"):
        try:
            result = _analyze_tweets(account.get("tweet_texts", []), account.get("description", ""))
            account["tweet_analysis"] = result["description"]
            account["entities"] = result["entities"]
            account["account_type"] = result["account_type"]
            account["one_liner"] = result["one_liner"]
            account["sector"] = result["sector"]
            account["token_status"] = result["token_status"]
            account["stage"] = result["stage"]
        except Exception as e:
            print(f"  [warn] analysis failed for {account.get('username', account['id'])}: {e}")
            account["tweet_analysis"] = ""
            account["entities"] = []
            account["account_type"] = "unknown"
            account["one_liner"] = ""
            account["sector"] = []
            account["token_status"] = "unknown"
            account["stage"] = "unknown"
    return accounts
