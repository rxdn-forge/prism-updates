#!/usr/bin/env python3
"""Manually verify public Prism updates on a disposable standard hosted Mac."""
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import signal
import subprocess
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
FEED = "https://prism.rxdn.dev/updates/appcast.xml"
FEED_SHA = "c9e12a2c7f92405888a5c0496fc88948b0700a962c2c74839dabfc5a3210cee1"
OLD_URL = "https://prism.rxdn.dev/updates/Prism-Explorer-0.9.12-27.zip"
OLD_SHA = "44b1af31731582134d2c57790b59d656f2d65fcabff9da5c5afb8a0ef8c3d7d9"
TARGET_URL = "https://prism.rxdn.dev/updates/Prism-Explorer-0.9.13-28.zip"
TARGET_SHA = "0a6f74bf6f1e14a65e2e4628d6d40323dd8248bdf2c6e7779c4f2702469c8c53"


def permitted_host():
    return (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
        and os.environ.get("GITHUB_REPOSITORY") == "rxdn-forge/prism-updates"
        and platform.machine() == "arm64"
        and bool(os.environ.get("RUNNER_TEMP"))
    )


def checked(arguments):
    result = subprocess.run(
        [str(value) for value in arguments], capture_output=True, timeout=90
    )
    if result.returncode:
        raise RuntimeError(f"{Path(arguments[0]).name} failed with exit {result.returncode}")
    return result.stdout


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metadata(bundle):
    return plistlib.loads((bundle / "Contents/Info.plist").read_bytes())


def executable_hash(bundle):
    executable = metadata(bundle)["CFBundleExecutable"]
    return digest(bundle / "Contents/MacOS" / executable)


def wait_for(call, predicate, seconds=45):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = call()
        if predicate(value):
            return value
        time.sleep(0.5)
    raise RuntimeError("Current phase timed out; inspect its structured receipt")


