import os, sys, json, time
sys.path.insert(0, r"C:\Users\evely\Documents\AI_Project\assistant")
os.chdir(r"C:\Users\evely\Documents\AI_Project\assistant")
import requests
from core.config import SERVER_URL, MODEL_REQUEST_HEADERS
import main as assistant_main

CALLS = 0
def ask(question, history=None, prompt=None, tag=""):
    global CALLS
    history = history or []
    if prompt is None:
        prompt = assistant_main.build_system_prompt(question)
    body = [{"role":"system","content":prompt}] + history + [{"role":"user","content":question}]
    t0=time.time()
    r = requests.post(SERVER_URL + "/v1/chat/completions",
        headers=MODEL_REQUEST_HEADERS,
        json={"messages": body, "max_tokens":180, "temperature":0.8, "stream":False,
              "chat_template_kwargs":{"enable_thinking":False}}, timeout=300)
    a = r.json()["choices"][0]["message"]["content"].strip()
    CALLS += 1
    print("### CALL %d [%s] %.1fs" % (CALLS, tag, time.time()-t0))
    print("Q:", question)
    print("A:", a)
    print("---", flush=True)
    return a, prompt
