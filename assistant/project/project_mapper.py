import os
import json


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROJECT_MAP = os.path.join(PROJECT_ROOT, "project", "project_map.json")


def build_project_map():

    assistant_folder = PROJECT_ROOT

    project = {
        "files": [],
        "folders": []
    }


    for root, dirs, files in os.walk(assistant_folder):

        dirs[:] = [
            d for d in dirs
            if d != "__pycache__"
        ]

        relative_folder = os.path.relpath(
            root,
            assistant_folder
        )

        if relative_folder != ".":
            project["folders"].append(
                relative_folder
            )


        for file in files:

            if file.endswith(".py"):

                full_path = os.path.join(
                    root,
                    file
                )

                relative_path = os.path.relpath(
                    full_path,
                    assistant_folder
                )

                project["files"].append(
                    relative_path
                )


    with open(
        PROJECT_MAP,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            project,
            f,
            indent=4
        )


    return project


def load_project_map():

    if not os.path.exists(PROJECT_MAP):
        return build_project_map()


    with open(
        PROJECT_MAP,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)