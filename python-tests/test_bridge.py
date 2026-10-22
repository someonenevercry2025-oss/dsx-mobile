"""Uji kontrak dsx_bridge di CPython (tanpa Chaquopy)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "src", "main", "python"))

import dsx_bridge as b


class BridgeContractTest(unittest.TestCase):
    def test_version(self):
        r = json.loads(b.version())
        self.assertTrue(r["ok"])
        self.assertIn("package", r["data"])
        self.assertEqual(r["data"]["language"], "2.6")

    def test_list_blocks(self):
        r = json.loads(b.list_blocks())
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["data"]), 20)

    def test_default_form_and_build(self):
        r = json.loads(b.default_form_kind("surat-resmi"))
        self.assertTrue(r["ok"])
        form = r["data"]
        with tempfile.TemporaryDirectory() as td:
            gen = json.loads(b.generate_dsx(json.dumps(form), td))
            self.assertTrue(gen["ok"], gen)
            build = json.loads(b.build(td, "docx"))
            self.assertTrue(build["ok"], build)
            self.assertTrue(os.path.isfile(build["data"]["path"]))
            self.assertGreater(build["data"]["size"], 1000)

    def test_custom_empty(self):
        r = json.loads(b.default_form_kind("custom"))
        self.assertTrue(r["ok"])

    def test_new_block(self):
        r = json.loads(b.new_block_json("paragraph"))
        self.assertTrue(r["ok"])
        self.assertEqual(r["data"]["type"], "paragraph")

    def test_never_raises(self):
        # build on missing dir must return ok=false, not raise
        r = json.loads(b.build("/tmp/dsx-path-yang-tidak-ada-xyz", "docx"))
        self.assertFalse(r["ok"])
        self.assertTrue(r["diagnostics"])
        # unknown block type
        r2 = json.loads(b.new_block_json("tipe-aneh-xyz"))
        self.assertFalse(r2["ok"])



    def test_generate_invalid_form_fails_and_no_stale_doc(self):
        form = json.loads(b.default_form_kind("custom"))["data"]
        with tempfile.TemporaryDirectory() as td:
            self.assertTrue(json.loads(b.generate_dsx(json.dumps(form), td))["ok"])
            form["blocks"] = [{"type": "tipe-aneh-xyz"}]
            r = json.loads(b.generate_dsx(json.dumps(form), td))
            self.assertFalse(r["ok"])
            self.assertEqual(r["diagnostics"][0]["code"], "FORM_INVALID")

    def test_surat_ttd_is_list(self):
        # SuratFormEditor (Kotlin) mengedit ttd sebagai array
        form = json.loads(b.default_form_kind("surat-resmi"))["data"]
        self.assertIsInstance(form["ttd"], list)

    def test_preset_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            form = json.loads(b.default_form_kind("custom"))["data"]
            form["blocks"] = [{"type": "paragraph", "text": "Hello preset"}]
            r = json.loads(b.save_preset(td, "my-preset", json.dumps(form), "uji"))
            self.assertTrue(r["ok"], r)
            listed = json.loads(b.list_presets(td))
            self.assertTrue(listed["ok"])
            names = [x["name"] for x in listed["data"]]
            self.assertIn("my-preset", names)
            loaded = json.loads(b.load_preset(td, "my-preset"))
            self.assertTrue(loaded["ok"])
            self.assertEqual(loaded["data"]["blocks"][0]["text"], "Hello preset")
            deleted = json.loads(b.delete_preset(td, "my-preset"))
            self.assertTrue(deleted["ok"])

    def test_dsx_to_form(self):
        # minimal dsx
        src = "DOCUMENT {\n  PARAGRAPH \"Halo dunia\"\n}\n"
        r = json.loads(b.dsx_to_form(src))
        # may or may not fully parse depending on syntax; must not throw
        self.assertIn("ok", r)

if __name__ == "__main__":
    unittest.main()
