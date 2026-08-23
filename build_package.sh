#!/bin/bash
# DAMM v1.7 — assemble the review package.
# Built on LOCAL disk first, then moved across in a single operation: the pCloud FUSE
# mount has dropped twice under sustained small writes, and a local build survives that.
# Run only after gauntlet/loop-1/verify_end_to_end.py reports ALL CHECKS PASS.
set -e
cd "$(dirname "$0")"
SRC="$(pwd)"
PKGNAME="Katreyna-Review-Package-2026-08-23"
STAGE="/private/tmp/claude-501/pkgbuild/$PKGNAME"
L1="gauntlet/loop-1"
SKD="/Users/randeepsudan/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/7fa72b6b-bf7f-4b6d-9cd3-62aa57ef46d1/b21ce9e4-9f62-4185-8a66-257f1e009678/skills/docx"
# Transmittal source lives in the project, not a session scratchpad: a temp directory is not a
# source of record, and the package must rebuild from this repository alone.
TN="$SRC/transmittal"

rm -rf "$STAGE"; mkdir -p "$STAGE/1 Read first" "$STAGE/2 Diagnostic reports" "$STAGE/3 Instrument" "$STAGE/4 Method companions"

cp "$TN/note.docx"                   "$STAGE/1 Read first/00 Transmittal note.docx"
cp DAMM-v1.7-Guidebook.docx          "$STAGE/1 Read first/01 DAMM v1.7 Guidebook.docx"
cp DAMM-v1.7-Specification.md        "$STAGE/1 Read first/02 DAMM v1.7 Specification (decisions in section 13).md"
cp "$L1/Egypt-DAR-Diagnostic.html"   "$STAGE/2 Diagnostic reports/Egypt — Digital Agriculture Diagnostic.html"
cp "$L1/Nigeria-DAR-Diagnostic.html" "$STAGE/2 Diagnostic reports/Nigeria — Digital Agriculture Diagnostic.html"
cp "$L1"/workbooks-v1.7/*.xlsx       "$STAGE/3 Instrument/"
cp DAMM-v1.7-Indicator-Census.csv    "$STAGE/3 Instrument/"
cp DAMM-v1.7-Source-Tier-Protocol.md DAMM-v1.7-QC-Protocol.md DAMM-v1.7-Practice-Library-Schema.md "$STAGE/4 Method companions/"
cp "$L1/issues-log.md"               "$STAGE/4 Method companions/Test-run issues log.md"
cp "$L1/VERIFICATION-RECORD.md"      "$STAGE/4 Method companions/Build and verification record.md"

# PDF renditions, all produced on local disk
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TMPD="/private/tmp/claude-501/pkgpdf"; rm -rf "$TMPD"; mkdir -p "$TMPD"
for c in Egypt Nigeria; do
  timeout 90 "$CH" --headless --disable-gpu --no-pdf-header-footer \
    --print-to-pdf="$TMPD/$c.pdf" --virtual-time-budget=8000 --user-data-dir="$TMPD/p_$c" \
    "file://$STAGE/2 Diagnostic reports/$c — Digital Agriculture Diagnostic.html" >/dev/null 2>&1 || true
  [ -f "$TMPD/$c.pdf" ] && cp "$TMPD/$c.pdf" "$STAGE/2 Diagnostic reports/$c — Digital Agriculture Diagnostic.pdf"
done
# A wide table used to be CLIPPED in print, silently dropping the register's Overlaps and Source
# columns from the PDF while the HTML kept them. Every column header in the HTML must survive into
# the PDF text, or the package does not ship.
python3 - "$STAGE" <<'PYCHK'
import sys, os, re, html, subprocess
stage = sys.argv[1]; bad = []
def toks(s):
    # compare on distinctive words: a header may wrap across lines in the PDF, but a CROPPED
    # column loses its words entirely, which is the thing being guarded against.
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if len(t) >= 4}
for c in ("Egypt", "Nigeria"):
    h = os.path.join(stage, "2 Diagnostic reports", f"{c} \u2014 Digital Agriculture Diagnostic.html")
    p = h[:-4] + "pdf"
    if not os.path.exists(p):
        bad.append(f"{c}: PDF not produced"); continue
    heads = {re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m))).strip()
             for m in re.findall(r"<th[^>]*>(.*?)</th>", open(h).read(), re.S)}
    heads = {x for x in heads if toks(x)}
    txt = subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True, text=True).stdout
    have = set(re.findall(r"[a-z0-9]+", txt.lower()))
    missing = sorted(x for x in heads if not toks(x) <= have)
    if missing: bad.append(f"{c}: columns lost in PDF -> {missing}")
    else: print(f"  {c}: all {len(heads)} table columns present in the PDF")
if bad:
    print("PACKAGE BLOCKED - PDF layout regression:"); [print("  -", b) for b in bad]; sys.exit(1)
print("PDF column check passed")
PYCHK

for f in "01 DAMM v1.7 Guidebook" "00 Transmittal note"; do
  python3 "$SKD/scripts/office/soffice.py" --headless --convert-to pdf --outdir "$TMPD" "$STAGE/1 Read first/$f.docx" >/dev/null 2>&1 || true
  [ -f "$TMPD/$f.pdf" ] && cp "$TMPD/$f.pdf" "$STAGE/1 Read first/"
done
for f in "$STAGE/1 Read first/"*.md "$STAGE/4 Method companions/"*.md; do
  pandoc "$f" -o "${f%.md}.docx" 2>/dev/null || true
done

# The project itself lives on local disk; the finished package is assembled here first, so a
# build never depends on the network mount being up.
rm -rf "$SRC/$PKGNAME"
cp -R "$STAGE" "$SRC/$PKGNAME"
echo "package assembled: $PKGNAME"
find "$SRC/$PKGNAME" -type f | wc -l | xargs echo "files:"

# Publish to pCloud last, in one bulk copy, and never fail the build on it: the mount is a
# synchronous FUSE volume that has dropped three times under sustained writes. If it is down,
# the finished package is already safe locally — re-run just this step later.
PUBLISH="/Users/randeepsudan/pCloud Drive/02 World Bank/Projects/DAR/DAMM"
if [ -d "$PUBLISH" ]; then
  if rm -rf "$PUBLISH/$PKGNAME" 2>/dev/null && cp -R "$SRC/$PKGNAME" "$PUBLISH/$PKGNAME" 2>/dev/null; then
    echo "published to pCloud: $PUBLISH/$PKGNAME"
  else
    echo "WARNING: pCloud publish failed (mount down or dropped mid-copy)."
    echo "         The package is complete at: $SRC/$PKGNAME"
    echo "         Re-publish with: cp -R \"$SRC/$PKGNAME\" \"$PUBLISH/\""
  fi
else
  echo "NOTE: pCloud not mounted; package is at $SRC/$PKGNAME. Publish later with:"
  echo "      cp -R \"$SRC/$PKGNAME\" \"$PUBLISH/\""
fi
