#!/usr/bin/env bash
# Builds "Researchly Overlay.app" (and optionally a .dmg) on a Mac.
#
#   ./build.sh            release build → build/Researchly Overlay.app
#   ./build.sh --dmg      ...and build/Researchly-Overlay.dmg
#   ./build.sh --test     run the core's unit tests first
#
# Needs: macOS 14+, Xcode Command Line Tools with Swift 5.9 or newer
# (`xcode-select --install`). Nothing is downloaded: the app has no
# third-party dependencies.
#
# Signing: ad-hoc (`codesign -s -`), as the project is open source and not
# sold (PLAN D9). macOS treats every rebuild as a new app, so Accessibility
# must be allowed again after each build (README, "Granting Accessibility").
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
RULES="$REPO/packages/desktop-rules"
BUILD="$HERE/build"
APP="$BUILD/Researchly Overlay.app"
VERSION="0.1.0"
BUILD_NUMBER="$(date +%Y%m%d%H%M)"

make_dmg=0
run_tests=0
for arg in "$@"; do
  case "$arg" in
    --dmg) make_dmg=1 ;;
    --test) run_tests=1 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "build.sh builds the macOS app and must run on a Mac." >&2
  echo "(On Linux, 'swift test' still runs the core's tests.)" >&2
  exit 1
fi

if ! command -v swift >/dev/null 2>&1; then
  echo "Swift was not found. Install the Command Line Tools: xcode-select --install" >&2
  exit 1
fi

for f in fields.json apps-mac.json; do
  if [[ ! -f "$RULES/$f" ]]; then
    echo "Missing $RULES/$f — run this script from a full checkout of the repository." >&2
    exit 1
  fi
  # Refuse to bundle a rules file that does not parse (the app would not start).
  if command -v python3 >/dev/null 2>&1; then
    python3 -c "import json,sys; json.load(open(sys.argv[1], encoding='utf-8'))" "$RULES/$f" \
      || { echo "$RULES/$f is not valid JSON." >&2; exit 1; }
  fi
done

cd "$HERE"
echo "==> Swift $(swift --version 2>&1 | head -n 1)"

if [[ $run_tests -eq 1 ]]; then
  echo "==> Testing the core"
  swift test
fi

echo "==> Building (release)"
swift build -c release --product ResearchlyOverlay
BIN="$(swift build -c release --show-bin-path)/ResearchlyOverlay"

echo "==> Assembling $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/ResearchlyOverlay"
sed -e "s/__VERSION__/$VERSION/" -e "s/__BUILD__/$BUILD_NUMBER/" \
  "$HERE/Support/Info.plist" > "$APP/Contents/Info.plist"
cp "$RULES/fields.json" "$RULES/apps-mac.json" "$APP/Contents/Resources/"
printf 'APPL????' > "$APP/Contents/PkgInfo"

echo "==> Signing (ad hoc)"
codesign --force --deep --sign - --identifier org.researchly.overlay "$APP"
codesign --verify --verbose=1 "$APP"

if [[ $make_dmg -eq 1 ]]; then
  echo "==> Making the disk image"
  DMG="$BUILD/Researchly-Overlay.dmg"
  STAGE="$BUILD/dmg"
  rm -rf "$STAGE" "$DMG"
  mkdir -p "$STAGE"
  cp -R "$APP" "$STAGE/"
  ln -s /Applications "$STAGE/Applications"
  hdiutil create -volname "Researchly Overlay" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
  rm -rf "$STAGE"
  echo "    $DMG"
fi

cat <<EOF

Built: $APP

Next:
  1. Move it to /Applications (or run it from here):
       open "$APP"
  2. Follow the window that opens to allow Accessibility.
     After every rebuild, remove the old entry in System Settings →
     Privacy & Security → Accessibility and allow the new one.
  3. Choose the engine in the menu-bar item (This computer, or Hosted).
EOF
