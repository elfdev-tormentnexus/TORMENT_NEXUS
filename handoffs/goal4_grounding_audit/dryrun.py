import os, sys, json
sys.path.insert(0, r"C:\Users\evely\Documents\AI_Project\assistant")
os.chdir(r"C:\Users\evely\Documents\AI_Project\assistant")
import main as assistant_main

QS = {
 "fact": "What is the capital city of Australia, and which Australian city has the largest population? Answer in one short sentence.",
 "math": "A shop sells pens at 3 for $4.50. What do 11 pens cost? Show the arithmetic.",
 "summ": ("Summarise the following passage in exactly one sentence. Passage: "
          "\"In 1854 a physician named John Snow traced a cholera outbreak in Soho, London, "
          "to a single public water pump on Broad Street. He mapped the deaths street by "
          "street, noticed that they clustered around that one pump, and persuaded the "
          "parish to remove its handle. Cases fell away. The episode is remembered as an "
          "early example of epidemiology done by careful observation rather than by theory.\""),
 "oper": "What hardware does the developer own? Just list it.",
}

orig = assistant_main._self_knowledge_context
manifest_probe = orig()
print("=== LIVE MANIFEST (first 400 chars) ===")
print(manifest_probe[:400])
print("=== len manifest:", len(manifest_probe))

for k, q in QS.items():
    g = assistant_main.build_system_prompt(q)
    assistant_main._self_knowledge_context = lambda: ""
    u = assistant_main.build_system_prompt(q)
    assistant_main._self_knowledge_context = orig
    marker_ok = ("96,308 lines" not in u) and ("Your own source" not in u)
    print(f"\n--- {k} ---")
    print("grounded len", len(g), "ungrounded len", len(u), "delta", len(g)-len(u))
    print("manifest absent from ungrounded:", marker_ok)
    print("manifest present in grounded:", "Your own source" in g)
    # show the memory block that got retrieved
    i = g.find("Potentially relevant stored notes:")
    print("memory block:", repr(g[i:i+400]))

# clock stability check
import time
a = assistant_main.build_system_prompt("x")
time.sleep(2)
b = assistant_main.build_system_prompt("x")
print("\nprompt byte-identical across 2s:", a == b)
