import pandas as pd
from side_functions.users_tweets import summarize_account_tweets
import time
from tqdm import tqdm

def process_users_tweets():
    # Read the CSV file
    input_file = 'merged_tracking_following_2025-07-11.csv'
    output_file = 'merged_tracking_following_2025-07-11_with_analysis.csv'
    
    print(f"Reading {input_file}...")
    df = pd.read_csv(input_file)
    
    # Initialize the new column
    df['users_tweets_analysis'] = None
    
    # Process each user ID
    print("Processing user tweets...")
    for idx in tqdm(df.index):
        user_id = str(df.at[idx, 'id'])
        
        try:
            # Get the analysis
            description, entities = summarize_account_tweets(user_id)
            
            # Create a structured analysis string
            analysis = {
                'description': description,
                'mentioned_entities': entities
            }
            
            # Store the analysis
            df.at[idx, 'users_tweets_analysis'] = str(analysis)
            
            # Add a small delay to avoid rate limiting
            time.sleep(1)
            
        except Exception as e:
            print(f"Error processing user {user_id}: {str(e)}")
            df.at[idx, 'users_tweets_analysis'] = f"Error: {str(e)}"
    
    # Save the updated DataFrame
    print(f"Saving results to {output_file}...")
    df.to_csv(output_file, index=False)
    print("Done!")

if __name__ == "__main__":
    process_users_tweets() 