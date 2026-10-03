#!/bin/bash
# Sideload the Researchly add-in into Word for Mac.
# Copies the manifest into Word's add-in folder ("wef"). Run once; after
# that the add-in appears in Word under Insert > Add-ins (or the Add-ins
# button) > "Developer Add-ins" / "My Add-ins" > Researchly.

set -e
WEF="$HOME/Library/Containers/com.microsoft.Word/Data/Documents/wef"
HERE="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$WEF"
cp "$HERE/manifest.xml" "$WEF/researchly-manifest.xml"

echo "Manifest installed to:"
echo "  $WEF/researchly-manifest.xml"
echo
echo "Next steps:"
echo "  1. Start the local server:   python3 \"$HERE/server.py\""
echo "  2. Quit and reopen Word."
echo "  3. In Word: Insert tab > Add-ins dropdown > Developer Add-ins > Researchly"
echo "     (on some versions: Insert > My Add-ins > Researchly)"
