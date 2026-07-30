import os, sys, json, time
sys.path.insert(0, r"C:\Users\evely\Documents\AI_Project\assistant")
os.chdir(r"C:\Users\evely\Documents\AI_Project\assistant")
import requests
from core.config import SERVER_URL, MODEL_REQUEST_HEADERS
import main as assistant_main

SEQS = json.load(open(sys.argv[1], "r", encoding="utf-8"))

for seq in SEQS:
    label = seq["label"]
    history = []
    print("=" * 78)
    print("SEQUENCE:", label)
    print("=" * 78)
    for i, q in enumerate(seq["turns"], start=1):
        prompt = assistant_main.build_system_prompt(q)
        body = [{"role": "system", "content": prompt}] + history + [{"role": "user", "content": q}]
        t0 = time.time()
        r = requests.post(SERVER_URL + "/v1/chat/completions",
                          headers=MODEL_REQUEST_HEADERS,
                          json={"messages": body, "max_tokens": 180, "temperature": 0.8,
                                "stream": False,
                                "chat_template_kwargs": {"enable_thinking": False}},
                          timeout=300)
        answer = r.json()["choices"][0]["message"]["content"].strip()
        dt = time.time() - t0
        print("\n--- %s TURN %d (%.1fs) ---" % (label, i, dt))
        print("Q: " + q)
        print("A: " + answer)
        sys.stdout.flush()
        history = history + [{"role": "user", "content": q},
                             {"role": "assistant", "content": answer}]
print("\nDONE")
