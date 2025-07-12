import pandas as pd
import glob
from datetime import datetime
import os
import requests
import time
from urllib.parse import urlparse

def get_following_data(link, api_key):
    """Get accounts that a Twitter account follows"""
    url = "https://api.tweetscout.io/v2/follows"
    
    querystring = {"link": link}
    
    headers = {
        "Accept": "application/json",
        "ApiKey": api_key
    }
    
    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()
        data = response.json()
        
        # Extract id and name from each user in the response
        users_data = []
        for user in data:
            # Only add if both id and name are not empty
            if user.get('id') and user.get('name'):
                users_data.append({
                    'id': user['id'],
                    'name': user['name'],
                    'register_date': user.get('register_date')
                })
        
        return users_data
    except requests.exceptions.RequestException as e:
        print(f"Error getting following data for {link}: {e}")
        return []

def load_followed_accounts():
    """Load and process followed accounts from file"""
    with open('followed_accounts.txt', 'r') as f:
        accounts = [line.strip() for line in f if line.strip()]
    return accounts  # Return full URLs

def merge_and_check_following():
    # Load followed accounts
    followed_accounts = load_followed_accounts()
    print(f"Loaded {len(followed_accounts)} accounts to check")
    # Find all tracking CSV files
    tracking_files = glob.glob('new_tracking_*.csv')
    print(f"Found {len(tracking_files)} tracking files")
    
    # Initialize empty list to store all dataframes
    dfs = []
    
    # Read each file and append to list
    for file in tracking_files:
        try:
            df = pd.read_csv(file)
            print(f"Read {len(df)} records from {file}")
            dfs.append(df)
        except Exception as e:
            print(f"Error reading {file}: {e}")
    
    if not dfs:
        print("No tracking files found!")
        return
    
    # Concatenate all dataframes
    merged_df = pd.concat(dfs, ignore_index=True)
    print(f"Total records after merging: {len(merged_df)}")
    
    # Convert register_date to datetime
    merged_df['register_date'] = pd.to_datetime(merged_df['register_date'], format='%a %b %d %H:%M:%S %z %Y')
    
    # Group by id and get the latest record for each account
    latest_records = merged_df.sort_values('register_date').groupby('id').last().reset_index()
    # Convert id column to string
    latest_records['id'] = latest_records['id'].astype(str)
    
    # Fill missing links using account ID
    latest_records['link'] = latest_records.apply(
        lambda row: row['link'] if pd.notna(row['link']) and row['link'] != '' 
        else f"https://x.com/i/user/{row['id']}", 
        axis=1
    )
    
    print(f"Found {len(latest_records)} unique accounts in tracking files")
    
    # Dictionary to store which accounts follow each user
    account_followers = {}
    
    # For each account in followed_accounts.txt
    for followed_account in followed_accounts:
        print(f"\nGetting accounts that {followed_account} follows...")
        
        # Get all accounts this followed account follows
        following = get_following_data(followed_account, os.getenv("TweetScout_API_key"))
        print(f"Found {len(following)} accounts being followed")
        
        # For each account they follow, check if it's in our tracking files
        matches_found = 0
        for account in following:
            # Convert account_id to string
            account_id = str(account['id'])
            # Check if the account_id exists in the 'id' column of latest_records
            if account_id in latest_records['id'].values:
                matches_found += 1
                if account_id not in account_followers:
                    account_followers[account_id] = {
                        'followers': [],
                        'count': 0
                    }
                account_followers[account_id]['followers'].append(followed_account)
                account_followers[account_id]['count'] += 1
        
        print(f"Found {matches_found} matches in tracking files for {followed_account}")
        
        time.sleep(1)  # Rate limiting
    
    # Create list of processed records
    processed_records = []
    for account_id, data in account_followers.items():
        # Get the row where id matches account_id
        row = latest_records[latest_records['id'] == account_id].iloc[0]
        processed_records.append({
            'id': account_id,
            'name': row['name'],
            'followers_count': data['count'],
            'followed_by': ', '.join(data['followers']),
            'register_date': row['register_date'],
            'link': row['link']
        })
    
    print(f"\nTotal matches found: {len(processed_records)}")
    
    if not processed_records:
        print("No matches found between followed accounts and tracking files!")
        return
    
    # Create new dataframe with processed records
    result_df = pd.DataFrame(processed_records)
    
    # Sort by followers_count in descending order
    result_df = result_df.sort_values('followers_count', ascending=False)
    
    # Generate output filename with current date
    current_date = datetime.now().strftime('%Y-%m-%d')
    output_file = f'merged_tracking_following_{current_date}.csv'
    
    # Save to CSV
    result_df.to_csv(output_file, index=False)
    print(f"\nSuccessfully created {output_file}")
    print(f"Found {len(result_df)} accounts that are followed by at least one account from followed_accounts.txt")

if __name__ == "__main__":
    merge_and_check_following()