from datetime import date, timedelta

EXCLUDED_SECTORS = {"L1", "L2", "Gaming", "NFT"}


def filter_candidates(pages: list[dict]) -> tuple[list[dict], list[tuple[dict, str]]]:
    """
    Phase 1 hard filter.
    Returns (candidates, dropped) where dropped is list of (page, reason).
    """
    candidates: list[dict] = []
    dropped: list[tuple[dict, str]] = []
    cutoff = date.today() - timedelta(days=365)

    for page in pages:
        if page.get("account_type") == "person":
            dropped.append((page, "person"))
            continue

        last_tweet = page.get("last_tweet_date", "")
        if not last_tweet:
            dropped.append((page, "no_tweet_date"))
            continue
        try:
            if date.fromisoformat(last_tweet) < cutoff:
                dropped.append((page, "stale_tweets"))
                continue
        except ValueError:
            dropped.append((page, "bad_date"))
            continue

        sectors = set(page.get("sectors", []))
        if sectors & EXCLUDED_SECTORS:
            dropped.append((page, f"excluded_sector:{','.join(sectors & EXCLUDED_SECTORS)}"))
            continue

        candidates.append(page)

    return candidates, dropped
