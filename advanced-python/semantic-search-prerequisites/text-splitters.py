from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore

from dotenv import load_dotenv

load_dotenv()

file_path = "./rental-agreement.pdf"

# Load the PDF document
loader = PyPDFLoader(file_path)
docs = loader.load()

# print(f"Document metadata : {docs[0].metadata}")

text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=1000, chunk_overlap=200, add_start_index=True
)

all_split_docs = text_splitter.split_documents(docs)

# print(f"Total number of split documents: {len(all_split_docs)}\n")

embeddings_model = OpenAIEmbeddings(model="text-embedding-3-large")

vector_1 = embeddings_model.embed_query(all_split_docs[0].page_content)
vector_2 = embeddings_model.embed_query(all_split_docs[1].page_content)
assert len(vector_1) == len(vector_2), "Vectors should have the same shape"

# print(f"Generated vectors of length {len(vector_1)}\n")
# print(vector_1[:10])

vector_store = InMemoryVectorStore(embeddings_model)
ids = vector_store.add_documents(all_split_docs)

query = input("Enter your query: ")

results = vector_store.similarity_search_with_score(query)
print(f"Number of results found: {len(results)}\n")

for idx, result in enumerate(results):
    doc, score = result
    print(f"Result {idx + 1}:")
    print(f"Score: {score:.4f}")
    print(f"Content: {doc.page_content}\n")
    print("-" * 50)




