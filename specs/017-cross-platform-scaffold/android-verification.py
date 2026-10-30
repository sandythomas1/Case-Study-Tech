"""Check the running preview in the isolated cst17_verification Android AVD.

Set ANDROID_HOME and start npm run android -- --localhost --port 8087 first.
This deliberately refuses other AVDs and never wipes or uninstalls applications.
"""

import os
import re
import subprocess
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


HERE = Path(__file__).resolve().parent
ADB = Path(os.environ["ANDROID_HOME"]) / "platform-tools/adb.exe"


def adb(*args, binary=False):
    result = subprocess.run([str(ADB), "-s", "emulator-5556", *args],
                            capture_output=True, text=not binary, check=True, timeout=25)
    return result.stdout


def hierarchy():
    adb("shell", "uiautomator", "dump", "/sdcard/cst17-verification.xml")
    return ET.fromstring(adb("shell", "cat", "/sdcard/cst17-verification.xml"))


class AndroidVerification(unittest.TestCase):
    def test_preview_flow_tabs_and_hardware_back(self):
        self.assertIn("cst17_verification", adb("emu", "avd", "name"))
        adb("reverse", "tcp:8087", "tcp:8087")
        adb("shell", "am", "force-stop", "host.exp.exponent")
        adb("shell", "am start -W -a android.intent.action.VIEW "
            "-d 'exp://127.0.0.1:8087?__expo_disable_fab=1&__expo_disable_auto_launch=1&__expo_disable_onboarding=1' "
            "host.exp.exponent")
        self.assert_screen("Welcome")
        for action, title in (("Explore the preview", "Library"),
                              ("Preview Preparation", "Preparation"),
                              ("Preview Session", "Session"),
                              ("Preview Report", "Report")):
            self.tap(action)
            self.assert_screen(title)
        for title in ("Session", "Preparation", "Library"):
            adb("shell", "input", "keyevent", "4")
            self.assert_screen(title)
        for title in ("Score history", "Account", "Library"):
            self.tap(title)
            self.assert_screen(title)

    def assert_screen(self, title):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            root = hierarchy()
            texts = {node.get("text") for node in root.iter("node")}
            if {"Reload", "Go home", "Open DevTools"}.issubset(texts):
                # Expo Go can restore its own developer menu on launch.
                adb("shell", "input", "keyevent", "4")
                continue
            if title in texts and "Navigation preview" in texts:
                self.assertFalse(any("Error" == text for text in texts))
                name = title.lower().replace(" ", "-")
                (HERE / "screenshots" / f"android-{name}.png").write_bytes(
                    adb("exec-out", "screencap", "-p", binary=True))
                print(f"Android screen verified: {title}", flush=True)
                return
        self.fail(f"Expected {title}; observed text: {sorted(filter(None, texts))}")

    def tap(self, label):
        root = hierarchy()
        parents = {child: parent for parent in root.iter() for child in parent}
        for node in root.iter("node"):
            if label not in (node.get("text"), node.get("content-desc")):
                continue
            while node.get("clickable") != "true" and node in parents:
                node = parents[node]
            if node.get("clickable") == "true":
                x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.get("bounds", "")))
                adb("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))
                return
        self.fail(f"No clickable control named {label}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
