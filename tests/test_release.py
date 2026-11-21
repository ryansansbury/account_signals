"""The release tools, offline: the page's header rule goes last in the site's _headers and replaces an older one, the
cache rule is read the way the live check reads it, and a preview or a stand-in build never goes live. tools/ never
ships, so a clean clone of the public repo skips these."""
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def load(name, rel):
    path = HERE.joinpath(*rel.split("/"))
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gl = load("tools_go_live_test", "tools/go_live.py")


@unittest.skipIf(gl is None, "tools/ never ships")
class GoLive(unittest.TestCase):
    def test_the_rule_goes_last_and_replaces_an_older_one(self):
        site = "/*\n  Content-Security-Policy: default-src 'self'\n  Cache-Control: public, max-age=31536000, immutable\n"
        once = gl.with_rule(site)
        self.assertTrue(once.startswith(site.rstrip("\n")))
        self.assertTrue(once.endswith(gl.rule()))
        self.assertEqual(gl.with_rule(once), once)
        older = site + f"\n/{gl.FOLDER}/*\n  Content-Security-Policy: default-src 'none'\n"
        self.assertEqual(gl.with_rule(older).count(f"/{gl.FOLDER}/*"), 1)
        self.assertIn(gl.POLICY, gl.with_rule(older))

    def test_the_cache_rule_is_read_like_the_live_check(self):
        self.assertEqual(gl.cache_kept([gl.CACHE]), 0)
        self.assertIsNone(gl.cache_kept(["public, max-age=31536000, immutable"]))
        self.assertIsNone(gl.cache_kept([gl.CACHE, gl.CACHE]))

    def test_the_policy_allows_only_the_page_itself(self):
        for part in ("default-src 'none'", "script-src 'self'", "style-src 'self'", "font-src 'self'"):
            self.assertIn(part, gl.POLICY)
        self.assertNotIn("unsafe", gl.POLICY)
        self.assertEqual(gl.FOLDER, "account-signals")
        self.assertEqual(set(gl.SHIPS), {"index.html", "app.css", "app.js", "scoring.js", "route.js", "claims.js",
                                         "data.js", "code.js", "favicon.svg"})


if __name__ == "__main__":
    unittest.main()
