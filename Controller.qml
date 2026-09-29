import QtQuick
import Quickshell.Io

Item {
    id: root
    property string helper: decodeURIComponent(Qt.resolvedUrl("backend/fingerprint.py").toString().replace(/^file:\/\//, ""))
    property var snapshot: ({fingers: [], auth: {}, packages: [], present: false})
    property var preferences: ({verifyTimeout: 20, enrollTimeout: 90, animations: true, showHints: true, defaultHand: "right"})
    property bool busy: false
    property bool refreshing: false
    property bool initialized: false
    property bool saving: false
    property string action: ""
    property string phase: "idle"
    property string message: "Select a finger to get started."
    property string result: ""
    property int passed: 0
    property int stages: 0
    property int elapsed: 0
    property int limit: 20
    property bool terminalEvent: false
    property var recentEvents: []
    signal loaded()

    function refresh() {
        if (busy || refreshing || saving) return
        refreshing = true
        statusProcess.running = true
    }
    function receive(line, stream) {
        var event
        try { event = JSON.parse(line) } catch (e) { return }
        if (event.type === "snapshot") {
            snapshot = event
            preferences = event.settings
            if (!initialized) { initialized = true; loaded() }
            return
        }
        if (event.type === "settings") { preferences = event.settings; return }
        if (stream === "status" || stream === "settings") {
            if (event.type === "error") { result = "error"; message = event.message }
            return
        }
        if (event.message) message = event.message
        if (event.type === "phase") {
            phase = event.code
            if (event.stages !== undefined) stages = event.stages
        }
        if (event.type === "scan") {
            passed = event.passed
            stages = event.stages
            recentEvents = [{text: event.message, seconds: elapsed}].concat(recentEvents).slice(0, 4)
        }
        if (event.type === "error" || event.type === "result" || event.done === true) {
            terminalEvent = true
            result = event.success ? "success" : event.code === "cancelled" ? "cancelled" : "error"
            phase = "finished"
        }
    }
    function start(kind, finger) {
        if (busy || refreshing || saving) return
        busy = true
        action = kind
        phase = "authorizing"
        result = ""
        passed = 0; stages = 0; elapsed = 0
        terminalEvent = false
        recentEvents = []
        message = "Requesting access to the reader…"
        limit = kind === "enroll" ? preferences.enrollTimeout : preferences.verifyTimeout
        var command = ["/usr/bin/python", "-u", helper, kind, "--finger", finger, "--timeout", String(limit)]
        if (kind === "delete") command = command.concat(["--confirm-finger", finger])
        operation.command = command
        operation.running = true
    }
    function cancel() {
        if (!busy) return
        phase = "cancelling"
        message = "Releasing the reader…"
        operation.signal(15)
        cancelDeadline.restart()
    }
    function save(key, value) {
        if (busy || saving || refreshing) return
        var next = Object.assign({}, preferences)
        next[key] = value
        settingsProcess.command = ["/usr/bin/python", "-u", helper, "settings", "--json", JSON.stringify(next)]
        saving = true
        settingsProcess.running = true
    }
    Process {
        id: statusProcess
        command: ["/usr/bin/python", "-u", root.helper, "status"]
        stdout: SplitParser { onRead: data => root.receive(data, "status") }
        onExited: function(code) {
            root.refreshing = false
            if (code !== 0 && !root.initialized) root.message = "Could not read sensor status. Check python-gobject and fprintd."
        }
    }
    Process {
        id: settingsProcess
        stdout: SplitParser { onRead: data => root.receive(data, "settings") }
        onExited: function(code) {
            root.saving = false
            if (code !== 0) { root.result = "error"; root.message = "Preferences could not be saved." }
        }
    }
    Process {
        id: operation
        stdout: SplitParser { onRead: data => root.receive(data, "operation") }
        onExited: function(code) {
            cancelDeadline.stop()
            root.busy = false
            if (!root.terminalEvent) {
                root.result = root.phase === "cancelling" ? "cancelled" : "error"
                root.message = root.result === "cancelled" ? "Scan cancelled" : "The operation stopped unexpectedly. Refresh and try again."
            }
            root.phase = "finished"
            Qt.callLater(root.refresh)
        }
    }
    Timer {
        interval: 1000
        repeat: true
        running: root.busy && root.phase === "scanning"
        onTriggered: root.elapsed++
    }
    Timer {
        id: cancelDeadline
        interval: 4000
        onTriggered: if (operation.running) operation.running = false
    }
    Component.onDestruction: if (operation.running) operation.running = false
}
