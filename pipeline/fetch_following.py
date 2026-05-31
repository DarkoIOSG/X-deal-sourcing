import time
from tqdm import tqdm
from api.sorsa import username_to_id, get_new_following_7d
from config import WATCHLIST_FILE


def load_watchlist() -> list[str]:
    with open(WATCHLIST_FILE) as f:
        return [line.strip() for line in f if line.strip()]


def _username_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


MAX_NEW_FOLLOWS = 200  # accounts with more new follows than this are likely bots or mass-follow accounts


def fetch_all_following(watchlist: list[str]) -> dict[str, set[str]]:
    """
    Returns {watchlist_username: set_of_new_followed_user_ids (last 7 days)}
    """
    result = {}
    for url in tqdm(watchlist, desc="Fetching new follows (7d)"):
        username = _username_from_url(url)
        try:
            user_id = username_to_id(username)
            following = get_new_following_7d(user_id)
            if len(following) > MAX_NEW_FOLLOWS:
                print(f"  {username}: {len(following)} new follows — skipped (likely bot/mass-follow)")
                result[username] = set()
                continue
            result[username] = {u["id"] for u in following}
            print(f"  {username}: {len(result[username])} new follows")
        except Exception as e:
            print(f"  [warn] {username}: {e}")
            result[username] = set()
        time.sleep(0.3)
    return result
