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

inputs = ["Good Morning", "Good Night", "How are you!", "Hi"]
prompts = [None for i in inputs]

for idx,text in enumerate(inputs):
    prompt = prompt_template.invoke({
        "language": "Italian",
        "text": text
    })
    prompts[idx] = prompt

responses = model.batch(prompts)


# Print outputs
for input_text, response in zip(inputs, responses):
    print(f"Input: {input_text}")
    print(f"Output: {response.content.strip()}")
    print("-" * 40)