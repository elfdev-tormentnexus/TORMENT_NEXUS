import os, sys, time
sys.path.insert(0, r"C:\Users\evely\Documents\AI_Project\assistant")
os.chdir(r"C:\Users\evely\Documents\AI_Project\assistant")
import requests
from core.config import SERVER_URL, MODEL_REQUEST_HEADERS
import main as assistant_main

qs = ["What does assistant/core/machinespirit.py contain?",
      "Does assistant/core/persona.py exist?",
      "Summarise in one sentence why the sky is blue.",
      "How many lines is docs/RESEARCHC_GOALS.md?"]
for q in qs:
    prompt = assistant_main.build_system_prompt(q)
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
    print(f"{el:6.1f}s  pt={u.get('prompt_tokens')} ct={u.get('completion_tokens')} :: {q}")
    print("    ", r.json()["choices"][0]["message"]["content"].strip()[:260].replace("\n", " "))
