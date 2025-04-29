import pandas as pd
import matplotlib.pyplot as plt

# Read the CSV file
df = pd.read_csv('new_tracking.csv')

# Convert followers_count to numeric
df['followers_count'] = pd.to_numeric(df['followers_count'])

# Sort by followers_count in descending order
df_sorted = df.sort_values('followers_count', ascending=False)

# Take top 10 accounts
top_10 = df_sorted.head(30)

# Create the visualization
plt.figure(figsize=(12, 6))
bars = plt.bar(top_10['name'], top_10['followers_count'])
plt.title('Top 30 Accounts by Number of Followers')
plt.xlabel('Account Name')
plt.ylabel('Number of Followers')
plt.xticks(rotation=45, ha='right')

# Add value labels on top of each bar
for bar in bars:
    height = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2., height,
             f'{int(height)}',
             ha='center', va='bottom')

plt.tight_layout()
plt.savefig('top_followers.png')
plt.show() 