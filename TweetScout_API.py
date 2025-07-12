import requests
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import defaultdict

API_KEY = os.getenv("TweetScout_API_key")
TG_bot_token = os.getenv("TG_bot_token")

def get_followers_data(link):
    url = "https://api.tweetscout.io/v2/follows"
    
    querystring = {"link": link}
    
    headers = {
        "Accept": "application/json",
        "ApiKey": API_KEY
    }
    
    response = requests.get(url, headers=headers, params=querystring)
    data = response.json()
    # Extract id and name from each user in the response
    users_data = []
    for user in data:
        # Only add if both id and name are not empty
        if user.get('id') and user.get('name'):
            users_data.append({
                'id': user['id'],
                'name': user['name'],
                'register_date': user['register_date']
            })
    
    # Create DataFrame
    df = pd.DataFrame(users_data)
    return df

def add_twitter_links(df):
    """
    Add Twitter profile links to the dataframe
    """
    df['link'] = df['id'].apply(lambda x: f"https://x.com/i/user/{x}")
    return df

def find_common_follows(links):
    # Dictionary to store how many users follow each account
    account_followers = defaultdict(list)
    # Dictionary to store account names
    account_names = {}
    # Dictionary to store account register dates
    account_register_dates = {}
    
    # Process each link
    for link in links:
        try:
            username = link.split('/')[-1]
            print(f"Processing {username}...")
            df = get_followers_data(link)
            
            # Add each followed account to our dictionary
            for _, row in df.iterrows():
                # Skip if id or name is empty
                if pd.isna(row['id']) or pd.isna(row['name']) or not row['id'] or not row['name']:
                    continue
                    
                account_id = row['id']
                account_followers[account_id].append(username)
                # Store the account name and register date
                account_names[account_id] = row['name']
                account_register_dates[account_id] = row['register_date']
                
        except Exception as e:
            print(f"Error processing {link}: {str(e)}")
    
    # Calculate 20% threshold
    threshold = len(links) * 0.2
    
    # Find accounts followed by at least 20% of users
    common_follows = []
    # Find accounts followed by at least 20% of users but not in common_follows
    new_tracking = []
    
    # First, collect all accounts with 20%+ followers
    potential_accounts = []
    for account_id, followers in account_followers.items():
        if len(followers) >= threshold:
            # Skip if account name is empty
            if not account_names.get(account_id):
                continue
                
            potential_accounts.append({
                'id': account_id,
                'name': account_names.get(account_id, 'Unknown'),
                'register_date': account_register_dates.get(account_id, 'Unknown'),
                'followed_by': ', '.join(followers),
                'followers_count': len(followers)
            })
    
    # Read existing common_follows if it exists
    existing_common_follows = set()
    if Path("common_follows.csv").exists():
        existing_df = pd.read_csv("common_follows.csv", dtype={'id': str})
        existing_common_follows = set(existing_df['id'].astype(str))
    
    # Separate into common_follows and new_tracking
    for account in potential_accounts:
        if account['id'] in existing_common_follows:
            common_follows.append(account)
        else:
            new_tracking.append(account)
    
    return pd.DataFrame(common_follows), pd.DataFrame(new_tracking)

