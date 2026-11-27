// Public black-box macOS adapter. It does not import or call Prism internals.
import AppKit
import ApplicationServices
import CryptoKit
import Foundation

func attribute(_ element: AXUIElement, _ key: String) -> CFTypeRef? {
    var value: CFTypeRef?
    let result = AXUIElementCopyAttributeValue(element, key as CFString, &value)
    return result == .success ? value : nil
}

func children(_ element: AXUIElement) -> [AXUIElement] {
    attribute(element, kAXChildrenAttribute) as? [AXUIElement] ?? []
}

func label(_ element: AXUIElement) -> String {
    (attribute(element, kAXTitleAttribute) as? String)
        ?? (attribute(element, kAXDescriptionAttribute) as? String)
        ?? (attribute(element, kAXValueAttribute) as? String)
        ?? ""
}

func walk(_ element: AXUIElement, depth: Int = 0) -> [AXUIElement] {
    guard depth < 28 else { return [] }
    return [element] + children(element).flatMap { walk($0, depth: depth + 1) }
}

func emit(_ value: Any) {
    let data = try! JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
    print(String(data: data, encoding: .utf8)!)
}

let arguments = CommandLine.arguments
let mode = arguments[1]

if mode == "capabilities" {
    let session = CGSessionCopyCurrentDictionary() as? [String: Any] ?? [:]
    emit([
        "axTrusted": AXIsProcessTrusted(),
        "windowServerAvailable": CGWindowListCopyWindowInfo(.optionAll, kCGNullWindowID) != nil,
        "screenCapturePermitted": CGPreflightScreenCaptureAccess(),
        "consoleSession": session["kCGSessionOnConsoleKey"] as? Bool ?? false,
        "existingPrismPIDs": NSRunningApplication.runningApplications(withBundleIdentifier: "dev.prism.explorer").map(\.processIdentifier)
    ])
} else if mode == "apps" {
    emit(NSRunningApplication.runningApplications(withBundleIdentifier: "dev.prism.explorer").map {
        ["pid": $0.processIdentifier, "path": $0.bundleURL?.path ?? ""]
    })
} else if mode == "seed-preferences" {
    let data = try Data(contentsOf: URL(fileURLWithPath: arguments[2]))
    let defaults = UserDefaults(suiteName: "dev.prism.explorer")!
    defaults.set(data, forKey: "prism.featureConfiguration.v2")
    defaults.synchronize()
    emit(["readbackMatches": defaults.data(forKey: "prism.featureConfiguration.v2") == data])
} else if mode == "verify-signature" {
    let data = try Data(contentsOf: URL(fileURLWithPath: arguments[2]))
    let publicKey = try Curve25519.Signing.PublicKey(rawRepresentation: Data(base64Encoded: arguments[3])!)
    let signature = Data(base64Encoded: arguments[4])!
    emit(["valid": publicKey.isValidSignature(signature, for: data)])
} else {
    let pid = pid_t(arguments[2])!
    let app = AXUIElementCreateApplication(pid)
    let windows = attribute(app, kAXWindowsAttribute) as? [AXUIElement] ?? []

    if mode == "inspect" {
        // Only control labels are returned. File/editor text values are not exported.
        emit(windows.map { window in
            let buttons = walk(window).filter {
                (attribute($0, kAXRoleAttribute) as? String) == kAXButtonRole
            }.map {
                ["title": label($0), "enabled": attribute($0, kAXEnabledAttribute) as? Bool ?? false]
            }
            let fixtureVisible = walk(window).contains {
                label($0).contains("Upgrade-proof.txt") || label($0).contains("Clean Mac Upgrade Fixture")
            }
            let offerVisible = walk(window).contains { label($0).contains("0.9.13") }
            return [
                "title": label(window), "buttons": buttons,
                "fixtureVisible": fixtureVisible, "expectedOfferVisible": offerVisible
            ] as [String: Any]
        })
    } else if mode == "capture" {
        let entries = CGWindowListCopyWindowInfo([.optionAll, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
        var ids: [Int] = []
        var exits: [Int32] = []
        for entry in entries {
            guard (entry[kCGWindowOwnerPID as String] as? Int) == Int(pid),
                  (entry[kCGWindowLayer as String] as? Int) == 0,
                  let id = entry[kCGWindowNumber as String] as? Int else { continue }
            ids.append(id)
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
            process.arguments = ["-x", "-l", String(id), arguments[3] + "-\(id).png"]
            try process.run()
            process.waitUntilExit()
            exits.append(process.terminationStatus)
        }
        emit(["windowIDs": ids, "captureExits": exits, "success": !ids.isEmpty && exits.allSatisfy { $0 == 0 }])
    } else {
        let desired = arguments[3]
        let roots: [AXUIElement]
        if mode == "menu", let menu = attribute(app, kAXMenuBarAttribute) {
            roots = [unsafeBitCast(menu, to: AXUIElement.self)]
        } else {
            roots = windows
        }
        let matches = roots.flatMap { walk($0) }.filter {
            label($0) == desired && (attribute($0, kAXEnabledAttribute) as? Bool) == true
        }
        guard matches.count == 1 else {
            emit(["success": false, "matches": matches.count, "label": desired])
            exit(3)
        }
        NSRunningApplication(processIdentifier: pid)?.activate(options: [])
        let result = AXUIElementPerformAction(matches[0], kAXPressAction as CFString)
        emit(["success": result == .success, "result": result.rawValue, "label": desired])
    }
}
