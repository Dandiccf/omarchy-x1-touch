import QtQuick
import QtQuick.Controls
import qs.Commons

Button {
    id: root
    property bool primary: false
    property bool danger: false
    property bool selected: false
    property bool compact: false
    readonly property color ink: danger ? Color.urgent : Color.accent
    implicitHeight: Style.space(compact ? 30 : 38)
    implicitWidth: label.implicitWidth + leftPadding + rightPadding + Style.space(8)
    leftPadding: Style.space(12)
    rightPadding: Style.space(12)
    opacity: enabled ? 1 : 0.35
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: text
    contentItem: Text {
        id: label
        text: root.text
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
        font.bold: root.primary || root.selected
        color: root.primary ? Color.background : root.danger ? Color.urgent : Color.foreground
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        radius: Style.cornerRadius
        color: root.primary ? root.ink : root.hovered || root.selected ? Qt.alpha(root.ink, 0.12) : "transparent"
        border.width: 1
        border.color: root.activeFocus || root.selected || root.primary ? root.ink : Qt.alpha(Color.foreground, root.hovered ? 0.45 : 0.18)
    }
}
