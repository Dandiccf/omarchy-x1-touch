#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
omarchy plugin validate .
/usr/bin/python -m unittest discover -s tests -v
/usr/bin/python -m py_compile backend/*.py scripts/*.py

# Omarchy's qs.Commons import needs a qs module root for standalone linting.
lint_root=$(mktemp -d)
trap 'rm -rf -- "$lint_root"' EXIT
ln -s /usr/share/omarchy/shell "$lint_root/qs"
/usr/lib/qt6/bin/qmllint -I "$lint_root" \
  --uncreatable-type disable --signal-handler-parameters disable \
  --missing-property disable \
  Panel.qml Controller.qml BarWidget.qml components/*.qml
# Suppress only host metadata gaps: Quickshell PanelWindow / QProcess enum and
# Omarchy's dynamically declared Style.font QObject properties. Live smoke
# testing remains required because static lint cannot resolve those types.
