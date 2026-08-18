from pipeline.retriever import retrieve
import logging
logging.basicConfig(level=logging.INFO)

chunks = retrieve("SKF", "6205-2RS1", "Deep groove ball bearing 25x52x15mm sealed", "bearings")
print(f"Chunks retrieved: {len(chunks)}")
for c in chunks:
    print("Type:", c.get("source_type"))
