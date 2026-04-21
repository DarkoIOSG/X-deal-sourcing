import time
from tqdm import tqdm
from api.notion import create_page
from state import add_account, update_notion_page_id


def sync_to_notion(accounts: list[dict]):
    for account in tqdm(accounts, desc="Syncing to Notion"):
        try:
            page_id = create_page(account)
            account["notion_page_id"] = page_id
            add_account(account["id"], page_id)
        except Exception as e:
            print(f"  [warn] Notion sync failed for {account.get('username', account['id'])}: {e}")
            account["notion_page_id"] = None
        time.sleep(0.3)
