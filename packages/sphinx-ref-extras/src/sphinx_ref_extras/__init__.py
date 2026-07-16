"""Standalone Sphinx reference/label extensions.

Each submodule is an independent Sphinx extension; add the ones you want to the
``extensions`` list in ``conf.py``:

- ``sphinx_ref_extras.sref`` — ``sref`` role resolving to the nearest same-named
  section label along the toctree.
- ``sphinx_ref_extras.autosectionprefix`` — register a delimiter-scoped prefix of
  a section title as a ``std:label``.
- ``sphinx_ref_extras.underscore_fallback`` — resolve unresolved ``word_``
  references to a glossary term or ``std:label``.
"""
