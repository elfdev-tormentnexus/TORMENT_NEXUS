import os, sys
sys.path.insert(0, r"C:\Users\evely\Documents\AI_Project\assistant")
os.chdir(r"C:\Users\evely\Documents\AI_Project\assistant")
import main as assistant_main
SP = r"C:\Users\evely\AppData\Local\Temp\claude\C--Users-evely-Documents-AI-Project\e221798d-31d5-4440-86e8-bc1d8333775a\scratchpad"
Q = "What does assistant/memory/memory_logic.py contain?"
p = assistant_main.build_system_prompt(Q)
open(SP + r"\prompt_grounded.txt", "w", encoding="utf-8").write(p)
for k in ["memory_logic", "assistant/memory", "memory retrieval", "storage", "word-overlap", "superseding", "memory"]:
    print(repr(k), "->", p.count(k))
assistant_main._self_knowledge_context = lambda: ""
p2 = assistant_main.build_system_prompt(Q)
open(SP + r"\prompt_ungrounded.txt", "w", encoding="utf-8").write(p2)
print("grounded len", len(p), "ungrounded len", len(p2))
print("manifest gone:", "96,308" not in p2 and "Your own source" not in p2)