def compare_with_previous(common_follows_df, new_tracking_df):
    previous_file = Path("common_follows.csv")
    # Create new_tracking filename with current date
    current_date = datetime.now().strftime("%Y-%m-%d")
    new_tracking_file = Path(f"new_tracking_{current_date}.csv")
    
    # Handle common follows comparison
    if previous_file.exists():
        # Read previous results with id as string
        previous_df = pd.read_csv(previous_file, dtype={'id': str})
        # Remove rows with empty values
        previous_df = previous_df.dropna(subset=['id', 'name'])
        
        # Ensure new_df id is also string
        common_follows_df['id'] = common_follows_df['id'].astype(str)
        # Remove rows with empty values
        common_follows_df = common_follows_df.dropna(subset=['id', 'name'])
        
        # Find new accounts (those not in previous results)
        new_accounts = common_follows_df[~common_follows_df['id'].isin(previous_df['id'])]
        
        #if not new_accounts.empty:
            #token = TG_bot_token
            #msg_type = 'sendMessage'
            #chat_id = '-4652016922'
            #for _, row in new_accounts.iterrows():
               #text = f'\nNew common follows found (not in previous results):\nAccount: {row["name"]} (ID: {row["id"]})\nFollowed by: {row["followed_by"]}\nNumber of followers: {row["followers_count"]}'
                #msg = f'https://api.telegram.org/bot{token}/{msg_type}?chat_id={chat_id}&text={text}'
                #telegram_msg = requests.get(msg)
        #else:
            #print("\nNo new common follows found.")
    else:
        #token = TG_bot_token
        #msg_type = 'sendMessage'
        #chat_id = '-4652016922'
        #text = f'\nNo previous data found. This is the first run'
        #msg = f'https://api.telegram.org/bot{token}/{msg_type}?chat_id={chat_id}&text={text}'
        #telegram_msg = requests.get(msg)
        print("\nNo previous data found. This is the first run.")
        # For first run, show all common follows
        #if not common_follows_df.empty:
            #print("\nCommon follows found (first run) - at least 20% of users follow these accounts:")
            #for _, row in common_follows_df.iterrows():
                #text = f'\nAccount: {row["name"]} (ID: {row["id"]})\nFollowed by: {row["followed_by"]}\nNumber of followers: {row["followers_count"]}'
                #msg = f'https://api.telegram.org/bot{token}/{msg_type}?chat_id={chat_id}&text={text}'
                #telegram_msg = requests.get(msg)
    
    # Handle new tracking accounts
    if new_tracking_file.exists():
        previous_tracking_df = pd.read_csv(new_tracking_file, dtype={'id': str})
        previous_tracking_df = previous_tracking_df.dropna(subset=['id', 'name'])
        
        new_tracking_df['id'] = new_tracking_df['id'].astype(str)
        new_tracking_df = new_tracking_df.dropna(subset=['id', 'name'])
        
        # Find new accounts that weren't being tracked before
        #new_tracking_accounts = new_tracking_df[~new_tracking_df['id'].isin(previous_tracking_df['id'])]
        
        #if not new_tracking_accounts.empty:
            #token = TG_bot_token
            #msg_type = 'sendMessage'
            #chat_id = '-4652016922'
            #for _, row in new_tracking_accounts.iterrows():
                #text = f'\nNew account to track (20%+ followers):\nAccount: {row["name"]} (ID: {row["id"]})\nFollowed by: {row["followed_by"]}\nNumber of followers: {row["followers_count"]}'
                #msg = f'https://api.telegram.org/bot{token}/{msg_type}?chat_id={chat_id}&text={text}'
                #telegram_msg = requests.get(msg)
    else:
        print("\nNo previous tracking data found. This is the first run for tracking accounts.")
        #if not new_tracking_df.empty:
            #print("\nNew accounts to track (20%+ followers):")
            #for _, row in new_tracking_df.iterrows():
                #print(f"\nAccount: {row['name']} (ID: {row['id']})")
                #print(f"Followed by: {row['followed_by']}")
                #print(f"Number of followers: {row['followers_count']}")
    
    # Add Twitter links to both dataframes
    common_follows_df = add_twitter_links(common_follows_df)
    new_tracking_df = add_twitter_links(new_tracking_df)
    
    # Combine common_follows and new_tracking dataframes
    all_accounts_df = pd.concat([common_follows_df, new_tracking_df], ignore_index=True)
    
    # Save combined results to common_follows.csv for next run
    all_accounts_df.to_csv(previous_file, index=False)
    print("\nAll accounts (common follows and new tracking) saved to common_follows.csv for next run")
    
    # Save new tracking results with date suffix
    new_tracking_df.to_csv(new_tracking_file, index=False)
    print(f"\nNew tracking results saved to {new_tracking_file}")

def main():
    print(f"\nRunning check at {datetime.now()}")
    
    # Read links from file
    try:
        with open('followed_accounts.txt', 'r') as file:
            links = [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        print("Error: followed_accounts.txt file not found!")
        return
    
    # Remove duplicates from links list
    links = list(dict.fromkeys(links))
    print(f"Total unique links to process: {len(links)}")
    
    # Find common follows and new tracking accounts
    common_follows_df, new_tracking_df = find_common_follows(links)
    
    # Compare with previous results
    compare_with_previous(common_follows_df, new_tracking_df)

if __name__ == "__main__":
    main()
