import os


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_FOLDER = os.path.join(PROJECT_ROOT, "memory")
APPROVAL_FILE = os.path.join(MEMORY_FOLDER, "approved_plan.txt")


def approve_plan(plan_path):

    os.makedirs(MEMORY_FOLDER, exist_ok=True)

    with open(
        APPROVAL_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(plan_path)

    return True



def get_approved_plan():

    if not os.path.exists(APPROVAL_FILE):
        return None


    with open(
        APPROVAL_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return f.read().strip()



def clear_approval():

    if os.path.exists(APPROVAL_FILE):
        os.remove(APPROVAL_FILE)
