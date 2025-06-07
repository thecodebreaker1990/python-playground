from typing import Optional, List
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.utils.function_calling import tool_example_to_messages
from langchain_openai import ChatOpenAI 
import os

load_dotenv()

class Person(BaseModel):
    # Note that:
    # 1. Each field is an `optional` -- this allows the model to decline to extract it!
    # 2. Each field has a `description` -- this description is used by the LLM.
    # Having a good description can help improve extraction results.
    name: Optional[str] = Field(default=None, description="The name of the person")
    hair_color: Optional[str] = Field(
        default=None, description="The color of the person's hair if known"
    )
    height_in_meters: Optional[str] = Field(
        default=None, description="Height measured in meters"
    )
    city: Optional[str] = Field(default=None, description="The city where the person lives")

class Data(BaseModel):
    """Extracted data about people."""

    # Creates a model so that we can extract multiple entities.
    people: List[Person]


examples = [
    (
        "The ocean is vast and blue. It's more than 20,000 feet deep.",
        Data(people=[]),
    ),
    (
        "My name is Jeff, my hair is black and i am 6 feet tall. Anna has the same color hair as me.",
        Data(people=[Person(name="Jeff", height_in_meters="1.8288", hair_color="Black", city=None), Person(name="Anna", height_in_meters=None, hair_color="Black", city=None)]),
    )
]

messages = []

for txt, tool_call in examples:
    if tool_call.people:
        ai_response = "Detected people"
    else:
        ai_response = "Detected no people"
    messages.extend(
        tool_example_to_messages(txt, [tool_call], ai_response=ai_response)
    )

# for message in messages:
#     message.pretty_print()


# Define a custom prompt to provide instructions and any additional context.
# 1) You can add examples into the prompt template to improve extraction quality
# 2) Introduce additional parameters to take context into account (e.g., include metadata
#    about the document from which the text was extracted.)
prompt_template = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an expert extraction algorithm. "
            "Only extract relevant information from the text. "
            "If you do not know the value of an attribute asked to extract, "
            "return null for the attribute's value.",
        ),
        (
            "human", 
            "{text}"
        ),
    ]
)


# Access the API key
api_key = os.getenv("OPENAI_API_KEY")

# Initialize the ChatOpenAI model
model = ChatOpenAI(
    openai_api_key=api_key,
    model="gpt-4.1-mini",  # or gpt-4, etc.
    temperature=0.2,
)

structured_llm = model.with_structured_output(schema=Data)

text = "Alan Smith is 6 feet tall and has black hair. He lives in New York, USA. Anna has the same hair color, but she is 5 feet tall and lives in San Francisco. John is 5.8 feet tall, has brown hair, and lives in Los Angeles. Mary is 5.5 feet tall, has blonde hair, and lives together with John."
prompt = prompt_template.invoke({"text": text})
structured_output = structured_llm.invoke(prompt)

print(f"Extracted structured output: {structured_output}")

message_no_extraction = {
    "role": "user",
    "content": "The solar system is large, but earth has only 1 moon.",
}
structured_output_no_extraction = structured_llm.invoke(messages + [message_no_extraction])

print(f"Extracted structured output: {structured_output_no_extraction}")

