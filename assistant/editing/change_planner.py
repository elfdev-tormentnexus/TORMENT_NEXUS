import os
from datetime import datetime


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANS_FOLDER = os.path.join(PROJECT_ROOT, "memory", "change_plans")


def save_plan(filename, request, steps):

    os.makedirs(
        PLANS_FOLDER,
        exist_ok=True
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    path = os.path.join(PLANS_FOLDER, f"plan_{timestamp}.txt")

    counter = 1
    while os.path.exists(path):
        path = os.path.join(PLANS_FOLDER, f"plan_{timestamp}_{counter}.txt")
        counter += 1

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write("CHANGE PLAN\n")
        f.write("============\n\n")

        f.write(
            f"Target file:\n{filename}\n\n"
        )

        f.write(
            f"Request:\n{request}\n\n"
        )

        f.write(
            "Steps:\n"
        )

        for step in steps:
            f.write(
                f"- {step}\n"
            )

    return path
