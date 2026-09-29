pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import qs.Commons
import "components"

Item {
    id: root
    property var shell: null
    property var manifest: null
    property bool opened: false
    property string page: "fingers"
    property string hand: "right"
    property string selectedFinger: "right-index-finger"
    property bool confirmingDelete: false
    readonly property bool enrolled: controller.snapshot.fingers.indexOf(selectedFinger) >= 0
    readonly property bool ready: controller.snapshot.present && !controller.snapshot.error && !controller.busy && !controller.refreshing && !controller.saving
    readonly property var fingerNames: ["thumb", "index-finger", "middle-finger", "ring-finger", "little-finger"]
    readonly property color line: Qt.alpha(Color.foreground, 0.13)
    readonly property color faint: Qt.alpha(Color.foreground, 0.55)
    readonly property string selectedName: pretty(selectedFinger)

    function pretty(value) { return value.replace("-finger", "").replace(/-/g, " ").replace(/^./, c => c.toUpperCase()) }
    function open(payload) {
        var options = {}
        try { options = JSON.parse(payload || "{}") } catch (e) {}
        if (options && ["fingers", "preferences", "system"].indexOf(options.page) >= 0) page = options.page
        opened = true
        confirmingDelete = false
        controller.refresh()
        Qt.callLater(function() { keyRoot.forceActiveFocus() })
    }
    function close() {
        controller.cancel()
        opened = false
    }
    function dismiss() {
        close()
        if (shell) shell.hide("io.github.dandiccf.x1-touch")
    }
    function chooseHand(value) {
        if (controller.busy) return
        hand = value
        selectedFinger = value + "-index-finger"
        confirmingDelete = false
    }
    function chooseFinger(value) {
        if (controller.busy) return
        selectedFinger = value
        confirmingDelete = false
    }
    Controller {
        id: controller
        onLoaded: root.chooseHand(preferences.defaultHand)
    }

    PanelWindow {
        id: window
        visible: root.opened
        anchors { top: true; bottom: true; left: true; right: true }
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "x1-touch"
        WlrLayershell.layer: WlrLayer.Overlay
        // OnDemand lets Omarchy's Polkit prompt receive focus during enrollment.
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand

        Rectangle {
            anchors.fill: parent
            color: Qt.rgba(0, 0, 0, .48)
            MouseArea { anchors.fill: parent; onClicked: root.dismiss() }
        }
        FocusScope {
            id: keyRoot
            anchors.fill: parent
            focus: true
            Keys.onEscapePressed: {
                if (root.confirmingDelete) root.confirmingDelete = false
                else if (controller.busy) controller.cancel()
                else root.dismiss()
            }
            Rectangle {
                id: card
                width: Style.space(900)
                height: Style.space(740)
                anchors.centerIn: parent
                scale: Math.min(1, (keyRoot.width - 32) / width, (keyRoot.height - 32) / height)
                color: Color.background
                border.width: 1
                border.color: Qt.alpha(Color.accent, .6)
                radius: Style.cornerRadius
                MouseArea { anchors.fill: parent; onClicked: keyRoot.forceActiveFocus() }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Style.space(28)
                    spacing: Style.space(22)

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Style.space(14)
                        Rectangle {
                            implicitWidth: Style.space(40); implicitHeight: implicitWidth
                            color: Color.accent
                            radius: Style.cornerRadius
                            TouchText { anchors.centerIn: parent; text: "X1"; color: Color.background; font.bold: true; font.pixelSize: Style.font.heading }
                        }
                        ColumnLayout {
                            spacing: 2
                            TouchText { text: "TOUCH"; font.pixelSize: Style.font.heading; font.bold: true; font.letterSpacing: 4 }
                            TouchText { text: "Your fingerprint studio"; color: root.faint; font.pixelSize: Style.font.caption }
                        }
                        Item { Layout.fillWidth: true }
                        Rectangle { implicitWidth: 6; implicitHeight: 6; radius: 3; color: controller.snapshot.present ? Color.accent : Color.urgent }
                        TouchText { text: controller.refreshing ? "CHECKING" : controller.snapshot.present ? "READER ONLINE" : "READER OFFLINE"; color: root.faint; font.pixelSize: Style.font.caption; font.letterSpacing: 1 }
                        TouchButton { text: "Refresh"; compact: true; enabled: !controller.busy && !controller.refreshing; onClicked: controller.refresh() }
                        TouchButton { text: "×"; compact: true; implicitWidth: Style.space(32); Accessible.name: "Close fingerprint studio"; onClicked: root.dismiss() }
                    }
                    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: root.line }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: Style.space(28)

                        ColumnLayout {
                            Layout.preferredWidth: Style.space(246)
                            Layout.minimumWidth: 0
                            Layout.maximumWidth: Style.space(246)
                            Layout.fillHeight: true
                            spacing: Style.space(10)
                            TouchText { text: "FINGERPRINT / FPRINTD"; color: root.faint; font.pixelSize: Style.font.caption; font.letterSpacing: 1 }
                            PrintVisual {
                                Layout.alignment: Qt.AlignHCenter
                                Layout.preferredWidth: Style.space(218)
                                Layout.preferredHeight: Style.space(235)
                                scanning: controller.busy && controller.phase === "scanning"
                                animated: controller.preferences.animations
                                success: controller.result === "success"
                                failed: controller.result === "error"
                            }
                            TouchText { text: controller.busy ? "Listening to the reader" : "Your print. Your machine."; font.bold: true; font.pixelSize: Style.font.body }
                            TouchText {
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                                text: (controller.snapshot.name || "No reader detected") + "\n" + controller.snapshot.fingers.length + " of 10 fingers enrolled"
                                color: root.faint
                                font.pixelSize: Style.font.caption
                                lineHeight: 1.5
                            }
                            Item { Layout.fillHeight: true }
                            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: root.line }
                            TouchText {
                                Layout.fillWidth: true
                                visible: controller.preferences.showHints
                                text: controller.snapshot.scanType === "swipe" ? "Swipe your fingertip steadily across the sensor. Lift fully between swipes. Keep the sensor clean and dry." : controller.snapshot.scanType === "press" ? "Rest your fingertip flat. Lift fully between touches. A clean, dry sensor works best." : "Follow your reader’s scan instructions. Keep your finger and sensor clean and dry."
                                wrapMode: Text.WordWrap
                                color: root.faint
                                font.pixelSize: Style.font.caption
                                lineHeight: 1.4
                            }
                            TouchText { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: "Illustration · no fingerprint image stored"; color: root.faint; font.pixelSize: Style.font.caption * .85 }
                        }
                        Rectangle { Layout.fillHeight: true; implicitWidth: 1; color: root.line }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: Style.space(16)
                            RowLayout {
                                spacing: Style.space(6)
                                Repeater {
                                    model: [{id: "fingers", label: "Fingerprints"}, {id: "preferences", label: "Preferences"}, {id: "system", label: "System"}]
                                    TouchButton {
                                        required property var modelData
                                        text: modelData.label
                                        selected: root.page === modelData.id
                                        compact: true
                                        onClicked: { root.page = modelData.id; root.confirmingDelete = false }
                                    }
                                }
                            }

                            ColumnLayout {
                                visible: root.page === "fingers"
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                spacing: Style.space(10)
                                RowLayout {
                                    Layout.fillWidth: true
                                    TouchText { text: "Choose a finger"; font.bold: true; Layout.fillWidth: true }
                                    TouchButton { text: "Left"; selected: root.hand === "left"; compact: true; enabled: !controller.busy; onClicked: root.chooseHand("left") }
                                    TouchButton { text: "Right"; selected: root.hand === "right"; compact: true; enabled: !controller.busy; onClicked: root.chooseHand("right") }
                                }
                                // Five distinct touch targets form a stylized hand. Labels and
                                // the list below provide an accessible equivalent to the diagram.
                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: Style.space(106)
                                    spacing: Style.space(7)
                                    Repeater {
                                        model: root.hand === "right" ? [0, 1, 2, 3, 4] : [4, 3, 2, 1, 0]
                                        Button {
                                            id: fingerButton
                                            required property int modelData
                                            readonly property string finger: root.hand + "-" + root.fingerNames[modelData]
                                            readonly property bool registered: controller.snapshot.fingers.indexOf(finger) >= 0
                                            readonly property bool chosen: root.selectedFinger === finger
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: Style.space([65, 94, 106, 96, 77][modelData])
                                            Layout.alignment: Qt.AlignBottom
                                            enabled: !controller.busy
                                            hoverEnabled: true
                                            Accessible.name: root.pretty(finger) + (registered ? ", enrolled" : ", not enrolled")
                                            onClicked: root.chooseFinger(finger)
                                            background: Rectangle {
                                                radius: width / 2
                                                color: fingerButton.chosen ? Qt.alpha(Color.accent, .14) : Qt.alpha(Color.foreground, .025)
                                                border.width: fingerButton.chosen ? 2 : 1
                                                border.color: fingerButton.chosen || fingerButton.activeFocus ? Color.accent : fingerButton.hovered ? Qt.alpha(Color.accent, .65) : root.line
                                            }
                                            contentItem: Column {
                                                anchors.centerIn: parent
                                                spacing: Style.space(5)
                                                TouchText { anchors.horizontalCenter: parent.horizontalCenter; text: ["TH", "IN", "MI", "RI", "LI"][fingerButton.modelData]; font.pixelSize: Style.font.caption; color: fingerButton.chosen ? Color.accent : root.faint }
                                                Rectangle { anchors.horizontalCenter: parent.horizontalCenter; width: 5; height: 5; radius: 3; color: fingerButton.registered ? Color.accent : "transparent"; border.width: 1; border.color: fingerButton.registered ? Color.accent : root.faint }
                                            }
                                        }
                                    }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 0
                                    Repeater {
                                        model: root.fingerNames
                                        Button {
                                            id: fingerRow
                                            required property string modelData
                                            readonly property string finger: root.hand + "-" + modelData
                                            readonly property bool registered: controller.snapshot.fingers.indexOf(finger) >= 0
                                            Layout.fillWidth: true
                                            implicitHeight: Style.space(31)
                                            enabled: !controller.busy
                                            hoverEnabled: true
                                            Accessible.name: root.pretty(finger) + (registered ? ", enrolled" : ", empty")
                                            onClicked: root.chooseFinger(finger)
                                            background: Rectangle { color: root.selectedFinger === fingerRow.finger || fingerRow.hovered || fingerRow.activeFocus ? Qt.alpha(Color.accent, .08) : "transparent"; radius: Style.cornerRadius }
                                            contentItem: RowLayout {
                                                spacing: 10
                                                TouchText { text: root.selectedFinger === fingerRow.finger ? "›" : " "; color: Color.accent; Layout.leftMargin: Style.space(8) }
                                                TouchText { text: root.pretty(fingerRow.finger); font.pixelSize: Style.font.bodySmall; Layout.fillWidth: true }
                                                TouchText { text: fingerRow.registered ? "ENROLLED" : "EMPTY"; color: fingerRow.registered ? Color.accent : root.faint; font.pixelSize: Style.font.caption * .9; Layout.rightMargin: Style.space(8) }
                                            }
                                        }
                                    }
                                }
                                Item { Layout.fillHeight: true }
                                RowLayout {
                                    visible: !root.confirmingDelete
                                    Layout.fillWidth: true
                                    TouchButton { text: root.enrolled ? "Test fingerprint" : "Enroll fingerprint"; primary: true; enabled: root.ready; onClicked: controller.start(root.enrolled ? "verify" : "enroll", root.selectedFinger) }
                                    TouchButton { text: "Remove"; danger: true; visible: root.enrolled; enabled: root.ready; onClicked: root.confirmingDelete = true }
                                    Item { Layout.fillWidth: true }
                                }
                                ColumnLayout {
                                    visible: root.confirmingDelete
                                    Layout.fillWidth: true
                                    spacing: Style.space(6)
                                    TouchText { Layout.fillWidth: true; text: "Remove " + root.selectedName.toLowerCase() + "? You’ll need to enroll it again to use it."; wrapMode: Text.WordWrap; color: Color.urgent; font.pixelSize: Style.font.caption }
                                    RowLayout {
                                        TouchButton { text: "Remove this finger"; danger: true; enabled: root.ready; onClicked: { root.confirmingDelete = false; controller.start("delete", root.selectedFinger) } }
                                        TouchButton { text: "Keep it"; onClicked: root.confirmingDelete = false }
                                    }
                                }
                            }

                            ColumnLayout {
                                visible: root.page === "preferences"
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                spacing: Style.space(14)
                                TouchText { text: "Make it feel like yours"; font.bold: true }
                                TouchText { text: "These settings apply to scans inside X1 Touch."; color: root.faint; font.pixelSize: Style.font.caption; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                                SettingRow {
                                    Layout.fillWidth: true
                                    title: "Test timeout"; detail: "Time to present your finger"
                                    value: controller.preferences.verifyTimeout + "s"
                                    onMinus: controller.save("verifyTimeout", Math.max(10, controller.preferences.verifyTimeout - 5))
                                    onPlus: controller.save("verifyTimeout", Math.min(60, controller.preferences.verifyTimeout + 5))
                                }
                                SettingRow {
                                    Layout.fillWidth: true
                                    title: "Enrollment timeout"; detail: "Time for all enrollment stages"
                                    value: controller.preferences.enrollTimeout + "s"
                                    onMinus: controller.save("enrollTimeout", Math.max(30, controller.preferences.enrollTimeout - 15))
                                    onPlus: controller.save("enrollTimeout", Math.min(180, controller.preferences.enrollTimeout + 15))
                                }
                                PreferenceToggle { title: "Scan animation"; detail: "A moving guide while the reader waits"; checked: controller.preferences.animations; onToggled: controller.save("animations", !checked) }
                                PreferenceToggle { title: "Helpful hints"; detail: "Show placement tips beside the reader"; checked: controller.preferences.showHints; onToggled: controller.save("showHints", !checked) }
                                RowLayout {
                                    Layout.fillWidth: true
                                    TouchText { text: "Start with"; Layout.fillWidth: true; font.pixelSize: Style.font.bodySmall }
                                    TouchButton { text: "Left hand"; compact: true; selected: controller.preferences.defaultHand === "left"; enabled: !controller.busy && !controller.saving; onClicked: controller.save("defaultHand", "left") }
                                    TouchButton { text: "Right hand"; compact: true; selected: controller.preferences.defaultHand === "right"; enabled: !controller.busy && !controller.saving; onClicked: controller.save("defaultHand", "right") }
                                }
                                Item { Layout.fillHeight: true }
                                TouchText { text: controller.saving ? "Saving…" : "Saved automatically · follows your Omarchy theme"; color: root.faint; font.pixelSize: Style.font.caption }
                            }

                            ColumnLayout {
                                visible: root.page === "system"
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                spacing: Style.space(12)
                                TouchText { text: "The reader, at a glance"; font.bold: true }
                                SystemRow { label: "Machine"; value: controller.snapshot.model || "This computer" }
                                SystemRow { label: "Sensor"; value: controller.snapshot.name || "Not detected" }
                                SystemRow { label: "Backend"; value: "fprintd / libfprint" }
                                SystemRow { label: "Scan method"; value: controller.snapshot.scanType === "swipe" ? "Swipe" : controller.snapshot.scanType === "press" ? "Press" : "Unknown" }
                                SystemRow { label: "Account"; value: controller.snapshot.user || "Current user" }
                                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: root.line }
                                TouchText { text: "AUTHENTICATION"; font.pixelSize: Style.font.caption; color: root.faint; font.letterSpacing: 1 }
                                SystemRow { label: "sudo"; value: root.authLabel("sudo") }
                                SystemRow { label: "Authorization dialogs"; value: root.authLabel("polkit") }
                                SystemRow { label: "Lock screen"; value: root.authLabel("lock") }
                                TouchText { Layout.fillWidth: true; text: "Configuration detected on disk. Actual login behavior is managed by Omarchy."; wrapMode: Text.WordWrap; color: root.faint; font.pixelSize: Style.font.caption }
                                Item { Layout.fillHeight: true }
                                TouchText { Layout.fillWidth: true; text: (controller.snapshot.packages || []).join("\n"); color: root.faint; font.pixelSize: Style.font.caption * .9; wrapMode: Text.WrapAnywhere }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: Style.space(76)
                        color: Qt.alpha(controller.result === "error" || controller.snapshot.error ? Color.urgent : Color.accent, .045)
                        border.width: 1
                        border.color: controller.result === "error" ? Qt.alpha(Color.urgent, .45) : root.line
                        radius: Style.cornerRadius
                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: Style.space(14)
                            spacing: Style.space(12)
                            TouchText { text: controller.busy ? "◎" : controller.result === "success" ? "✓" : controller.result === "error" || controller.snapshot.error ? "!" : "◌"; font.pixelSize: Style.space(25); color: controller.result === "error" || controller.snapshot.error ? Color.urgent : Color.accent }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: Style.space(6)
                                TouchText {
                                    Layout.fillWidth: true
                                    text: controller.snapshot.error && !controller.busy ? controller.snapshot.error : controller.message
                                    font.pixelSize: Style.font.bodySmall
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 2
                                    elide: Text.ElideRight
                                }
                                Rectangle {
                                    visible: controller.busy && controller.phase === "scanning"
                                    Layout.fillWidth: true
                                    implicitHeight: 3
                                    color: root.line
                                    Rectangle {
                                        height: parent.height
                                        width: parent.width * (controller.action === "enroll" && controller.stages > 0 ? Math.min(1, controller.passed / controller.stages) : Math.min(1, controller.elapsed / controller.limit))
                                        color: Color.accent
                                        Behavior on width { NumberAnimation { duration: controller.preferences.animations ? 180 : 0 } }
                                    }
                                }
                                TouchText {
                                    visible: controller.busy
                                    text: controller.phase === "authorizing" ? "Approve the system dialog if prompted" : controller.phase === "scanning" ? (controller.action === "enroll" && controller.stages > 0 ? controller.passed + " / " + controller.stages + " scans  ·  " : "") + Math.max(0, controller.limit - controller.elapsed) + "s remaining" : "Finishing…"
                                    color: root.faint; font.pixelSize: Style.font.caption
                                }
                            }
                            TouchButton { text: "Cancel"; compact: true; visible: controller.busy; enabled: controller.phase !== "cancelling"; onClicked: controller.cancel() }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        TouchText { text: "X1 TOUCH  /  0.2.0"; color: root.faint; font.pixelSize: Style.font.caption * .85; font.letterSpacing: 1 }
                        Item { Layout.fillWidth: true }
                        TouchText { text: "Tab to navigate   ·   Esc to " + (controller.busy ? "cancel" : "close"); color: root.faint; font.pixelSize: Style.font.caption }
                    }
                }
            }
        }
    }
    function authLabel(key) { return controller.snapshot.auth[key] === "configured" ? "Configured" : "Not configured" }

    component SystemRow: RowLayout {
        id: systemRow
        property string label: ""
        property string value: ""
        Layout.fillWidth: true
        spacing: Style.space(16)
        TouchText { text: systemRow.label; color: root.faint; font.pixelSize: Style.font.caption; Layout.preferredWidth: Style.space(153) }
        TouchText { text: systemRow.value; font.pixelSize: Style.font.caption; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    }
    component SettingRow: RowLayout {
        property string title: ""
        property string detail: ""
        property string value: ""
        signal minus()
        signal plus()
        id: row
        Layout.fillWidth: true
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 3
            TouchText { text: row.title; font.pixelSize: Style.font.bodySmall }
            TouchText { text: row.detail; color: root.faint; font.pixelSize: Style.font.caption }
        }
        TouchButton { text: "−"; compact: true; enabled: !controller.busy && !controller.saving; Accessible.name: "Decrease " + row.title; onClicked: row.minus() }
        TouchText { text: row.value; Layout.preferredWidth: Style.space(40); horizontalAlignment: Text.AlignHCenter; font.pixelSize: Style.font.bodySmall }
        TouchButton { text: "+"; compact: true; enabled: !controller.busy && !controller.saving; Accessible.name: "Increase " + row.title; onClicked: row.plus() }
    }
    component PreferenceToggle: RowLayout {
        id: row
        property string title: ""
        property string detail: ""
        property bool checked: false
        signal toggled()
        Layout.fillWidth: true
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 3
            TouchText { text: row.title; font.pixelSize: Style.font.bodySmall }
            TouchText { text: row.detail; color: root.faint; font.pixelSize: Style.font.caption }
        }
        TouchButton { text: row.checked ? "On" : "Off"; selected: row.checked; compact: true; implicitWidth: Style.space(64); enabled: !controller.busy && !controller.saving; Accessible.name: row.title + ": " + text; onClicked: row.toggled() }
    }
}
