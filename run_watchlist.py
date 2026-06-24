from datetime import datetime
from state import init_db, log_run
from pipeline.fetch_following import load_watchlist, fetch_all_following
from pipeline.aggregate import aggregate
from pipeline.enrich import enrich_profiles, enrich_tweets
from pipeline.analyze import analyze_accounts
from pipeline.notion_sync import sync_to_notion


def main():
    print(f"\n=== Deal Sourcing Pipeline — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n")

    init_db()

    watchlist = load_watchlist()
    print(f"Watchlist: {len(watchlist)} accounts\n")

    following_map = fetch_all_following(watchlist)

    new_accounts, existing_accounts = aggregate(following_map)
    print(f"\nFound {len(new_accounts)} new accounts")
    print(f"Skipping {len(existing_accounts)} already known accounts\n")

    if not new_accounts:
        print("Nothing new this run.")
        log_run(len(watchlist), 0)
        return

    print("Enriching profiles...")
    new_accounts = enrich_profiles(new_accounts)

    print("Fetching tweets...")
    new_accounts = enrich_tweets(new_accounts)

    print("Analyzing tweets...")
    new_accounts = analyze_accounts(new_accounts)

    print("Syncing to Notion...")
    sync_to_notion(new_accounts)

    log_run(len(watchlist), len(new_accounts))
    print(f"\nDone. {len(new_accounts)} new accounts added to Notion.")


if __name__ == "__main__":
    main()
