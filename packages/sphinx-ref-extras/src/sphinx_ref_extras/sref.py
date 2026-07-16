"""`sref` role: 同名 section label のうち toctree 上で最近傍のものへ解決する。

section title を key に (docname, labelid, sectname) を env.scoped_labels へ蓄積し、
参照元から toctree 距離が最小の候補を選ぶ。env 属性への蓄積のため、incremental
rebuild 用の purge と parallel read 用の merge を明示的に登録する。
"""

from __future__ import annotations

from collections import defaultdict, deque

from docutils import nodes
from sphinx import addnodes
from sphinx.util import logging
from sphinx.util.nodes import clean_astext, make_refnode

logger = logging.getLogger(__name__)


def _store(env):
    if not hasattr(env, "scoped_labels"):
        env.scoped_labels = defaultdict(list)
    return env.scoped_labels


def register_scoped_labels(app, document):
    env = app.env
    store = _store(env)
    docname = env.current_document.docname
    for node in document.findall(nodes.section):
        title = node[0]
        name = nodes.fully_normalize_name(title.astext())
        labelid = node["ids"][0]
        sectname = clean_astext(title)
        store[name].append((docname, labelid, sectname))


def purge_scoped_labels(app, env, docname):
    store = getattr(env, "scoped_labels", None)
    if not store:
        return
    for name in list(store):
        kept = [c for c in store[name] if c[0] != docname]
        if kept:
            store[name] = kept
        else:
            del store[name]


def merge_scoped_labels(app, env, docnames, other):
    other_store = getattr(other, "scoped_labels", None)
    if not other_store:
        return
    store = _store(env)
    for name, candidates in other_store.items():
        store[name].extend(candidates)


def sref_role(name, rawtext, text, lineno, inliner, options=None, content=None):
    env = inliner.document.settings.env
    node = addnodes.pending_xref(
        rawtext,
        refdomain=None,
        reftype="sref",
        reftarget=nodes.fully_normalize_name(text),
        refexplicit=False,
        refdoc=env.docname,
    )
    node += nodes.Text(text)
    return [node], []


def _build_toctree_graph(env):
    graph = defaultdict(set)
    for parent, children in env.toctree_includes.items():
        for child in children:
            graph[parent].add(child)
            graph[child].add(parent)
    return graph


def _distance(graph, src, dst):
    if src == dst:
        return 0
    visited = {src}
    q = deque([(src, 0)])
    while q:
        node, d = q.popleft()
        for nxt in graph[node]:
            if nxt == dst:
                return d + 1
            if nxt not in visited:
                visited.add(nxt)
                q.append((nxt, d + 1))
    return float("inf")


def resolve_sref(app, env, node, contnode):
    if node.get("reftype") != "sref":
        return None

    target = node["reftarget"]
    candidates = getattr(env, "scoped_labels", {}).get(target)
    if not candidates:
        logger.warning("sref target not found: %s", target, location=node)
        return None

    src_docname = node["refdoc"]
    graph = _build_toctree_graph(env)

    best = min(candidates, key=lambda c: _distance(graph, src_docname, c[0]))
    docname, labelid, sectname = best

    if len({d for d, _, _ in candidates}) > 1:
        logger.info(
            "sref '%s' is ambiguous (%d candidates); chose %s (nearest to %s)",
            target, len(candidates), docname, src_docname,
        )

    return make_refnode(app.builder, src_docname, docname, labelid, contnode, sectname)


def setup(app):
    app.add_role("sref", sref_role)
    app.connect("doctree-read", register_scoped_labels)
    app.connect("env-purge-doc", purge_scoped_labels)
    app.connect("env-merge-info", merge_scoped_labels)
    app.connect("missing-reference", resolve_sref)
    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
