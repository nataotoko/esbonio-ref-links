"""未解決の `word_` 参照を glossary term / std:label へ fallback 解決する。"""

from docutils import nodes
from docutils.transforms import Transform
from sphinx import addnodes


class UnderscoreTermFallback(Transform):
    """
    未解決の `word_` 参照を glossary term として解決を試みる。
    一致しなければ標準のSphinx動作(warning、-Wでエラー)に委ねる。
    優先度: 通常処理(640-670) < default_priority < DanglingReferences (850)

    注意: `.. _name:` 型の空 target は PropagateTargets (260) で次要素へ
    propagate されるため、その参照の refname 解決は 640-670 では起きず
    SphinxDanglingReferences (850) まで遅延する。この時点では refuri/refid
    の有無で解決可否を判定できないので、document.nameids に載る名前
    (文書内で解決可能、または重複 name の error 報告対象) は 850 に委ねる。
    """

    default_priority = 800

    def apply(self):
        env = self.document.settings.env
        for node in list(self.document.findall(nodes.reference)):
            if "refuri" in node or "refid" in node:
                continue
            refname = node.get("refname")
            if not refname:
                continue
            if refname in self.document.nameids:
                continue
            title = node.astext()
            xref = addnodes.pending_xref(
                title,
                refdomain="std",
                reftype="term",
                reftarget=refname,
                refexplicit=False,
                refwarn=True,
                refdoc=env.docname,
            )
            xref += nodes.Text(title)
            node.replace_self(xref)
            if refname in self.document.refnames:
                refs = [n for n in self.document.refnames[refname] if n is not node]
                if refs:
                    self.document.refnames[refname] = refs
                else:
                    del self.document.refnames[refname]


def resolve_std_label_fallback(app, env, node, contnode):
    """
    UnderscoreTermFallback が reftype="term" で作った pending_xref のうち、
    term として見つからなかったものを、最後に std:label としても試す。
    (:ref: 自身は node 作成時に fully_normalize_name 済みの reftarget を
    前提にしているため、ここで同じ正規化を自前で行う)
    見つからなければ None を返し、通常の "term not in glossary" warning に委ねる。
    """
    if node.get("reftype") != "term":
        return None
    std = env.domains.standard_domain
    target = nodes.fully_normalize_name(node["reftarget"])
    docname, labelid, sectname = std.labels.get(target, ("", "", ""))
    if not docname:
        docname, labelid = std.anonlabels.get(target, ("", ""))
        sectname = contnode.astext()
    if not docname:
        return None
    return std.build_reference_node(
        node["refdoc"], app.builder, docname, labelid, sectname, "ref"
    )


def setup(app):
    app.add_transform(UnderscoreTermFallback)
    app.connect("missing-reference", resolve_std_label_fallback)
    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
