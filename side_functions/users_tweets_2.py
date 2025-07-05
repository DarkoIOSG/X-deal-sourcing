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

def get_user_tweets(user_id: str, max_tweets: int = 20) -> list:
    """
    Fetch tweets from a specified X user account.
    
    Args:
        user_id (str): The X user ID to fetch tweets from
        max_tweets (int): Maximum number of tweets to fetch (default: 20)
    
    Returns:
        list: List of tweet texts
    """
    url = "https://api.tweetscout.io/v2/user-tweets"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "ApiKey": API_KEY
    }
    
    all_tweets = []
    cursor = None
    
    while len(all_tweets) < max_tweets:
        payload = {
            "user_id": user_id
        }
        
        if cursor:
            payload["cursor"] = cursor
            
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            tweets = data.get("tweets", [])
            if not tweets:
                break
                
            # Extract only the full_text from each tweet
            tweet_texts = [tweet.get("full_text", "") for tweet in tweets]
            all_tweets.extend(tweet_texts)
            
            cursor = data.get("next_cursor")
            if not cursor:
                break
                
        except requests.exceptions.RequestException as e:
            print(f"Error fetching tweets: {e}")
            break
    
    return all_tweets[:max_tweets]

def get_last_tweet_date(user_id: str) -> str:
    """
    Get the date of the most recent tweet from a specified X user account.
    
    Args:
        user_id (str): The X user ID to fetch the last tweet date from
    
    Returns:
        str: The date in format 'YYYY-MM-DD' of the most recent tweet, or None if no tweets found
    """
    url = "https://api.tweetscout.io/v2/user-tweets"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "ApiKey": API_KEY
    }
    
    payload = {
        "user_id": user_id
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        tweets = data.get("tweets", [])
        if tweets:
            # Parse the date string and format it as YYYY-MM-DD
            date_str = tweets[0].get("created_at")
            if date_str:
                date_obj = datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
                return date_obj.strftime("%Y-%m-%d")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching last tweet date: {e}")
        return None

def summarize_account_tweets(user_id: str) -> str:
    """
    Analyze user's tweets to classify the account as either a "project" or "individual".
    
    Args:
        user_id (str): The X user ID to analyze tweets from
    
    Returns:
        str: Classification of the account as either "project" or "individual"
    """
    # Get the tweets
    tweets = get_user_tweets(user_id)
    if not tweets:
        return "unknown"
    
    # Combine tweets into a single text
    tweets_text = "\n".join(tweets)
    
    # Initialize OpenAI client
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    try:
        # Create the prompt for the LLM
        prompt = f"""Analyze these tweets and determine if this account represents a project/organization or an individual person.
Consider these factors:
- Project accounts typically discuss company updates, product launches, technical details, and have formal communication
- Individual accounts typically share personal opinions, experiences, and have more casual communication

Classify the account as either "project" or "individual".

Tweets to analyze:
{tweets_text}"""
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert at analyzing social media accounts and determining if they represent projects/organizations or individuals."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=50,
            temperature=0.5
        )
        
        # Parse the response and ensure it's one of the two categories
        classification = response.choices[0].message.content.strip().lower()
        
        # Normalize the response to ensure it's either "project" or "individual"
        if "project" in classification:
            return "project"
        elif "individual" in classification:
            return "individual"
        else:
            return "unknown"
        
    except Exception as e:
        print(f"Error classifying account: {str(e)}")
        return "unknown"

# Load your CSV file
df = pd.read_csv("cleaned_tracking_following_with_dates_2025-06-26.csv")

# Make sure there is an 'id' column
if "id" not in df.columns:
    raise ValueError("The CSV file must contain an 'id' column.")

# Add a new column to store the classification
df["account_type"] = None

# Loop through each user ID and get the classification
for idx, user_id in tqdm(enumerate(df["id"]), total=len(df)):
    try:
        classification = summarize_account_tweets(str(user_id))
        df.at[idx, "account_type"] = classification
        time.sleep(0.5)  # Respectful delay to avoid rate limiting
    except Exception as e:
        print(f"Error processing ID {user_id}: {e}")
        df.at[idx, "account_type"] = "unknown"

# Save the updated CSV
df.to_csv("cleaned_tracking_following_with_dates_2025-06-26_enriched.csv", index=False)
print("Finished. Output saved as 'cleaned_tracking_following_with_dates_2025-06-26_enriched_with_account_type.csv'")