import QtQuick
import Quickshell
import qs.Ui

Item {
    id: root
    property var bar: null
    property var shell: null
    property var manifest: null
    property var settings: ({})
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    BarIconButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        text: "󰈷"
        tooltipText: "X1 Touch · Fingerprints"
        onPressed: {
            if (root.shell) root.shell.summon("io.github.dandiccf.x1-touch", "{}")
            else Quickshell.execDetached(["omarchy-shell", "shell", "summon", "io.github.dandiccf.x1-touch", "{}"])
        }
    }
}
