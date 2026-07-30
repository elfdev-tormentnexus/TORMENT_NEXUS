import os, sys, time
sys.path.insert(0, r"C:\Users\evely\Documents\AI_Project\assistant")
os.chdir(r"C:\Users\evely\Documents\AI_Project\assistant")
import requests
from core.config import SERVER_URL, MODEL_REQUEST_HEADERS
import main as assistant_main

q = "How many files are in assistant/core?"
prompt = assistant_main.build_system_prompt(q)
for i in range(3):
    t = time.time()
    r = requests.post(SERVER_URL + "/v1/chat/completions",
                      headers=MODEL_REQUEST_HEADERS,
                      json={"messages": [{"role": "system", "content": prompt},
                                         {"role": "user", "content": q}],
                            "max_tokens": 180, "temperature": 0.8, "stream": False,
                            "chat_template_kwargs": {"enable_thinking": False}},
                      timeout=180)
    el = time.time() - t
    u = r.json().get("usage", {})
    print(f"run {i}: {el:.1f}s  prompt_tokens={u.get('prompt_tokens')} completion={u.get('completion_tokens')}")
    print("   ", r.json()["choices"][0]["message"]["content"].strip()[:200].replace("\n", " "))
