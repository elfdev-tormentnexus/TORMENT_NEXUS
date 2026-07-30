import os, sys
sys.path.insert(0, r"C:\Users\evely\Documents\AI_Project\assistant")
os.chdir(r"C:\Users\evely\Documents\AI_Project\assistant")
import requests
from core.config import SERVER_URL, MODEL_REQUEST_HEADERS
import main as assistant_main

q = "What is the largest part of your source tree?"
prompt = assistant_main.build_system_prompt(q)
print("=== SERVER_URL:", SERVER_URL)
print("=== PROMPT CHARS:", len(prompt))
print("=== SELF-KNOWLEDGE BLOCK ===")
print(assistant_main._self_knowledge_context())
print("=== END BLOCK ===")

r = requests.post(SERVER_URL + "/v1/chat/completions",
                  headers=MODEL_REQUEST_HEADERS,
                  json={"messages": [{"role": "system", "content": prompt},
                                     {"role": "user", "content": q}],
                        "max_tokens": 120, "temperature": 0.8, "stream": False,
                        "chat_template_kwargs": {"enable_thinking": False}},
                  timeout=180)
print("=== HTTP", r.status_code)
print(r.json()["choices"][0]["message"]["content"].strip())
