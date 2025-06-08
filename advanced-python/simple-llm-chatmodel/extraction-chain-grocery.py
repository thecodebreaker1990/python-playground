from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
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
groceries = [
    "Poha",
    "Oil mustard - 2lt",
    "Saffola - 1lt",
    "Rice 5 kg",
    "Ghee",
    "Salt",
    "Elachi",
    "Coriander powder",
    "Jeera powder",
    "Cornflour",
    "Biscuit",
    "Poppy seeds",
    "Dry red chilli",
    "Peanuts",
    "Mustard seeds",
    "Egg masala",
    "Aashirwad atta - 2kg",
    "Maida - 1Kg",
    "Pasta raw",
    "Vermicelli",
    "Sattu",
    "Flask seeds",
    "Chilli sauce",
    "Kalonji",
    "Haldiram snacks",
    "Sabudana papad"
]

household_items = [
    "Ropes",
    "Garbage bags",
    "Pril",
    "Flush matic",
    "Handwash",
    "Wipes",
    "Tissue",
    "Scotch brite",
    "Naphthalene",
    "Surf excel",
    "Lizol"
]

# Define few-shot examples for different categories
# Create example messages as dictionaries for FewShotChatMessagePromptTemplate
examples = [
    {
        "input": "From the following list of grocery items: Poha, Oil mustard - 2lt, Saffola - 1lt, Rice 5 kg, Ghee, Salt\n\nIdentify which ones belong to the broad category: 'Oils & Ghee'\n\nOnly extract relevant information from the text.\nIf you do not know the category or are unsure, return null for the attribute's value.",
        "output": '{"matched_items": [{"name": "Oil mustard - 2lt", "category": "Oils & Ghee"}, {"name": "Saffola - 1lt", "category": "Oils & Ghee"}, {"name": "Ghee", "category": "Oils & Ghee"}]}'
    },
    {
        "input": "From the following list of grocery items: Salt, Elachi, Coriander powder, Jeera powder, Cornflour, Biscuit\n\nIdentify which ones belong to the broad category: 'Spices & Seasonings'\n\nOnly extract relevant information from the text.\nIf you do not know the category or are unsure, return null for the attribute's value.",
        "output": '{"matched_items": [{"name": "Salt", "category": "Spices & Seasonings"}, {"name": "Elachi", "category": "Spices & Seasonings"}, {"name": "Coriander powder", "category": "Spices & Seasonings"}, {"name": "Jeera powder", "category": "Spices & Seasonings"}]}'
    },
    {
        "input": "From the following list of grocery items: Poha, Rice 5 kg, Aashirwad atta - 2kg, Maida - 1Kg, Pasta raw, Vermicelli\n\nIdentify which ones belong to the broad category: 'Grains & Cereals'\n\nOnly extract relevant information from the text.\nIf you do not know the category or are unsure, return null for the attribute's value.",
        "output": '{"matched_items": [{"name": "Poha", "category": "Grains & Cereals"}, {"name": "Rice 5 kg", "category": "Grains & Cereals"}, {"name": "Aashirwad atta - 2kg", "category": "Grains & Cereals"}, {"name": "Maida - 1Kg", "category": "Grains & Cereals"}, {"name": "Pasta raw", "category": "Grains & Cereals"}, {"name": "Vermicelli", "category": "Grains & Cereals"}]}'
    }
]

few_shot_prompt = FewShotChatMessagePromptTemplate(
    example_prompt=ChatPromptTemplate.from_messages([
        ("human", "{input}"),
        ("ai", "{output}"),
    ]),
    examples=examples
)

print(few_shot_prompt.invoke({}).to_messages())

# Create a comprehensive prompt template with few-shot examples
system_message = """You are a helpful shopping assistant that categorizes grocery items.

Your task is to:
1. Analyze the given list of grocery items
2. Identify which items belong to the specified category
3. Extract only the relevant items that match the category
4. Return null for items that don't match or if you're unsure

Be precise and only include items that clearly belong to the specified category."""

# Create the chat prompt template with examples
prompt_template = ChatPromptTemplate.from_messages([
    ("system", system_message),
    few_shot_prompt,
    ("human", """From the following list of grocery items:

{grocery_list}

Identify which ones belong to the broad category: "{category}"

Only extract relevant information from the text.
If you do not know the category or are unsure, return null for the attribute's value.""")
])

# Create structured LLM
structured_llm = llm.with_structured_output(schema=Data)

# Create the chain
chain = prompt_template | structured_llm

# Function to run extraction for different categories
def extract_items_by_category(category_name, item_list):
    """Extract items that belong to a specific category"""
    response = chain.invoke({
        "category": category_name,
        "grocery_list": ", ".join(item_list)
    })
    return response

# Test with different categories
categories_to_test = [
    "Oils & Ghee",
    "Spices & Seasonings", 
    "Grains & Cereals",
    "Snacks & Confectionery"
]

print("🛒 Enhanced Grocery Item Extraction with Few-Shot Prompting")
print("=" * 60)

for category in categories_to_test:
    print(f"\n📂 Category: {category}")
    result = extract_items_by_category(category, groceries)
    
    if result.matched_items:
        for item in result.matched_items:
            print(f"  ✓ {item.name} → {item.category}")
    else:
        print(f"  ❌ No items found for category: {category}")

# Also test with household items to show it correctly identifies non-matches
print(f"\n📂 Category: Oils & Ghee (Testing with household items)")
household_result = extract_items_by_category("Oils & Ghee", household_items)
if household_result.matched_items:
    for item in household_result.matched_items:
        print(f"  ✓ {item.name} → {item.category}")
else:
    print(f"  ✅ Correctly identified no oils/ghee in household items")