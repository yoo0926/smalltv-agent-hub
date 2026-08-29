import unittest
from pathlib import Path

from scripts.install_launch_agent import LABEL, build_plist


class LaunchAgentTests(unittest.TestCase):
    def test_plist_uses_absolute_project_paths(self):
        project = Path("/tmp/geekmagic")
        plist = build_plist(project, "127.0.0.1", 4747, "http://smalltv.local")
        self.assertEqual(plist["Label"], LABEL)
        self.assertEqual(plist["ProgramArguments"][0], "/tmp/geekmagic/bin/desk-hub")
        self.assertEqual(plist["ProgramArguments"][2], "127.0.0.1")
        self.assertIn("http://smalltv.local", plist["ProgramArguments"])
        self.assertTrue(plist["RunAtLoad"])
        self.assertTrue(plist["KeepAlive"])


if __name__ == "__main__":
    unittest.main()
