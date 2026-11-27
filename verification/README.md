# Manual clean Mac update acceptance

This optional workflow tests previously public Prism packages on a fresh standard GitHub-hosted macOS 15 ARM virtual machine. It does not build or disclose private application source. It has read-only repository permission, no secrets, no publishing step, no schedule and no pull request trigger. An owner must explicitly dispatch it after reviewing the pinned versions and hashes.

The verifier refuses personal, self-hosted or non-ARM execution. It first checks the console WindowServer and trusted Accessibility without requesting permissions or changing security settings. Missing UI capability still permits clean package, signature, feed and ordinary launch checks, then records a specific UI gap without claiming update acceptance. It never modifies TCC databases, disables Gatekeeper, clears quarantine, changes signing identities or grants itself privileges. Hosted runner availability and its preauthorized GUI capabilities are distinct from product acceptance.

If capabilities pass, the job downloads immutable public build 27 and build 28 packages plus the exact reviewed signed production feed. It preserves the real original bundle, executable and application identity, installing build 27 at a fresh runner-owned `~/Applications/Prism Explorer.app`. It seeds only synthetic normal persisted preferences in the fresh runner account, including completed onboarding, and launches the normal app with a synthetic folder and the real default session path at ~/Library/Application Support/Prism Explorer/Workspace/session-v1.json. The restarted app therefore reads its normal persisted configuration and session without inheriting custom configuration arguments. There are no developer review flags, custom updater drivers or alternate feeds.

The OS Accessibility adapter invokes the real Check for Updates menu by PID, verifies the offered public 0.9.13, then presses only its stock Install Update and, if offered, Install and Relaunch buttons. Unknown prompts cause timeout, never an automatic bypass. It waits for a new process at the exact same installed path, build 28 metadata and an executable digest matching the pinned public archive. It checks signature integrity, the unchanged synthetic file and visible fixture restoration. Receipts and WindowServer screenshots distinguish each phase. The original offer and final restored workspace captures are required; a transient ready/progress capture is recorded when available and never substitutes for final replacement and restoration checks. No success is claimed merely because an update was offered or a button was pressed.

No raw editor/file text or application log is uploaded. Accessibility evidence is limited to control labels, expected-offer detection and synthetic-fixture presence.

The runner is disposable. This job does not touch the owner's computer, live Prism sessions, private repositories or publisher credentials. Its artifacts contain only the synthetic fixture and public release evidence and expire after three days. Installing a publisher-signed preview on this controlled runner is not proof of Developer ID signing, notarization or first-launch acceptance on another Mac.

A capability failure is a runner limitation. An installation or restoration failure requires inspecting its phase and screenshots before attributing it to Prism. The workflow must be updated and reviewed when public versions or signed feed hashes change.

Official runner reference

https://docs.github.com/en/actions/reference/runners/github-hosted-runners

The current standard public ARM labels include macos-15, with a new hosted VM per job. Standard public runners are free. Labels ending in large or xlarge are not used. No paid, larger or self-hosted runner is permitted here.
