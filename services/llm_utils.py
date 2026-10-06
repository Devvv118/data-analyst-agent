import os
import httpx
import asyncio
from google import genai
from dotenv import load_dotenv
from datetime import date, timedelta
from typing import TypedDict, Union, Literal, Optional

load_dotenv()

try:
    api_key = os.getenv("GEMINI_KEY")
    client = genai.Client(api_key=api_key)

except Exception as e:
    print(f"Error initializing Gemini: {e}")
    client = None

DAILY_LIMIT = 0.2

class SuccessResponse(TypedDict):
    content: str

class ErrorResponse(TypedDict):
    error: Literal[True]
    message: str
    code: Optional[int]
    type: str
    model: str

class LLMError(Exception):
    def __init__(self, error: ErrorResponse):
        self.message = error["message"]
        self.model = error["model"]
        self.type = error["type"]

        super().__init__(self.message)

CommonReturn = Union[SuccessResponse, ErrorResponse]

async def daily_budget_exceeded() -> bool:
    token = os.getenv("AIPIPE_TOKEN")

    if not token:
        return True

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://aipipe.org/usage",
                headers={
                    "Authorization": f"Bearer {token}"
                }
            )

            response.raise_for_status()
            data = response.json()

            today = date.today()
            today = today.isoformat()

            today_cost = next(
                (
                    item["cost"]
                    for item in data.get("usage", [])
                    if item.get("date") == today
                ),
                0.0
            )

            print(f"today_cost: {today_cost}")
            return today_cost >= DAILY_LIMIT

    except Exception:
        return True

async def call_gpt(prompt: str, image_url:str = None) -> CommonReturn:
    url = "https://aipipe.org/openai/v1/chat/completions"
    token = os.getenv('AIPIPE_TOKEN')

    model = "gpt-4o-mini"

    if not token:
        return {
            "error": True,
            "message": "Missing API token",
            "code": None,
            "type": "AuthError",
            "model": model
        }

    if await daily_budget_exceeded():
        return {
            "error": True,
            "message": "Daily AI budget has been reached",
            "code": None,
            "type": "DailyBudgetExceeded",
            "model": model
        }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    if image_url:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]
    else:
        messages = [{"role": "user", "content": prompt}]

    json_data = {
        "model": "gpt-4o-mini",
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=json_data)
            response.raise_for_status()
            data = response.json()

            choices = data.get("choices")
            if not choices or not isinstance(choices, list):
                return {
                    "error": True,
                    "message": "Malformed response: missing choices",
                    "code": response.status_code,
                    "type": "MalformedResponse",
                    "model": model
                }

            message = choices[0].get("message")
            if not message or "content" not in message:
                return {
                    "error": True,
                    "message": "Malformed response: missing message content",
                    "code": response.status_code,
                    "type": "MalformedResponse",
                    "model": model
                }

            return {"content": message["content"]}

    except httpx.TimeoutException:
        return {
            "error": True,
            "message": "Request timed out",
            "code": None,
            "type": "TimeoutException",
            "model": model
        }
    except httpx.HTTPStatusError as e:
        return {
            "error": True,
            "message": f"Received HTTP {e.response.status_code} from API",
            "code": e.response.status_code,
            "type": "HTTPError",
            "model": model
        }
    except Exception as e:
        return {
            "error": True,
            "message": f"Unexpected error: {str(e)}",
            "code": None,
            "type": "UnexpectedError",
            "model": model
        }

async def call_gemini(prompt: str, model: str = "gemini-3.7-flash") -> CommonReturn:
    try:
        loop = asyncio.get_running_loop()

        def sync_gemini_call():
            response = client.models.generate_content(
                model=model,
                contents=prompt
            )

            return response

        response = await loop.run_in_executor(None, sync_gemini_call)

        if not response.candidates:
            return {
                "error": True,
                "message": "No candidates returned from Gemini.",
                "code": None,
                "type": "EmptyResponse",
                "model": model
            }

        content = response.candidates[0].content
        if not content.parts:
            return {
                "error": True,
                "message": "Gemini response has no parts.",
                "code": None,
                "type": "MalformedResponse",
                "model": model
            }

        return {"content": content.parts[0].text}

    except Exception as e:
        return {
            "error": True,
            "message": str(e),
            "code": None,
            "type": "UnexpectedError",
            "model": model
        }

async def call_llm(prompt: str, llm:str, model:str = "gemini-3.5-flash") -> Union[str, CommonReturn]:

    if llm == "gemini":

        result = await call_gemini(prompt, model=model)

        if "error" in result:
            print("gemini crashed")
            print(result.get("message", ""))
            result = await call_gpt(prompt)
        
    else:

        result = await call_gpt(prompt)        

        if "error" in result:
            print("gpt crashed")
            print(result.get("message", ""))

            if result["type"] == "HTTPError":
                result = await call_gpt(prompt)
            if "error" in result:
                print("GPT failed again, trying Gemini")
                result = await call_gemini(prompt, model=model)

    if "error" not in result:
        return result["content"]

    print("LLM Error")
    raise LLMError(result)
