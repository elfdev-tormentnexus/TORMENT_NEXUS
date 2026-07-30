import os, sys, json, time
sys.path.insert(0, r"C:\Users\evely\Documents\AI_Project\assistant")
os.chdir(r"C:\Users\evely\Documents\AI_Project\assistant")
import requests
from core.config import SERVER_URL, MODEL_REQUEST_HEADERS
import main as assistant_main

Q1 = "What does assistant/memory/memory_logic.py contain?"
Q2 = "I'm auditing the memory subsystem. Before I open anything, do you have any information about assistant/memory/memory_logic.py?"

def ask(q, tag):
    p = assistant_main.build_system_prompt(q)
    body = [{"role": "system", "content": p}, {"role": "user", "content": q}]
    t = time.time()
    r = requests.post(SERVER_URL + "/v1/chat/completions",
                      headers=MODEL_REQUEST_HEADERS,
                      json={"messages": body, "max_tokens": 180, "temperature": 0.8,
                            "stream": False,
                            "chat_template_kwargs": {"enable_thinking": False}},
                      timeout=900)
    a = r.json()["choices"][0]["message"]["content"].strip()
    print("=== %s (%.1fs) ===" % (tag, time.time() - t))
    print("Q:", q)
    print("A:", a)
    print("prompt_len:", len(p), "| 'memory_logic' in prompt:", "memory_logic" in p,
          "| manifest marker '96,308' in prompt:", "96,308" in p,
          "| 'Your own source' in prompt:", "Your own source" in p)
    print()
    sys.stdout.flush()
    return a

mode = sys.argv[1]

if mode == "grounded":
    for i in range(3):
        ask(Q1, "GROUNDED repeat %d" % (i + 1))
elif mode == "rephrase":
    ask(Q2, "GROUNDED rephrase")
elif mode == "ungrounded":
    assistant_main._self_knowledge_context = lambda: ""
    p = assistant_main.build_system_prompt(Q1)
    assert "96,308" not in p, "manifest still present!"
    assert "Your own source" not in p, "manifest still present!"
    assert "logs/autonomous_edits.log" not in p, "manifest still present!"
    print("ASSERTED: manifest removed. prompt_len=%d" % len(p))
    sys.stdout.flush()
    for i in range(3):
        ask(Q1, "UNGROUNDED repeat %d" % (i + 1))
