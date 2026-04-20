import time
from datetime import datetime
from tqdm import tqdm
from api.sorsa import get_profiles_batch, get_user_tweets


def _parse_tweet_date(value: str) -> str:
    if not value:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%a %b %d %H:%M:%S %z %Y"):
        try:
            return datetime.strptime(value.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value[:10]


def enrich_profiles(accounts: list[dict]) -> list[dict]:
    """Add profile fields to each account dict in-place."""
    ids = [a["id"] for a in accounts]
    profiles = get_profiles_batch(ids)
    profile_map = {p["id"]: p for p in profiles}

    for account in accounts:
        p = profile_map.get(account["id"], {})
        account["username"] = p.get("username", "")
        account["display_name"] = p.get("display_name", "")
        account["description"] = p.get("description", "")
        account["followers_count"] = p.get("followers_count")
        account["followings_count"] = p.get("followings_count")
        account["tweets_count"] = p.get("tweets_count")
        account["verified"] = p.get("verified", False)
        account["created_at"] = p.get("created_at", "")

    return accounts


def enrich_tweets(accounts: list[dict]) -> list[dict]:
    """Fetch last 20 tweets for each account, add tweet texts and last tweet date."""
    for account in tqdm(accounts, desc="Fetching tweets"):
        try:
            tweets = get_user_tweets(account["id"], max_tweets=20)
            account["tweet_texts"] = [t.get("full_text", "") for t in tweets]
            if tweets:
                account["last_tweet_date"] = _parse_tweet_date(tweets[0].get("created_at", ""))
            else:
                account["last_tweet_date"] = ""
        except Exception as e:
            print(f"  [warn] tweets for {account['id']}: {e}")
            account["tweet_texts"] = []
            account["last_tweet_date"] = ""
        time.sleep(0.5)
    return accounts
