#!/usr/bin/env swift

import ApplicationServices
import AppKit
import Foundation

struct Node {
    let element: AXUIElement
    let depth: Int
    let role: String
    let title: String
    let description: String
    let value: String
    let identifier: String
    let actions: [String]

    var searchableText: String {
        [role, title, description, value, identifier].joined(separator: " ")
    }
}

enum AXProbeError: Error, CustomStringConvertible {
    case usage(String)
    case ax(String)
    case notFound(String)

    var description: String {
        switch self {
        case .usage(let message), .ax(let message), .notFound(let message):
            return message
        }
    }
}

func usage() -> Never {
    fputs("""
    Usage:
      scripts/axprobe.swift list --pid PID [--max-depth N]
      scripts/axprobe.swift activate --pid PID
      scripts/axprobe.swift actions --pid PID [--contains TEXT] [--role AXRole]
      scripts/axprobe.swift attributes --pid PID [--contains TEXT] [--role AXRole]
      scripts/axprobe.swift focus --pid PID [--contains TEXT] [--role AXRole]
      scripts/axprobe.swift key --key down|up|left|right|enter|space|tab [--repeat N]
      scripts/axprobe.swift perform --pid PID [--contains TEXT] [--role AXRole] --action AXPress
      scripts/axprobe.swift set-bool --pid PID [--contains TEXT] [--role AXRole] --attribute AXSelected --value true|false
      scripts/axprobe.swift set-value --pid PID [--contains TEXT] [--role AXRole] --value VALUE

    Examples:
      scripts/axprobe.swift list --pid 12345 --max-depth 8
      scripts/axprobe.swift perform --pid 12345 --contains "Run primary action" --action AXPress
      scripts/axprobe.swift perform --pid 12345 --contains "Quantity slider" --action AXIncrement
      scripts/axprobe.swift perform --pid 12345 --role AXIncrementor --action AXIncrement
      scripts/axprobe.swift attributes --pid 12345 --contains "editable initial value" --role AXTextField

    Requires macOS Accessibility permission for the terminal process running this script.
    \n
    """, stderr)
    exit(2)
}

func option(_ name: String, in args: [String]) -> String? {
    guard let index = args.firstIndex(of: name), index + 1 < args.count else {
        return nil
    }
    return args[index + 1]
}

func keyCode(named name: String) throws -> CGKeyCode {
    switch name.lowercased() {
    case "left": return 123
    case "right": return 124
    case "down": return 125
    case "up": return 126
    case "enter", "return": return 36
    case "tab": return 48
    case "space": return 49
    default:
        throw AXProbeError.usage("unknown --key \(name)")
    }
}

func sendKey(_ code: CGKeyCode) {
    let source = CGEventSource(stateID: .hidSystemState)
    let down = CGEvent(keyboardEventSource: source, virtualKey: code, keyDown: true)
    let up = CGEvent(keyboardEventSource: source, virtualKey: code, keyDown: false)
    down?.post(tap: .cghidEventTap)
    up?.post(tap: .cghidEventTap)
}

func stringAttribute(_ element: AXUIElement, _ name: String) -> String {
    var value: CFTypeRef?
    let error = AXUIElementCopyAttributeValue(element, name as CFString, &value)
    guard error == .success, let value else {
        return ""
    }
    if CFGetTypeID(value) == CFStringGetTypeID() {
        return value as! String
    }
    if CFGetTypeID(value) == AXValueGetTypeID() {
        return String(describing: value)
    }
    return String(describing: value)
}

func childElements(_ element: AXUIElement) -> [AXUIElement] {
    var value: CFTypeRef?
    let error = AXUIElementCopyAttributeValue(element, kAXChildrenAttribute as CFString, &value)
    guard error == .success, let children = value as? [AXUIElement] else {
        return []
    }
    return children
}

func actionNames(_ element: AXUIElement) -> [String] {
    var names: CFArray?
    let error = AXUIElementCopyActionNames(element, &names)
    guard error == .success, let names else {
        return []
    }
    return (names as NSArray).compactMap { $0 as? String }
}

func snapshot(_ element: AXUIElement, depth: Int) -> Node {
    Node(
        element: element,
        depth: depth,
        role: stringAttribute(element, kAXRoleAttribute),
        title: stringAttribute(element, kAXTitleAttribute),
        description: stringAttribute(element, kAXDescriptionAttribute),
        value: stringAttribute(element, kAXValueAttribute),
        identifier: stringAttribute(element, kAXIdentifierAttribute),
        actions: actionNames(element)
    )
}

