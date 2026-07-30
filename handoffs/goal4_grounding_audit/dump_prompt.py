import os, sys, io
sys.path.insert(0, r"C:\Users\evely\Documents\AI_Project\assistant")
os.chdir(r"C:\Users\evely\Documents\AI_Project\assistant")
import main as assistant_main

q = "What does assistant/core/persona.py contain?"
p = assistant_main.build_system_prompt(q)
out = r"C:\Users\evely\AppData\Local\Temp\claude\C--Users-evely-Documents-AI-Project\e221798d-31d5-4440-86e8-bc1d8333775a\scratchpad\system_prompt.txt"
with open(out, "w", encoding="utf-8") as f:
    f.write(p)
print("LEN", len(p))
