from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import getpass
import os

load_dotenv()

if not os.environ.get("OPENAI_API_KEY"):
  os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter API key for OpenAI: ")

# Access the API key
api_key = os.getenv("OPENAI_API_KEY")

# Initialize the ChatOpenAI model
model = ChatOpenAI(
    openai_api_key=api_key,
    model="gpt-4.1-nano",  # or gpt-4, etc.
    temperature=0.2,
)

system_template = "Translate the following from English into {language}"

prompt_template = ChatPromptTemplate.from_messages(
  [("system", system_template), ("user", "{text}")]
)

user_text_input = input("Enter text in english: ")
user_preferred_language = input("Enter preferred translation language: ")

prompt = prompt_template.invoke({
  "language": user_preferred_language,
  "text": user_text_input
})

response = model.invoke(prompt)

print(f"Output: {response.content}")