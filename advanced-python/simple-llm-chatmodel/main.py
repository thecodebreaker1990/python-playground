from langchain_core.messages import HumanMessage, SystemMessage
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

messages = [
    SystemMessage("Translate the following from English into Italian"),
    HumanMessage("hi!"),
]

# Run a sample query
#print(model.invoke(messages))

for token in model.stream(messages):
    print(token.content, end="|")