import pathlib
import sys

# Make the modules at the repo root importable (fixture -> tests -> root).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

project = "fixture"
author = "fixture"
release = "0.0.0"

extensions = [
    "sphinx.ext.autosectionlabel",
    "esbonio_object_locations",
]

autosectionlabel_prefix_document = True

exclude_patterns = ["_build"]