func traverse(_ root: AXUIElement, maxDepth: Int, visit: (Node) -> Bool) -> Bool {
    var stack: [(AXUIElement, Int)] = [(root, 0)]
    while let (element, depth) = stack.popLast() {
        let node = snapshot(element, depth: depth)
        if visit(node) {
            return true
        }
        if depth < maxDepth {
            for child in childElements(element).reversed() {
                stack.append((child, depth + 1))
            }
        }
    }
    return false
}

func appElement(from args: [String]) throws -> AXUIElement {
    guard let pidText = option("--pid", in: args), let pid = pid_t(pidText) else {
        throw AXProbeError.usage("missing or invalid --pid")
    }
    return AXUIElementCreateApplication(pid)
}

func printNode(_ node: Node) {
    let indent = String(repeating: "  ", count: node.depth)
    let actionText = node.actions.isEmpty ? "-" : node.actions.joined(separator: ",")
    print("\(indent)\(node.role) title=\(debugField(node.title)) desc=\(debugField(node.description)) value=\(debugField(node.value)) id=\(debugField(node.identifier)) actions=\(actionText)")
}

func attributeValue(_ element: AXUIElement, _ name: String) -> String {
    var value: CFTypeRef?
    let error = AXUIElementCopyAttributeValue(element, name as CFString, &value)
    guard error == .success, let value else {
        return "<\(error.rawValue)>"
    }
    if let array = value as? [Any] {
        return "[" + array.map { String(describing: $0) }.joined(separator: ", ") + "]"
    }
    return String(describing: value).replacingOccurrences(of: "\n", with: "\\n")
}

func printAttributes(_ node: Node) {
    printNode(node)
    var names: CFArray?
    let error = AXUIElementCopyAttributeNames(node.element, &names)
    guard error == .success, let names else {
        print("  attributes unavailable: \(error.rawValue)")
        return
    }
    for case let name as String in names as NSArray {
        var settable = DarwinBoolean(false)
        let settableError = AXUIElementIsAttributeSettable(node.element, name as CFString, &settable)
        let settableText = settableError == .success ? String(settable.boolValue) : "?"
        print("  \(name) settable=\(settableText) value=\(attributeValue(node.element, name))")
    }
}

func debugField(_ value: String) -> String {
    value.isEmpty ? "-" : value.replacingOccurrences(of: "\n", with: "\\n")
}

func findNode(root: AXUIElement, contains needle: String?, role: String?, maxDepth: Int) -> Node? {
    let lowerNeedle = needle?.lowercased()
    var match: Node?
    _ = traverse(root, maxDepth: maxDepth) { node in
        let textMatches = lowerNeedle.map { node.searchableText.lowercased().contains($0) } ?? true
        let roleMatches = role.map { node.role == $0 } ?? true
        if textMatches && roleMatches {
            match = node
            return true
        }
        return false
    }
    return match
}

