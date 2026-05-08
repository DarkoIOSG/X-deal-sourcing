"""Quick sanity test for the IC retrieval index."""
import sys
sys.path.insert(0, ".")
from shared.ic_retrieval import retrieve_ic_context

QUERIES = [
    ("EN", "stablecoin payment rails"),
    ("EN", "RWA tokenization"),
    ("EN", "mobile DeFi consumer app"),
    ("ZH", "代币经济学"),
    ("ZH", "稳定币支付"),
]

for lang, query in QUERIES:
    print(f"\n{'─'*60}")
    print(f"[{lang}] {query}")
    print('─'*60)
    for r in retrieve_ic_context(query, top_k=3):
        print(f"  {r['score']:.3f}  {r['source_file']}  ({r['source_type']})")
        print(f"         {r['text'][:180].strip()}")
        print()
