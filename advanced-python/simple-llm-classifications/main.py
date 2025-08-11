from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from dotenv import load_dotenv
import os

load_dotenv()

# Access the API key
api_key = os.getenv("OPENAI_API_KEY")

print(api_key)