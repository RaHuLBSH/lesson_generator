"""Environment-backed OpenAI-compatible chat client factory."""
import os

def create_client():
    from dotenv import load_dotenv
    from openai import OpenAI
    load_dotenv()
    key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Set LLM_API_KEY (or OPENAI_API_KEY) in the environment")
    return OpenAI(api_key=key, base_url=os.getenv("LLM_BASE_URL") or None)

def model_name() -> str:
    name = os.getenv("LLM_MODEL")
    if not name:
        raise RuntimeError("Set LLM_MODEL in the environment")
    return name
