from fastapi import FastAPI, HTTPException
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Dict
import os

load_dotenv()

app = FastAPI()

# Access the API key
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError("This operation can not be performed! Contact your System Administrator")

# Initialize the ChatOpenAI model
model = ChatOpenAI(
    openai_api_key=api_key,
    model="gpt-4.1-nano",  # or gpt-4, etc.
    temperature=0.2,
)

translation_prompt_template = ChatPromptTemplate.from_messages([
    ("system", "Translate the user input into {language}."),
    ("human", "{text}")
])

def generate_translations(texts: List[str], language: str) -> List[str]:
    prompts = [
        translation_prompt_template.invoke({"language": language, "text": text})
        for text in texts
    ]
    results = model.batch(prompts)
    return [res.content.strip() for res in results]

# Request model
class TranslationRequest(BaseModel):
    inputs: List[str]
    language: str

# Response model
class TranslationResponse(BaseModel):
    results: List[str]

# Endpoint
@app.post("/translate", response_model = TranslationResponse)
async def translate_batch(request: TranslationRequest):
    try:
        outputs = generate_translations(request.inputs, request.language)
        return TranslationResponse(results=outputs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# Request model
class TranslationBulkRequest(BaseModel):
    inputs: Dict[str, str]
    language: str

# Response model
class TranslationBulkResponse(BaseModel):
    results: Dict[str, str]
    
@app.post("/translate-bulk-json", response_model = TranslationBulkResponse)
async def translate_bulk_json_batch(request: TranslationBulkRequest):
    try:
        keys = list(request.inputs.keys())
        texts = list(request.inputs.values())
        translated_texts = generate_translations(texts, request.language)
        output_dict = dict(zip(keys, translated_texts))
        return TranslationBulkResponse(results=output_dict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))