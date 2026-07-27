import os

from core import file_utils


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def analyze_file(filename):

    try:
        filepath = file_utils.safe_join(PROJECT_ROOT, filename)
    except file_utils.PathError as e:
        return {"error": str(e)}

    if not os.path.exists(filepath):
        return None


    try:
        with open(
            filepath,
            "r",
            encoding="utf-8"
        ) as f:

            content = f.read()


        lines = content.splitlines()


        functions = []

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("def "):
                name = stripped.split("(")[0]
                name = name.replace("def ", "")
                functions.append(name)


        return {
            "file": filename,
            "lines": len(lines),
            "functions": functions,
            "size": len(content)
        }


    except Exception as e:
        return {
            "error": str(e)
        }
