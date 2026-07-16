import pathlib
import sys

# Make the package importable (fixture -> tests -> package root -> src).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

project = "fixture"
author = "fixture"
release = "0.0.0"

extensions = [
    "sphinx.ext.autosectionlabel",
    "esbonio_ref_links.object_locations",
]

autosectionlabel_prefix_document = True

exclude_patterns = ["_build"]