func main() throws {
    let args = Array(CommandLine.arguments.dropFirst())
    guard let command = args.first else {
        usage()
    }

    let maxDepth = Int(option("--max-depth", in: args) ?? "12") ?? 12

    if command == "key" {
        guard let key = option("--key", in: args) else {
            throw AXProbeError.usage("missing --key")
        }
        let repeatCount = Int(option("--repeat", in: args) ?? "1") ?? 1
        let code = try keyCode(named: key)
        for _ in 0..<repeatCount {
            sendKey(code)
            Thread.sleep(forTimeInterval: 0.05)
        }
        print("sent key \(key) repeat=\(repeatCount)")
        return
    }

    let root = try appElement(from: args)

    switch command {
    case "activate":
        guard let pidText = option("--pid", in: args), let pid = pid_t(pidText) else {
            throw AXProbeError.usage("missing or invalid --pid")
        }
        guard let app = NSRunningApplication(processIdentifier: pid) else {
            throw AXProbeError.notFound("no running application for pid \(pid)")
        }
        app.unhide()
        let activated = app.activate(options: [])
        guard activated else {
            throw AXProbeError.ax("NSRunningApplication.activate returned false")
        }
        print("activated pid \(pid)")
    case "list":
        _ = traverse(root, maxDepth: maxDepth) { node in
            printNode(node)
            return false
        }
    case "actions":
        let contains = option("--contains", in: args)
        let role = option("--role", in: args)
        guard contains != nil || role != nil else {
            throw AXProbeError.usage("missing --contains or --role")
        }
        guard let node = findNode(root: root, contains: contains, role: role, maxDepth: maxDepth) else {
            throw AXProbeError.notFound("no matching accessibility node")
        }
        printNode(node)
    case "attributes":
        let contains = option("--contains", in: args)
        let role = option("--role", in: args)
        guard contains != nil || role != nil else {
            throw AXProbeError.usage("missing --contains or --role")
        }
        guard let node = findNode(root: root, contains: contains, role: role, maxDepth: maxDepth) else {
            throw AXProbeError.notFound("no matching accessibility node")
        }
        printAttributes(node)
    case "perform":
        let contains = option("--contains", in: args)
        let role = option("--role", in: args)
        guard contains != nil || role != nil else {
            throw AXProbeError.usage("missing --contains or --role")
        }
        guard let action = option("--action", in: args) else {
            throw AXProbeError.usage("missing --action")
        }
        guard let node = findNode(root: root, contains: contains, role: role, maxDepth: maxDepth) else {
            throw AXProbeError.notFound("no matching accessibility node")
        }
        guard node.actions.contains(action) else {
            throw AXProbeError.ax("matched node does not expose \(action): \(node.actions)")
        }
        let error = AXUIElementPerformAction(node.element, action as CFString)
        guard error == .success else {
            throw AXProbeError.ax("AXUIElementPerformAction failed with \(error.rawValue)")
        }
        print("performed \(action) on:")
        printNode(node)
    case "focus":
        let contains = option("--contains", in: args)
        let role = option("--role", in: args)
        guard contains != nil || role != nil else {
            throw AXProbeError.usage("missing --contains or --role")
        }
        guard let node = findNode(root: root, contains: contains, role: role, maxDepth: maxDepth) else {
            throw AXProbeError.notFound("no matching accessibility node")
        }
        let error = AXUIElementSetAttributeValue(node.element, kAXFocusedAttribute as CFString, kCFBooleanTrue)
        guard error == .success else {
            throw AXProbeError.ax("AXUIElementSetAttributeValue AXFocused failed with \(error.rawValue)")
        }
        print("focused:")
        printNode(node)
    case "set-value":
        let contains = option("--contains", in: args)
        let role = option("--role", in: args)
        guard contains != nil || role != nil else {
            throw AXProbeError.usage("missing --contains or --role")
        }
        guard let value = option("--value", in: args) else {
            throw AXProbeError.usage("missing --value")
        }
        guard let node = findNode(root: root, contains: contains, role: role, maxDepth: maxDepth) else {
            throw AXProbeError.notFound("no matching accessibility node")
        }
        var settable = DarwinBoolean(false)
        let settableError = AXUIElementIsAttributeSettable(node.element, kAXValueAttribute as CFString, &settable)
        guard settableError == .success, settable.boolValue else {
            throw AXProbeError.ax("matched node AXValue is not settable")
        }
        let error = AXUIElementSetAttributeValue(node.element, kAXValueAttribute as CFString, value as CFTypeRef)
        guard error == .success else {
            throw AXProbeError.ax("AXUIElementSetAttributeValue failed with \(error.rawValue)")
        }
        print("set AXValue on:")
        printNode(node)
    case "set-bool":
        let contains = option("--contains", in: args)
        let role = option("--role", in: args)
        guard contains != nil || role != nil else {
            throw AXProbeError.usage("missing --contains or --role")
        }
        guard let attribute = option("--attribute", in: args) else {
            throw AXProbeError.usage("missing --attribute")
        }
        guard let valueText = option("--value", in: args) else {
            throw AXProbeError.usage("missing --value")
        }
        let boolValue: CFBoolean
        switch valueText.lowercased() {
        case "true", "1", "yes":
            boolValue = kCFBooleanTrue
        case "false", "0", "no":
            boolValue = kCFBooleanFalse
        default:
            throw AXProbeError.usage("--value must be true or false")
        }
        guard let node = findNode(root: root, contains: contains, role: role, maxDepth: maxDepth) else {
            throw AXProbeError.notFound("no matching accessibility node")
        }
        var settable = DarwinBoolean(false)
        let settableError = AXUIElementIsAttributeSettable(node.element, attribute as CFString, &settable)
        guard settableError == .success, settable.boolValue else {
            throw AXProbeError.ax("matched node \(attribute) is not settable")
        }
        let error = AXUIElementSetAttributeValue(node.element, attribute as CFString, boolValue)
        guard error == .success else {
            throw AXProbeError.ax("AXUIElementSetAttributeValue \(attribute) failed with \(error.rawValue)")
        }
        print("set \(attribute)=\(valueText) on:")
        printNode(node)
    default:
        usage()
    }
}

do {
    try main()
} catch let error as AXProbeError {
    fputs("axprobe: \(error.description)\n", stderr)
    exit(1)
} catch {
    fputs("axprobe: \(error)\n", stderr)
    exit(1)
}
