from collections import defaultdict
from config import MIN_WATCHERS
from state import get_known_ids


def aggregate(following_map: dict[str, set[str]]) -> tuple[list[dict], list[dict]]:
    """
    Returns (new_accounts, existing_accounts), both sorted descending by watcher_count.
    Each account dict has: id, watcher_count, watchers (list of usernames)
    """
    counts: dict[str, list[str]] = defaultdict(list)
    for username, followed_ids in following_map.items():
        for uid in followed_ids:
            counts[uid].append(username)

    above_min = [
        {"id": uid, "watcher_count": len(watchers), "watchers": watchers}
        for uid, watchers in counts.items()
        if len(watchers) >= MIN_WATCHERS
    ]

    above_min.sort(key=lambda a: a["watcher_count"], reverse=True)

    known_ids = get_known_ids()
    new_accounts = [a for a in above_min if a["id"] not in known_ids]
    existing_accounts = [a for a in above_min if a["id"] in known_ids]

    return new_accounts, existing_accounts
