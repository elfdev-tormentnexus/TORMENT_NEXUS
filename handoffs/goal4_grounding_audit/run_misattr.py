import os, sys, json, time
sys.path.insert(0, r"C:\Users\evely\Documents\AI_Project\assistant")
os.chdir(r"C:\Users\evely\Documents\AI_Project\assistant")
import requests
from core.config import SERVER_URL, MODEL_REQUEST_HEADERS
import main as assistant_main

OUT = r"C:\Users\evely\AppData\Local\Temp\claude\C--Users-evely-Documents-AI-Project\e221798d-31d5-4440-86e8-bc1d8333775a\scratchpad\results.jsonl"

TARGETS = [
    ("persona",    "assistant/core/persona.py"),
    ("srcaware",   "assistant/core/source_awareness.py"),
    ("memlogic",   "assistant/memory/memory_logic.py"),
    ("consume",    "assistant/core/consume.py"),
    ("vecpanel",   "assistant/ui/vector_panel.py"),
    ("voicesess",  "assistant/voice/session.py"),
]

ROUND = int(sys.argv[1]) if len(sys.argv) > 1 else 1

def ask(question):
    prompt = assistant_main.build_system_prompt(question)
    body = [{"role": "system", "content": prompt}] + [{"role": "user", "content": question}]
    t0 = time.time()
    r = requests.post(SERVER_URL + "/v1/chat/completions",
                      headers=MODEL_REQUEST_HEADERS,
                      json={"messages": body, "max_tokens": 180, "temperature": 0.8,
                            "stream": False,
                            "chat_template_kwargs": {"enable_thinking": False}},
                      timeout=180)
    dt = time.time() - t0
    return r.json()["choices"][0]["message"]["content"].strip(), dt

for key, path in TARGETS:
    q = "What does %s contain?" % path
    try:
        a, dt = ask(q)
    except Exception as e:
        a, dt = "ERROR: %r" % (e,), -1.0
    rec = {"round": ROUND, "key": key, "path": path, "q": q, "a": a, "secs": round(dt, 1)}
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("=" * 70)
    print("[r%d %s] %.1fs  Q: %s" % (ROUND, key, dt, q))
    print(a)
    sys.stdout.flush()
