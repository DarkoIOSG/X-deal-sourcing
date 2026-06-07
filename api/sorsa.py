import time
import requests
from config import SORSA_API_KEY, SORSA_BASE_URL

HEADERS = {"ApiKey": SORSA_API_KEY, "Accept": "application/json"}


def _get(path: str, params: dict = None) -> dict | list:
    url = f"{SORSA_BASE_URL}{path}"
    for attempt in range(3):
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        if r.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"GET {path} failed after retries")


def _post(path: str, payload: dict) -> dict:
    url = f"{SORSA_BASE_URL}{path}"
    for attempt in range(3):
        r = requests.post(url, headers={**HEADERS, "Content-Type": "application/json"},
                          json=payload, timeout=30)
        if r.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"POST {path} failed after retries")


def username_to_id(username: str) -> str:
    data = _get(f"/username-to-id/{username}")
    return data["id"]


def get_new_following_7d(user_id: str) -> list[dict]:
    """Return accounts the user started following in the last 7 days (1 API call)."""
    data = _get("/new-following-7d", {"user_id": user_id})
    return data.get("users", [])


def get_profiles_batch(user_ids: list[str]) -> list[dict]:
    """Fetch profiles in chunks of 50 with retry on timeout/429."""
    all_users = []
    for i in range(0, len(user_ids), 50):
        chunk = user_ids[i:i + 50]
        params = [("user_ids", uid) for uid in chunk]
        for attempt in range(4):
            try:
                r = requests.get(f"{SORSA_BASE_URL}/info-batch", headers=HEADERS,
                                 params=params, timeout=60)
                if r.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                r.raise_for_status()
                all_users.extend(r.json().get("users", []))
                break
            except requests.exceptions.Timeout:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        time.sleep(0.3)
    return all_users


def search_tweets(query: str, order: str = "popular", max_results: int = 100) -> list[dict]:
    """Search tweets with cursor-based pagination up to max_results."""
    tweets = []
    cursor = None
    while len(tweets) < max_results:
        payload = {"query": query, "order": order}
        if cursor:
            payload["next_cursor"] = cursor
        data = _post("/search-tweets", payload)
        batch = data.get("tweets", [])
        tweets.extend(batch)
        cursor = data.get("next_cursor")
        if not cursor or not batch:
            break
        time.sleep(0.3)
    return tweets[:max_results]


def get_user_tweets(user_id: str, max_tweets: int = 20) -> list[dict]:
    tweets = []
    cursor = None
    while len(tweets) < max_tweets:
        payload = {"user_id": user_id}
        if cursor:
            payload["next_cursor"] = cursor
        data = _post("/user-tweets", payload)
        batch = data.get("tweets", [])
        tweets.extend(batch)
        cursor = data.get("next_cursor")
        if not cursor or not batch:
            break
    return tweets[:max_tweets]
