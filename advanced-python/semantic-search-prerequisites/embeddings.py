import numpy as np
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

def cosine_similarity(vec1, vec2):
    dot_product = np.dot(vec1, vec2)
    norm_vec1 = np.linalg.norm(vec1)
    norm_vec2 = np.linalg.norm(vec2)
    return dot_product / (norm_vec1 * norm_vec2)

load_dotenv()

documents = [
    "Hi there!",
    "Oh, hello!",
    "What's your name?",
    "My friends call me World",
    "Hello World!"
]

embeddings_model = OpenAIEmbeddings(model="text-embedding-3-large")
embedded_documents = embeddings_model.embed_documents(documents)
embedded_query = embeddings_model.embed_query("What was the name mentioned in the conversation?")

for idx, doc_embedding in enumerate(embedded_documents):
    similarity = cosine_similarity(doc_embedding, embedded_query)
    print(f"Document {idx + 1}: {documents[idx]}")
    print(f"Cosine Similarity: {similarity:.4f}")
    print("-" * 50)

