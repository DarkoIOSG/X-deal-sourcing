import sys
import os
import requests
import pandas as pd

API_KEY = os.getenv("TweetScout_API_key")

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
followed_accounts_path = os.path.join(base_dir, 'followed_accounts.txt')

with open(followed_accounts_path, 'r') as f:
    links = [line.strip() for line in f if line.strip()]

results = []

for link in links:
    username = link.rstrip('/').split('/')[-1].split('?')[0]
    user_id = None
    num_follows = None
    try:
        # Step 1: Get user ID from handle
        url_id = f"https://api.tweetscout.io/v2/handle-to-id/{username}"
        headers = {"Accept": "application/json", "ApiKey": API_KEY}
        resp_id = requests.get(url_id, headers=headers)
        resp_id.raise_for_status()
        data_id = resp_id.json()
        user_id = data_id.get('id')
        if not user_id:
            raise Exception(f"No user id found for {username}")
        # Step 2: Get user info and friends_count
        url_info = f"https://api.tweetscout.io/v2/info-id/{user_id}"
        resp_info = requests.get(url_info, headers=headers)
        resp_info.raise_for_status()
        data_info = resp_info.json()
        num_follows = data_info.get('friends_count', None)
    except Exception as e:
        print(f"Error processing {username}: {e}")
        num_follows = 'ERROR'
    results.append({'username': username, 'num_follows': num_follows})

out_df = pd.DataFrame(results)
out_df.to_csv('accounts_num_follows.csv', index=False)
print('Saved to accounts_num_follows.csv') 