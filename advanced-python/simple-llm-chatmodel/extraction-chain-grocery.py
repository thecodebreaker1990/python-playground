from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

# Access the API key
api_key = os.getenv("OPENAI_API_KEY")

class GroceryItem(BaseModel):
    # Note that:
    # 1. Each field is an `optional` -- this allows the model to decline to extract it!
    # 2. Each field has a `description` -- this description is used by the LLM.
    # Having a good description can help improve extraction results.
    name: Optional[str] = Field(default=None, description="The name of the item")
    category: Optional[str] = Field(default=None, description="The category of the grocery item")

class Data(BaseModel):
    """Extracted data about grocery item."""

    # Creates a model so that we can extract multiple entities.
    matched_items: List[GroceryItem]

# Initialize the ChatOpenAI model
llm = ChatOpenAI(
    openai_api_key=api_key,
    model="gpt-4.1-mini",  # or gpt-4, etc.
    temperature=0.2,
)

# Your grocery list
my_grocery_items = [
    "Ariel Liquid 1L",
    "Wheel Detergent Powder 500g",
    "Godrej No.1 Soap",
    "Nirma Washing Powder",
    "Dove Soap",
    "Cumin Seeds",
    "Surf Excel Matic Liquid",
    "Colgate",
    "Sensodyne",
]

parser = PydanticOutputParser(pydantic_object=Data)

# Prompt Template
prompt = PromptTemplate(
    template="""
You are a helpful shopping assistant.
From the following list of grocery items:

{grocery_list}

Identify which ones belong to the broad category: "{category}"

Respond in this JSON format:
{format_instructions}
""",
    input_variables=["category", "grocery_list"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

# Run it
category = "toothpaste"
formatted_prompt = prompt.format(
    category=category,
    grocery_list=", ".join(my_grocery_items)
)

response = llm.invoke(formatted_prompt)
print(f"🛒 Response: {response}")
# parsed = parser.parse(response)

# print(f"🛒 Detergent items matched: {parsed.matched_items}")