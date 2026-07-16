"""delimiter-scoped section label 登録。

section title に `autosectionprefix_delimiter` が含まれる場合、delimiter より前を
`docname:prefix` へ正規化した std:label として standard domain に登録する。
delimiter が空 (機能off) の場合は公式 autosectionlabel に全て委ねる。
"""

from docutils import nodes
from sphinx.errors import ConfigError, SphinxError
from sphinx.util import logging
from sphinx.util.nodes import clean_astext

logger = logging.getLogger(__name__)


def validate_delimiter(app, config):
    delim = config.autosectionprefix_delimiter
    if delim and not delim.isascii():
        raise ConfigError(
            f"autosectionprefix_delimiter must be ASCII only: {delim!r}"
        )


def register_sections_as_label(app, document):
    delim = app.config.autosectionprefix_delimiter
    if not delim:
        return  # 機能off -> 全部公式extensionに任せる

    strict = app.config.autosectionprefix_strict
    domain = app.env.domains.standard_domain
    for node in document.findall(nodes.section):
        title = node[0]
        ref_name = getattr(title, "rawsource", title.astext())

        if delim not in ref_name:
            continue

        labelid = node["ids"][0]
        docname = app.env.current_document.docname
        sectname = clean_astext(title)
        ref_name = ref_name.split(delim, 1)[0].rstrip()
        name = nodes.fully_normalize_name(docname + ":" + ref_name)

        if name in domain.labels:
            msg = (
                "duplicate autosectionprefix label: %s (already defined in %s)",
                name,
                domain.labels[name][0],
            )
            if strict:
                raise SphinxError(msg[0] % msg[1:])
            logger.warning(*msg, location=node)
        domain.anonlabels[name] = docname, labelid
        domain.labels[name] = docname, labelid, sectname


def setup(app):
    app.add_config_value(
        "autosectionprefix_delimiter", "", "env", types=frozenset({str})
    )
    app.add_config_value(
        "autosectionprefix_strict", False, "env", types=frozenset({bool})
    )
    app.connect("config-inited", validate_delimiter)
    app.connect("doctree-read", register_sections_as_label)
    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
