from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from dotenv import load_dotenv
import os

load_dotenv()

# Access the API key
api_key = os.getenv("OPENAI_API_KEY")

tagging_prompt = ChatPromptTemplate.from_template(
    """
Extract the desired information from the following passage.

Only extract the properties mentioned in the 'Classification' function.

Passage:
{input}
"""
)

class Classification(BaseModel):
    sentiment: str = Field(description="The sentiment of the text")
    aggressiveness: int = Field(description="How aggressive the text is, on a scale from 1 to 10")
    language: str = Field(description="The language of the text")

# Initialize the ChatOpenAI model
model = ChatOpenAI(
    openai_api_key=api_key,
    model="gpt-4.1-mini",  # or gpt-4, etc.
    temperature=0.2,
)

# Structured LLM
structured_llm = model.with_structured_output(Classification)

input_texts = [
    "I’m so glad we finally got to work together; you’ve been amazing to collaborate with.",
    "Your presentation was okay, but it felt a little rushed at the end.",
    "I can’t believe you messed this up again—it’s so disappointing.",
    "What you did was completely unacceptable, and I’m beyond angry right now!",
    "The way you handled that situation was impressive and inspiring.",
    "It’s fine, I guess, but I expected a lot more from you.",
    "I feel heartbroken knowing we might never see each other again.",
    "This is the absolute worst service I’ve ever experienced in my life!"
    "We achieved the milestone ahead of time—fantastic job, everyone!"
    "You better fix this mess right now, or there will be serious consequences."
]

for idx, input_text in enumerate(input_texts, start=1):
    print(f"Processing input {idx}: {input_text}")
    
    # Prepare the prompt
    prompt = tagging_prompt.invoke({"input": input_text})
    response = structured_llm.invoke(prompt)
    print(response.model_dump())

    print("-" * 100)