class Verification:
    def __init__(self):
        self.output = Path(os.environ["RUNNER_TEMP"]) / "prism-clean-mac-proof"
        self.app = Path.home() / "Applications/Prism Explorer.app"
        self.state = {
            "accepted": False,
            "phase": "capabilities",
            "scope": "Original public app and identity, normal menu, real signed download and same-path replacement on fresh standard hosted ARM Mac",
        }
        self.output.mkdir(parents=True, exist_ok=True)

    def save(self):
        destination = self.output / "receipt.json"
        destination.write_text(json.dumps(self.state, indent=2))

    def adapter(self, *arguments):
        result = subprocess.run(
            [str(self.output / "PrismAX"), *map(str, arguments)],
            capture_output=True, timeout=30,
        )
        if result.returncode not in (0, 3):
            raise RuntimeError("OS verification adapter failed")
        return json.loads(result.stdout)

    def download(self, url, destination, expected):
        data = urllib.request.urlopen(url, timeout=40).read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError("Public bytes differ from reviewed immutable digest")
        destination.write_bytes(data)

    def capture(self, pid, name, window_title=None, required=True):
        if window_title is None:
            window_title = "Software Update" if name == "offer" else "Clean Mac Upgrade Fixture"
        deadline = time.monotonic() + (8 if required else 2)
        result = {"success": False, "windowTitle": window_title}
        while time.monotonic() < deadline:
            result = self.adapter("capture", pid, self.output / name, window_title)
            if result.get("success"):
                break
            time.sleep(0.3)
        self.state.setdefault("captures", {})[name] = result
        if required and not result.get("success"):
            raise RuntimeError("Required stable WindowServer screenshot was unavailable")
        return result

    def verify_public_signatures(self, public_key):
        feed = (self.output / "appcast.xml").read_bytes()
        trailer = re.search(
            rb"<!-- sparkle-signatures:\s*edSignature:\s*(\S+)\s*length:\s*(\d+)", feed
        )
        if not trailer:
            raise RuntimeError("Signed feed trailer is missing")
        signed_length = int(trailer.group(2))
        signed_feed = self.output / "signed-feed-bytes.xml"
        signed_feed.write_bytes(feed[:signed_length])
        valid_feed = self.adapter(
            "verify-signature", signed_feed, public_key, trailer.group(1).decode()
        )["valid"]
        item = ET.fromstring(feed).find("channel/item")
        enclosure = item.find("enclosure")
        archive_signature = enclosure.attrib[
            "{http://www.andymatuschak.org/xml-namespaces/sparkle}edSignature"
        ]
        valid_archive = self.adapter(
            "verify-signature", self.output / "target.zip", public_key, archive_signature
        )["valid"]
        self.state["feedSignatureValid"] = valid_feed
        self.state["archiveSignatureValid"] = valid_archive
        if not valid_feed or not valid_archive:
            raise RuntimeError("Public Ed25519 signature validation failed")

    def prepare(self):
        checked(["swiftc", ROOT / "PrismAX.swift", "-o", self.output / "PrismAX"])
        capabilities = self.adapter("capabilities")
        self.state["capabilities"] = capabilities
        self.save()
        preferences = Path.home() / "Library/Preferences/dev.prism.explorer.plist"
        if self.app.exists() or preferences.exists() or capabilities["existingPrismPIDs"]:
            raise RuntimeError("Runner is not clean for the real Prism identity")
        self.state["phase"] = "public-package-and-feed"
        self.save()
        self.download(FEED, self.output / "appcast.xml", FEED_SHA)
        self.download(OLD_URL, self.output / "old.zip", OLD_SHA)
        self.download(TARGET_URL, self.output / "target.zip", TARGET_SHA)
        expected = self.output / "expected"
        expected.mkdir()
        checked(["/usr/bin/ditto", "-x", "-k", self.output / "target.zip", expected])
        target = expected / "Prism Explorer.app"
        self.state["expectedExecutableSHA256"] = executable_hash(target)
        self.app.parent.mkdir(exist_ok=True)
        checked(["/usr/bin/ditto", "-x", "-k", self.output / "old.zip", self.app.parent])
        before = metadata(self.app)
        if (before["CFBundleIdentifier"], before["CFBundleVersion"]) != ("dev.prism.explorer", "27"):
            raise RuntimeError("Wrong original public package")
        checked(["/usr/bin/codesign", "--verify", "--deep", "--strict", self.app])
        self.verify_public_signatures(before["SUPublicEDKey"])
        self.state["packageIntegrityValid"] = True
        self.state["beforeBuild"] = before["CFBundleVersion"]
        self.state["beforeExecutableSHA256"] = executable_hash(self.app)
        self.state["installedPath"] = str(self.app)
        return before

    def launch(self, before):
        fixture = self.output / "Clean Mac Upgrade Fixture"
        fixture.mkdir()
        proof = fixture / "Upgrade-proof.txt"
        proof.write_text("Synthetic file retained across the public update.\n")
        self.proof = proof
        self.proof_hash = digest(proof)
        settings = self.output / "synthetic-settings.json"
        settings.write_text(json.dumps({
            "onboardingCompleted": True,
            "terminalHistoryEnabled": False,
            "terminalLoadShellConfig": False,
            "terminalNotifyLongCommands": False,
            "updates": {
                "channel": "preview", "automaticallyChecks": False,
                "automaticallyDownloads": False, "checkIntervalHours": 24,
            },
        }))
        if not self.adapter("seed-preferences", settings)["readbackMatches"]:
            raise RuntimeError("Synthetic normal preferences were not persisted")
        session = Path.home() / "Library/Application Support/Prism Explorer/Workspace/session-v1.json"
        self.state["sessionPath"] = str(session)
        self.state["normalPersistedPreferences"] = True
        self.state["phase"] = "normal-launch"
        self.save()
        executable = self.app / "Contents/MacOS" / before["CFBundleExecutable"]
        process = subprocess.Popen(
            [str(executable), "--folder", str(fixture), "--workspace-session-file", str(session)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.state["beforePID"] = process.pid
        time.sleep(3)
        self.state["cleanLaunchProcessRunning"] = process.poll() is None
        self.save()
        return process

    def ui_acceptance(self, process):
        capabilities = self.state["capabilities"]
        required = ("axTrusted", "windowServerAvailable", "screenCapturePermitted")
        if not all(capabilities[key] for key in required):
            self.state["phase"] = "blocked-ui-capability"
            self.state["uiGap"] = "Hosted runner lacks a required preauthorized UI capability. Package, public signatures and normal launch were still checked. No security permissions were changed."
            self.save()
            return False
        pid = process.pid
        before_windows = wait_for(
            lambda: self.adapter("inspect", pid),
            lambda windows: any(window["fixtureVisible"] for window in windows),
        )
        self.state["beforeWindows"] = before_windows
        self.capture(pid, "before")
        self.state["phase"] = "normal-menu"
        self.save()
        wait_for(
            lambda: self.adapter("menu", pid, "Check for Updates…"),
            lambda result: result.get("success"),
        )
        offered = wait_for(
            lambda: self.adapter("inspect", pid),
            lambda windows: any(
                window["expectedOfferVisible"]
                and any(button["title"] == "Install Update" for button in window["buttons"])
                for window in windows
            ),
        )
        self.state["offeredWindows"] = offered
        time.sleep(2)
        self.capture(pid, "offer")
        self.state["phase"] = "sparkle-download-install"
        self.save()
        if not self.adapter("button", pid, "Install Update").get("success"):
            raise RuntimeError("Install Update action failed")
        deadline = time.monotonic() + 180
        relaunch_pressed = False
        while time.monotonic() < deadline:
            applications = self.adapter("apps")
            changed = [app for app in applications if app["path"] == str(self.app) and app["pid"] != pid]
            try:
                installed_build = metadata(self.app)["CFBundleVersion"]
            except (OSError, ValueError, KeyError):
                # Atomic replacement may briefly hide old/new metadata.
                installed_build = None
            if changed and installed_build == "28":
                new_pid = changed[0]["pid"]
                break
            windows = self.adapter("inspect", pid)
            self.state["lastWindows"] = windows
            ready_window = next((
                window for window in windows
                if any(
                    button["title"] == "Install and Relaunch" and button["enabled"]
                    for button in window["buttons"]
                )
            ), None)
            if not relaunch_pressed and ready_window:
                self.save()
                self.capture(pid, "ready", ready_window["title"], required=False)
                relaunch_pressed = self.adapter("button", pid, "Install and Relaunch").get("success", False)
                self.state["relaunchApprovalPressed"] = relaunch_pressed
                self.save()
            time.sleep(0.75)
        else:
            raise RuntimeError("No same-path build28 relaunch in180seconds; no unknown prompt was accepted")
        self.state["afterPID"] = new_pid
        self.state["afterBuild"] = metadata(self.app)["CFBundleVersion"]
        self.state["afterExecutableSHA256"] = executable_hash(self.app)
        if self.state["afterExecutableSHA256"] != self.state["expectedExecutableSHA256"]:
            raise RuntimeError("Installed executable differs from pinned public28 archive")
        checked(["/usr/bin/codesign", "--verify", "--deep", "--strict", self.app])
        after_windows = wait_for(
            lambda: self.adapter("inspect", new_pid),
            lambda windows: any(window["fixtureVisible"] for window in windows),
        )
        self.state["afterWindows"] = after_windows
        self.capture(new_pid, "after")
        self.state["fixtureFileUnchanged"] = digest(self.proof) == self.proof_hash
        self.state["fixtureVisibleAfter"] = True
        if not self.state["fixtureFileUnchanged"]:
            raise RuntimeError("Synthetic fixture content changed")
        self.state["phase"] = "complete"
        self.state["accepted"] = True
        self.save()
        return True

    def close_owned_processes(self):
        try:
            applications = self.adapter("apps")
            for app in applications:
                if app["path"] == str(self.app):
                    os.kill(app["pid"], signal.SIGTERM)
        except (OSError, RuntimeError):
            pass


def main():
    if not permitted_host():
        # This guard intentionally has no filesystem side effects anywhere.
        print(json.dumps({"accepted": False, "phase": "guard", "error": "Refusing non-hosted/non-public/non-ARM execution"}))
        return 1
    verification = Verification()
    try:
        before = verification.prepare()
        process = verification.launch(before)
        return 0 if verification.ui_acceptance(process) else 1
    except Exception as error:
        verification.state["error"] = str(error)
        verification.save()
        return 1
    finally:
        verification.close_owned_processes()


if __name__ == "__main__":
    sys.exit(main())
