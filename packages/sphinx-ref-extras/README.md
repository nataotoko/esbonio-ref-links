# sphinx-ref-extras

Three independent Sphinx extensions for reference/label handling. Add the ones
you want to the `extensions` list in `conf.py`:

- **`sphinx_ref_extras.sref`** — a `sref` role that resolves to the nearest
  same-named section label along the toctree (disambiguates duplicate section
  titles by toctree distance from the referencing document).
- **`sphinx_ref_extras.autosectionprefix`** — for section titles containing a
  configured delimiter, registers the part before the delimiter as a
  `docname:prefix` `std:label`. Configure with `autosectionprefix_delimiter`
  (default `""` = off, delegating entirely to `sphinx.ext.autosectionlabel`)
  and `autosectionprefix_strict` (default `False`).
- **`sphinx_ref_extras.underscore_fallback`** — resolves an unresolved `word_`
  reference to a glossary `term`, then to a `std:label`, before Sphinx's normal
  "undefined label" handling.

Each extension is self-contained; enable any subset.

## License

Apache-2.0.
