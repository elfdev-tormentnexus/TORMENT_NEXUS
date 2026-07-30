import os, sys, time, json
sys.path.insert(0, r"C:\Users\evely\Documents\AI_Project\assistant")
os.chdir(r"C:\Users\evely\Documents\AI_Project\assistant")
import requests
from core.config import SERVER_URL, MODEL_REQUEST_HEADERS
import main as assistant_main

# questions passed as a JSON file path: list of [tag, question, repeats]
spec_path = sys.argv[1]
out_path = sys.argv[2]
with open(spec_path, "r", encoding="utf-8") as h:
    spec = json.load(h)

results = []
for tag, question, repeats in spec:
    for i in range(repeats):
        t0 = time.time()
        prompt = assistant_main.build_system_prompt(question)
        body = [{"role": "system", "content": prompt},
                {"role": "user", "content": question}]
        try:
            r = requests.post(SERVER_URL + "/v1/chat/completions",
                              headers=MODEL_REQUEST_HEADERS,
                              json={"messages": body, "max_tokens": 180,
                                    "temperature": 0.8, "stream": False,
                                    "chat_template_kwargs": {"enable_thinking": False}},
                              timeout=600)
            answer = r.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            answer = "<<REQUEST FAILED: %s>>" % exc
        dt = time.time() - t0
        rec = {"tag": tag, "run": i + 1, "question": question,
               "answer": answer, "seconds": round(dt, 1)}
        results.append(rec)
        print("=" * 70, flush=True)
        print("[%s run %d]  %.1fs" % (tag, i + 1, dt), flush=True)
        print("Q: " + question, flush=True)
        print("A: " + answer, flush=True)
        with open(out_path, "w", encoding="utf-8") as h:
            json.dump(results, h, indent=1, ensure_ascii=False)

print("\nDONE %d requests" % len(results), flush=True)
