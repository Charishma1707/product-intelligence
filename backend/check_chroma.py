from chromadb import PersistentClient
client = PersistentClient(path="C:\\charishma\\apicurio registry\\unihack\\product-intelligence\\data\\chroma")
coll = client.get_or_create_collection("product_chunks")
all_ids = coll.get()["ids"]
print("Found", len(all_ids), "chunks.")
