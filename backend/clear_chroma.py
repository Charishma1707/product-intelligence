from pathlib import Path
from chromadb import PersistentClient

chroma_dir = Path(__file__).resolve().parent / "data" / "chroma"
client = PersistentClient(path=str(chroma_dir))
coll = client.get_or_create_collection("product_chunks")
all_ids = coll.get()["ids"]
if all_ids:
    coll.delete(ids=all_ids)
    print("Deleted", len(all_ids), "chunks.")
else:
    print("No chunks found in ChromaDB.")

