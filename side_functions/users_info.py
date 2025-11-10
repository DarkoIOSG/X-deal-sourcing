import requests
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from openai import OpenAI
from tqdm import tqdm  # progress bar
import time

API_KEY = os.getenv("TweetScout_API_key")
OPENAI_API_KEY = os.getenv("OPENAI_API_key")

def enrich_users_with_twitter_info(input_csv_path, output_csv_path=None):
    """
    Enrich user data from a CSV file with Twitter information.
    
    Args:
        input_csv_path (str): Path to the input CSV file containing Twitter IDs
        output_csv_path (str, optional): Path to save the enriched CSV. If None, will append '_enriched' to input filename
    
    Returns:
        pd.DataFrame: Enriched dataframe with Twitter user information
    """
    # Read the input CSV
    df = pd.read_csv(input_csv_path)
    
    # Ensure 'id' column exists
    if 'id' not in df.columns:
        raise ValueError("Input CSV must contain an 'id' column")
    
    # Initialize new columns
    new_columns = ['verified', 'description', 'followers_count', 'friends_count', 'tweets_count']
    for col in new_columns:
        df[col] = None
    
    # API endpoint base URL
    base_url = "https://api.tweetscout.io/v2/info-id/"
    
    # Headers for API request
    headers = {
        "Accept": "application/json",
        "ApiKey": API_KEY
    }
    
    # Process each ID with progress bar
    for idx in tqdm(df.index, desc="Fetching Twitter user info"):
        user_id = str(df.at[idx, 'id'])
        
        try:
            # Make API request
            response = requests.get(f"{base_url}{user_id}", headers=headers)
            response.raise_for_status()  # Raise exception for bad status codes
            
            # Parse response
            user_data = response.json()
            
            # Update dataframe with new information
            df.at[idx, 'verified'] = user_data.get('verified')
            df.at[idx, 'description'] = user_data.get('description')
            df.at[idx, 'followers_count'] = user_data.get('followers_count')
            df.at[idx, 'friends_count'] = user_data.get('friends_count')
            df.at[idx, 'tweets_count'] = user_data.get('tweets_count')
            
            # Add a small delay to avoid rate limiting
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Error processing ID {user_id}: {str(e)}")
            continue
    
    # Save the enriched data if output path is provided
    if output_csv_path is None:
        input_path = Path(input_csv_path)
        output_csv_path = str(input_path.parent / f"{input_path.stem}_enriched{input_path.suffix}")
    
    df.to_csv(output_csv_path, index=False)
    print(f"Enriched data saved to: {output_csv_path}")
    
    return df

if __name__ == "__main__":
    # Input file path
    input_file = "cleaned_tracking_following_with_dates_2025-11-09_enriched.csv"
    
    # Run the enrichment process
    print(f"Starting enrichment process for {input_file}")
    enriched_df = enrich_users_with_twitter_info(input_file)
    print("Enrichment process completed!")

