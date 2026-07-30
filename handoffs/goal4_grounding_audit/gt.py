import ast, re, io
root = r"C:\Users\evely\Documents\AI_Project"
for rel in [r"assistant\memory\memory_logic.py", r"assistant\core\tutorial.py"]:
    p = root + "\\" + rel
    src = io.open(p, encoding="utf-8").read()
    t = ast.parse(src)
    classes = [n.name for n in ast.walk(t) if isinstance(n, ast.ClassDef)]
    funcs = [n.name for n in t.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
    print("==", rel, "lines:", len(src.splitlines()))
    print(" classes:", classes)
    print(" module funcs:", funcs)
    print(" imports:", sorted({(n.module or '') if isinstance(n,ast.ImportFrom) else ','.join(a.name for a in n.names) for n in ast.walk(t) if isinstance(n,(ast.Import,ast.ImportFrom))}))
    print(" '200' count:", src.count("200"))
    for i,l in enumerate(src.splitlines(),1):
        if "200" in l: print("   L%d: %s" % (i, l.strip()[:120]))
    # module-level list assignments with len
    for n in t.body:
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.List):
            for tgt in n.targets:
                if isinstance(tgt, ast.Name):
                    print("   LIST", tgt.id, "len", len(n.value.elts))
    for pat in ["open(", "json", "import os", "sqlite", "pickle", "def save", "def load", ".write"]:
        print("   pat %-10s -> %d" % (pat, src.count(pat)))
