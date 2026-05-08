"""Build the IC retrieval index. Re-run when new IC sessions or research are added."""
import os, re, pickle
from pathlib import Path
from voyageai import Client
from dotenv import load_dotenv

load_dotenv()
VOYAGE = Client()
SOURCES = [
    ("ic",       Path("data/ic_transcripts")),
    ("research", Path("data/research")),
]
INDEX_PATH = Path("data/ic_index.pkl")
TARGET_CHARS = 3200
OVERLAP_CHARS = 400

def parse_date(name: str) -> str | None:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    return m.group(1) if m else None

def chunk_text(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
    chunks, current = [], ""
    for para in paragraphs:
        if not current:
            current = para
        elif len(current) + len(para) + 2 <= TARGET_CHARS:
            current += "\n\n" + para
        else:
            chunks.append(current)
            tail = current[-OVERLAP_CHARS:]
            current = tail + "\n\n" + para
    if current:
        chunks.append(current)
    return chunks

def make_prefix(source_type: str, filename: str, date: str | None) -> str:
    """Prepend file context to every chunk so mid-sentence fragments are still meaningful."""
    label = "IC discussion" if source_type == "ic" else "Research"
    stem = Path(filename).stem.replace("_", " ")
    date_str = f" | {date}" if date else ""
    return f"[{label}: {stem}{date_str}]\n\n"

def load_records() -> list[dict]:
    records = []
    for source_type, directory in SOURCES:
        if not directory.exists():
            continue
        for path in list(directory.rglob("*.md")) + list(directory.rglob("*.txt")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            date = parse_date(path.name)
            prefix = make_prefix(source_type, path.name, date)
            for i, chunk in enumerate(chunk_text(text)):
                records.append({
                    "id": f"{source_type}-{path.stem}-{i}",
                    "source_type": source_type,
                    "source_file": path.name,
                    "date": date,
                    "text": prefix + chunk,   # prefix embedded, raw chunk stored
                    "raw_text": chunk,
                })
    return records

BATCH_SIZE = 64

def embed_batches(texts: list[str], batch: int = BATCH_SIZE) -> list[list[float]]:
    import time
    import voyageai
    out = []
    total_batches = (len(texts) + batch - 1) // batch
    for idx, i in enumerate(range(0, len(texts), batch)):
        slice_ = texts[i:i+batch]
        while True:
            try:
                result = VOYAGE.embed(slice_, model="voyage-4-lite", input_type="document")
                break
            except voyageai.error.RateLimitError:
                print(f"  rate limited — waiting 10s ...")
                time.sleep(10)
        out.extend(result.embeddings)
        done = i + len(result.embeddings)
        print(f"  embedded {done}/{len(texts)}  (batch {idx+1}/{total_batches})")
    return out

def main():
    records = load_records()
    print(f"Loaded {len(records)} chunks")
    if not records:
        print("No records found. Did you extract the zips into data/ic_transcripts and data/research?")
        return
    embeddings = embed_batches([r["text"] for r in records])
    for r, e in zip(records, embeddings):
        r["embedding"] = e
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, "wb") as f:
        pickle.dump(records, f)
    print(f"Wrote {INDEX_PATH} ({len(records)} chunks)")

if __name__ == "__main__":
    main()
