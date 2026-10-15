import json
import tempfile
import unittest
from pathlib import Path

from helpers import commit, init_repo, load_doc_truth

dt = load_doc_truth()


def manifest(name, version):
    return json.dumps({"name": name, "version": version})


class CheckCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = init_repo(Path(tmp.name).resolve() / "r")

    def build(self, files):
        commit(self.repo, "docs", files)
        ctx = dt.Context(self.repo, dt.tracked_files(self.repo), {"exclude": [], "ignore_paths": [], "allow": []})
        docs = [f for f in ctx.files if f.endswith(".md")]
        return ctx, docs


class ParityTest(CheckCase):
    def test_equal_heading_levels_pass_even_when_the_text_is_translated(self):
        ctx, docs = self.build({"README.md": "# Title\n## Install\n## License\n", "README.pt-BR.md": "# Titulo\n## Instalacao\n## Licenca\n"})
        self.assertEqual(dt.check_parity(ctx, docs), [])

    def test_different_levels_are_a_finding_that_names_the_first_difference(self):
        ctx, docs = self.build({"README.md": "# T\n## A\n### B\n", "README.pt-BR.md": "# T\n## A\n## B\n"})
        found = dt.check_parity(ctx, docs)
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0]["category"], found[0]["document"], found[0]["value"]), ("parity", "README.md", "1,2,3|1,2,2"))
        self.assertIn("o titulo 3 difere", found[0]["message"])

    def test_a_different_count_is_reported_as_such(self):
        ctx, docs = self.build({"README.md": "# T\n## A\n## B\n", "README.pt-BR.md": "# T\n## A\n"})
        self.assertIn("3 titulos contra 2", dt.check_parity(ctx, docs)[0]["message"])

    def test_link_sets_are_not_compared(self):
        ctx, docs = self.build({"README.md": "# T\n[x](a.md)\n", "README.pt-BR.md": "# T\n[x](b.md)\n", "a.md": "a\n", "b.md": "b\n"})
        self.assertEqual(dt.check_parity(ctx, docs), [])

    def test_fenced_hash_lines_are_not_headings(self):
        ctx, docs = self.build({"a.md": "# T\n```\n# not\n```\n", "a.pt-BR.md": "# T\n"})
        self.assertEqual(dt.check_parity(ctx, docs), [])

    def test_a_readme_without_a_portuguese_counterpart_is_a_finding(self):
        ctx, docs = self.build({"README.md": "# T\n", "docs/notes.md": "# N\n"})
        found = dt.check_parity(ctx, docs)
        self.assertEqual([(f["document"], f["value"]) for f in found], [("README.md", "falta README.pt-BR.md")])

    def test_any_other_unpaired_document_is_fine(self):
        ctx, docs = self.build({"docs/notes.md": "# N\n", "docs/pt-BR/guia.md": "# G\n"})
        self.assertEqual(dt.check_parity(ctx, docs), [])

    def test_a_pair_with_an_excluded_side_is_skipped(self):
        ctx, _ = self.build({"a.md": "# T\n## A\n", "a.pt-BR.md": "# T\n"})
        self.assertEqual(dt.check_parity(ctx, ["a.md"]), [])


class VersionTest(CheckCase):
    def files(self, readme):
        return {"plugins/x-tool/.claude-plugin/plugin.json": manifest("x-tool", "1.3.0"),
                "plugins/y-tool/.claude-plugin/plugin.json": manifest("y-tool", "0.2.0"),
                "README.md": readme}

    def test_plugin_versions_come_from_every_manifest(self):
        ctx, _ = self.build(self.files("# R\n"))
        self.assertEqual(dt.plugin_versions(ctx), {"x-tool": "1.3.0", "y-tool": "0.2.0"})

    def test_a_matching_version_passes(self):
        ctx, docs = self.build(self.files("x-tool 1.3.0 and v0.2.0 of y-tool\n"))
        self.assertEqual(dt.check_versions(ctx, docs), [])

    def test_a_stale_version_next_to_a_plugin_name_is_a_finding(self):
        ctx, docs = self.build(self.files("Built with x-tool 1.2.0 last week.\n"))
        found = dt.check_versions(ctx, docs)
        self.assertEqual([(f["category"], f["line"], f["value"]) for f in found], [("version", 1, "x-tool 1.2.0")])
        self.assertIn("x-tool 1.3.0", found[0]["message"])

    def test_a_version_on_a_line_without_a_plugin_name_is_ignored(self):
        ctx, docs = self.build(self.files("Python 3.10.2 and 9.9.9 appear here.\n"))
        self.assertEqual(dt.check_versions(ctx, docs), [])

    def test_a_plugin_name_inside_a_longer_name_does_not_count(self):
        ctx, docs = self.build(self.files("the x-tool-extra 7.7.7 and my-x-tool 6.6.6\n"))
        self.assertEqual(dt.check_versions(ctx, docs), [])

    def test_with_two_plugins_on_a_line_either_version_is_accepted(self):
        ctx, docs = self.build(self.files("x-tool 1.3.0 needs y-tool 0.2.0\n"))
        self.assertEqual(dt.check_versions(ctx, docs), [])

    def test_fenced_lines_and_other_documents_are_not_checked(self):
        files = self.files("```\nx-tool 0.0.1\n```\n")
        files["CHANGELOG.md"] = "x-tool 0.0.1\n"
        files["docs/old.md"] = "x-tool 0.0.1\n"
        ctx, docs = self.build(files)
        self.assertEqual(dt.check_versions(ctx, docs), [])

    def test_skill_files_and_plugin_readmes_are_checked(self):
        files = self.files("ok\n")
        files["plugins/x-tool/skills/x-tool/SKILL.md"] = "needs x-tool 0.1.0\n"
        files["plugins/x-tool/README.pt-BR.md"] = "x-tool 0.1.0\n"
        ctx, docs = self.build(files)
        self.assertEqual(sorted(f["document"] for f in dt.check_versions(ctx, docs)),
                         ["plugins/x-tool/README.pt-BR.md", "plugins/x-tool/skills/x-tool/SKILL.md"])

    def test_without_manifests_there_is_nothing_to_check(self):
        ctx, docs = self.build({"README.md": "x-tool 9.9.9\n"})
        self.assertEqual(dt.check_versions(ctx, docs), [])


class PluginListTest(CheckCase):
    CATALOG = json.dumps({"plugins": [{"name": "x-tool"}, {"name": "y-tool"}]})

    def test_every_catalog_plugin_must_be_linked_from_the_root_readmes(self):
        ctx, docs = self.build({".claude-plugin/marketplace.json": self.CATALOG,
                                "README.md": "[x](plugins/x-tool) [y](./plugins/y-tool/README.md#top)\n",
                                "README.pt-BR.md": "[x](plugins/x-tool/README.pt-BR.md)\n"})
        found = dt.check_plugin_lists(ctx, docs)
        self.assertEqual([(f["document"], f["value"]) for f in found], [("README.pt-BR.md", "y-tool")])

    def test_no_catalog_means_nothing_to_check(self):
        ctx, docs = self.build({"README.md": "# R\n"})
        self.assertEqual(dt.check_plugin_lists(ctx, docs), [])

    def test_a_name_in_prose_is_not_a_link(self):
        ctx, docs = self.build({".claude-plugin/marketplace.json": self.CATALOG, "README.md": "x-tool and y-tool\n"})
        self.assertEqual(sorted(f["value"] for f in dt.check_plugin_lists(ctx, docs)), ["x-tool", "y-tool"])


if __name__ == "__main__":
    unittest.main()
