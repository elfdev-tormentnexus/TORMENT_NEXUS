import os, sys, json, time
sys.path.insert(0, r"C:\Users\evely\Documents\AI_Project\assistant")
os.chdir(r"C:\Users\evely\Documents\AI_Project\assistant")
import requests
from core.config import SERVER_URL, MODEL_REQUEST_HEADERS
import main as assistant_main

OUT = r"C:\Users\evely\AppData\Local\Temp\claude\C--Users-evely-Documents-AI-Project\e221798d-31d5-4440-86e8-bc1d8333775a\scratchpad\contam_results.jsonl"

QS = {
 "fact": "What is the capital city of Australia, and which Australian city has the largest population? Answer in one short sentence.",
 "math": "A shop sells pens at 3 for $4.50. What do 11 pens cost? Show the arithmetic.",
 "summ": ("Summarise the following passage in exactly one sentence. Passage: "
          "\"In 1854 a physician named John Snow traced a cholera outbreak in Soho, London, "
          "to a single public water pump on Broad Street. He mapped the deaths street by "
          "street, noticed that they clustered around that one pump, and persuaded the "
          "parish to remove its handle. Cases fell away. The episode is remembered as an "
          "early example of epidemiology done by careful observation rather than by theory.\""),
 "oper": "The developer owns some hardware. Name the GPU and the single-board computer.",
}

ORIG = assistant_main._self_knowledge_context

def prompt_for(q, grounded):
    if grounded:
        assistant_main._self_knowledge_context = ORIG
    else:
        assistant_main._self_knowledge_context = lambda: ""
    p = assistant_main.build_system_prompt(q)
    assistant_main._self_knowledge_context = ORIG
    if grounded:
        assert "Your own source as it is on disk right now" in p, "manifest missing from grounded"
    else:
        assert "Your own source as it is on disk right now" not in p, "MONKEYPATCH FAILED"
        assert "96,308 lines" not in p, "MONKEYPATCH FAILED (count leaked)"
    return p

def ask(key, grounded, rep):
    q = QS[key]
    p = prompt_for(q, grounded)
    body = [{"role": "system", "content": p}, {"role": "user", "content": q}]
    t0 = time.time()
    r = requests.post(SERVER_URL + "/v1/chat/completions",
                      headers=MODEL_REQUEST_HEADERS,
                      json={"messages": body, "max_tokens": 180, "temperature": 0.8,
                            "stream": False,
                            "chat_template_kwargs": {"enable_thinking": False}},
                      timeout=300)
    dt = time.time() - t0
    ans = r.json()["choices"][0]["message"]["content"].strip()
    rec = {"key": key, "grounded": grounded, "rep": rep, "secs": round(dt, 1),
           "prompt_chars": len(p), "answer": ans, "question": q}
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"[{key} grounded={grounded} rep={rep}] {dt:.1f}s promptchars={len(p)}")
    print(ans)
    print("-" * 70, flush=True)

plan = json.loads(sys.argv[1])
for key, grounded, rep in plan:
    ask(key, grounded, rep)
print("DONE")
