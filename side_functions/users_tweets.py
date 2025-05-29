import requests
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from openai import OpenAI

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
    Extract and list specific entities (projects, tokens, VCs, etc.) mentioned in the user's tweets.
    
    Args:
        user_id (str): The X user ID to analyze tweets from
    
    Returns:
        str: A list of entities mentioned in the tweets, one per line
    """
    # Get the tweets
    tweets = get_user_tweets(user_id)
    if not tweets:
        return "No tweets found to analyze."
    
    # Combine tweets into a single text
    tweets_text = "\n".join(tweets)
    
    # Initialize OpenAI client
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    try:
        # Create the prompt for the LLM
        prompt = f"""Extract all specific entities mentioned in these tweets. Return them as a simple list, one entity per line.
Include the entity type in parentheses after each name.

Example format:
ProjectA (project)
TOKEN1 (token)
VC1 (investor)
Company1 (company)
Person1 (person)

Tweets to analyze:
{tweets_text}

List the entities (one per line):"""
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an entity extraction specialist. Return a simple list of entities, one per line, with their type in parentheses. Be precise and avoid general terms."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.8
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        return f"Error generating summary: {str(e)}"

# Example usage
if __name__ == "__main__":
    user_id = "1395628622417825795"
    print("Last 20 tweets:")
    print(get_user_tweets(user_id))
    print("\nLast tweet date:")
    print(get_last_tweet_date(user_id))
    print("\nAccount summary:")
    print(summarize_account_tweets(user_id))