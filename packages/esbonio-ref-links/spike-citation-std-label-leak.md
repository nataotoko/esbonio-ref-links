# Spike: citation label が `std:label` として objects DB に漏れ出す件

- 日付: 2026-07-24
- 発端: `[CITE]_` citation reference の clickable link 化 (`document_links.py` /
  `object_locations.py`) を実機検証中、esbonio の objects DB に
  `('cit2002', 'std', 'label', 'index', ...)` という想定外の行が見つかった
  (citation 自体は別途 `('CIT2002', 'citation', 'label', 'index', ...)` として
  正しく登録されている、その上での重複)。

## 問い

なぜ citation の定義 (`.. [CIT2002] ...`) が、`:ref:` が引く Sphinx の
`std:label` 名前空間にも、正規化された小文字 (`cit2002`) で登録されるのか。
docutils の想定 use case は何か。

## 発見した事実(実機デバッグで検証済み)

1. docutils の citation 構文はパース時
   (`docutils/parsers/rst/states.py:2036-2053` の `citation()`) に
   `document.note_explicit_target(citation, citation)` を呼ぶ。これは
   `.. _name:` ハイパーリンクターゲット・footnote・citation が共有する汎用の
   「明示的ターゲット登録」機構であり、citation 固有のものではない。
2. Sphinx の `StandardDomain.process_doc()`
   (`sphinx/domains/std/__init__.py:937-993`) は、この共有機構に登録された
   全ての名前を拾い集めて `:ref:` 名前空間の label にしようとする。footnote
   は明示的に除外している
   (`node.tagname == 'footnote'` で `continue`) が、**citation を除外する
   分岐が無い**。
3. ただし citation ノードは
   section/rubric/enumerable_node/term/field_name/toctree caption の
   いずれでもないため、表示名 (sectname) を伴う `self.labels` には登録され
   ない(else 節の最後で `continue` される)。
4. 一方 `self.anonlabels` には無条件に登録される
   (`self.anonlabels[name] = docname, labelid` は上記の `continue` より前で
   実行される。`note_explicit_target` を通る全ターゲットが対象)。
5. `StandardDomain.get_objects()`
   (`sphinx/domains/std/__init__.py:1332-1354`) の末尾に、`self.labels` に
   無い `anonlabels` を `objtype='label'` としてフォールバック yield する
   処理 (`# add anonymous-only labels as well`) があり、ここで citation の
   正規化名がすり抜けて `std:label` として objects DB に現れる。

再現手順・実測値は `tests/fixture/index.rst` の `CIT2002` citation で確認済み
(venv: このリポジトリの `.venv`, docutils==0.22.4, sphinx==9.1.0, esbonio==2.1.0):

```
std.labels.get('cit2002')      -> None
std.anonlabels.get('cit2002')  -> ('index', 'cit2002')
std.get_objects() に          -> ('cit2002', 'cit2002', 'label', 'index', 'cit2002', -1) が実在
note_object('label', 'cit2002', ...) の呼び出しは無い(self.objects 経由ではなく anonlabels フォールバック経由と確認)
```

## 結論

- Sphinx 側の非対称な除外処理(footnote は除外、citation は除外し忘れ)による
  もので、docutils が想定した use case ではない。docutils の
  `note_explicit_target` は「文書内で一意なクロスリファレンス可能ターゲット」
  を登録する汎用機構であり、`:ref:`/`std:label` という概念自体が docutils
  には存在しない。
- `esbonio-ref-links` の `[CITE]_` 対応
  (`CITATION_REF` / `RefLinksFeature._citation()` /
  `object_locations.py` の citation INSERT 処理)には実害なし。
  `HYPERLINK_REF` は `[CITE]_` という構文にマッチしないため、二重解決は
  発生しない。
- 潜在的な副作用: 誰かが `cit2002_`(正規化済み小文字 + 末尾アンダースコア)
  という named hyperlink reference を書くと、既存の `resolve_named` →
  `find_object(OBJECT_TYPES)` 経由でこの citation 定義位置に(意図せず)
  リンクされ得る。これは Sphinx 自体の挙動であり、esbonio-ref-links 側の
  バグではない。
- **対応不要と判断。現状のコードは変更しない。**

## 参照ソース

- `docutils/parsers/rst/states.py:2036-2053` (`citation()`)
- `docutils/nodes.py:2002-2007` (`note_explicit_target`)
- `sphinx/domains/std/__init__.py:937-993` (`process_doc`, footnote 除外・
  citation 漏れの分岐)
- `sphinx/domains/std/__init__.py:1332-1354` (`get_objects`,
  anonymous-only labels フォールバック)
- `sphinx/domains/citation.py` (`CitationDomain`, `get_objects()` 未実装 →
  citation が objects DB に登録されない根本理由。今回の機能実装のきっかけ)
- `esbonio/sphinx_agent/handlers/domains.py`
  (`DomainObjects.commit`, 全 domain の `get_objects()` を無条件に収集)
