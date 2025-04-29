import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter

# Read the CSV file
df = pd.read_csv('new_tracking.csv')

# Process the followed_by column to count occurrences
all_followed = []
for followed in df['followed_by']:
    if pd.notna(followed):
        accounts = [acc.strip() for acc in followed.split(',')]
        all_followed.extend(accounts)

# Count occurrences of each account
account_counts = Counter(all_followed)

# Get top 30 accounts
top_30 = account_counts.most_common(30)

# Create visualization
plt.figure(figsize=(15, 10))
accounts, counts = zip(*top_30)
plt.barh(accounts, counts)
plt.title('Top 30 Most Followed Accounts')
plt.xlabel('Number of Followers')
plt.ylabel('Account Names')
plt.tight_layout()

# Save the plot
plt.savefig('top_30_followed.png')
plt.close()

# Print the results
print("\nTop 30 Most Followed Accounts:")
for account, count in top_30:
    print(f"{account}: {count} followers") 