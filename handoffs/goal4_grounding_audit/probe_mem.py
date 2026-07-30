import os, sys
sys.path.insert(0, r"C:\Users\evely\Documents\AI_Project\assistant")
os.chdir(r"C:\Users\evely\Documents\AI_Project\assistant")
import main as assistant_main

cands = [
 "What hardware does the developer own? Just list it.",
 "Which graphics card does the developer own?",
 "What GPU does the developer own, and what single-board computer do they own?",
 "The developer owns some hardware. Name the GPU and the single-board computer.",
 "What do you remember about the developer's hardware and the robot arm?",
 "What is the developer building, besides you?",
]
for q in cands:
    p = assistant_main.build_system_prompt(q)
    i = p.find("Potentially relevant stored notes:")
    j = p.find("Offline reference excerpts", i)
    print("Q:", q)
    print("   NOTES:", repr(p[i+34:j].strip())[:500])
    print()
