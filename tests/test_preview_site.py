"""The local preview serves the page under its live folder with the live site's headers, on a free port, and refuses a
build that never goes live."""
import importlib.util
import shutil
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, HERE.joinpath(*rel.split("/")))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ps = load("owner_preview_site", "owner/preview_site.py")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Preview(unittest.TestCase):
    def setUp(self):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        self.site = Path(tempfile.mkdtemp(dir=scratch))
        self.site.joinpath("index.html").write_text("<!doctype html><title>x</title>", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.site)

    def test_paths_outside_the_folder_find_nothing(self):
        h = object.__new__(ps.Handler)
        h.directory = str(self.site)
        self.assertEqual(Path(h.translate_path(f"/{ps.FOLDER}/index.html?x=1#map")), self.site.joinpath("index.html"))
        self.assertFalse(Path(h.translate_path("/index.html")).exists())
        self.assertFalse(Path(h.translate_path(f"/{ps.FOLDER}/../../secrets")).exists())

    def test_the_page_is_served_under_its_folder_with_the_live_headers(self):
        try:
            httpd = ps.serve(self.site)
        except PermissionError:
            self.skipTest("this machine doesn't allow a local server here")
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        try:
            with urllib.request.urlopen(f"{base}/{ps.FOLDER}/index.html", timeout=10) as r:
                self.assertEqual(r.status, 200)
                self.assertEqual(r.headers["Content-Security-Policy"], ps.POLICY)
                self.assertEqual(r.headers["Cache-Control"], ps.CACHE)
            opener = urllib.request.build_opener(NoRedirect)
            with self.assertRaises(urllib.error.HTTPError) as e:
                opener.open(f"{base}/", timeout=10)
            self.assertEqual((e.exception.code, e.exception.headers["Location"]), (301, f"/{ps.FOLDER}/"))
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(f"{base}/index.html", timeout=10)
            self.assertEqual(e.exception.code, 404)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_only_a_real_build_is_served(self):
        self.assertEqual(ps.built_kind(self.site), "missing")
        data = self.site.joinpath("data.js")
        data.write_text('/* {"preview":false,"stand_in":true} */\nwindow.AS = {};\n', encoding="utf-8")
        self.assertEqual(ps.built_kind(self.site), "stand-in")
        data.write_text('/* {"preview":false,"stand_in":false} */\nwindow.AS = {};\n', encoding="utf-8")
        self.assertEqual(ps.built_kind(self.site), "page")

    def test_the_policy_matches_the_one_go_live_stages(self):
        tool = HERE.joinpath("tools", "go_live.py")
        if not tool.exists():
            self.skipTest("tools/ never ships")
        gl = load("tools_go_live", "tools/go_live.py")
        self.assertEqual((gl.POLICY, gl.CACHE, gl.FOLDER), (ps.POLICY, ps.CACHE, ps.FOLDER))


if __name__ == "__main__":
    unittest.main()
