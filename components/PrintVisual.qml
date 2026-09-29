import QtQuick
import qs.Commons

Item {
    id: root
    property bool scanning: false
    property bool animated: true
    property bool success: false
    property bool failed: false
    property real sweep: 0
    readonly property color ink: failed ? Color.urgent : Color.accent
    implicitWidth: 220
    implicitHeight: 240

    Canvas {
        id: printCanvas
        anchors.fill: parent
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            var sx = width / 220, sy = height / 240
            ctx.scale(sx, sy)
            ctx.lineCap = "round"
            // An illustrative ridge pattern, never biometric data.
            ctx.strokeStyle = Qt.alpha(root.ink, root.scanning || root.success ? 0.95 : 0.58)
            ctx.lineWidth = 2
            for (var i = 0; i < 10; i++) {
                var spread = 11 + i * 8
                ctx.beginPath()
                ctx.moveTo(110 - spread, 156 + i * 2.9)
                ctx.bezierCurveTo(110 - spread - 5, 99 - i * 5, 110 - spread * .55, 74 - i * 4.1, 110, 74 - i * 4.1)
                ctx.bezierCurveTo(110 + spread * .72, 74 - i * 4.1, 110 + spread + 8, 106 - i * 3, 110 + spread - 3, 155 + i * 1.7)
                ctx.stroke()
            }
            for (var j = 0; j < 6; j++) {
                ctx.beginPath()
                ctx.moveTo(102 + j * 8, 103 + j * 2)
                ctx.bezierCurveTo(98 + j * 8, 144, 118 + j * 6, 174, 93 + j * 6, 206)
                ctx.stroke()
            }
            ctx.strokeStyle = Qt.alpha(root.ink, .25)
            ctx.lineWidth = 1
            var corners = [[12, 22, 1, 1], [208, 22, -1, 1], [12, 218, 1, -1], [208, 218, -1, -1]]
            corners.forEach(function(c) {
                ctx.beginPath(); ctx.moveTo(c[0] + c[2] * 16, c[1]); ctx.lineTo(c[0], c[1]); ctx.lineTo(c[0], c[1] + c[3] * 16); ctx.stroke()
            })
        }
        Connections {
            target: root
            function onInkChanged() { printCanvas.requestPaint() }
            function onScanningChanged() { printCanvas.requestPaint() }
            function onSuccessChanged() { printCanvas.requestPaint() }
        }
    }
    Rectangle {
        visible: root.scanning
        x: 12
        width: parent.width - 24
        height: 1
        y: root.animated ? 24 + root.sweep * (parent.height - 48) : parent.height / 2
        color: root.ink
        Rectangle { anchors.bottom: parent.top; width: parent.width; height: 14; color: Qt.alpha(root.ink, .06) }
    }
    NumberAnimation on sweep {
        from: 0; to: 1; duration: 2000
        running: root.scanning && root.animated
        loops: Animation.Infinite
    }
}
