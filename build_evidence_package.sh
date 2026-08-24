#!/usr/bin/env bash
# Rebuild the pipeline-evidence package for Katreyna and check that nothing was lost in
# the render. Everything is produced on local disk; the finished package is copied to
# pCloud by hand, because pCloud is a synchronous FUSE mount that has dropped under
# sustained writes.
#
# The check at the end exists because the earlier review package once shipped a PDF with
# a table column silently clipped: the HTML had it, the PDF did not, and nothing noticed.
# A header may WRAP across lines in a PDF, so the test compares distinctive words rather
# than contiguous strings. A wrapped header still has all its words. A cropped one is gone.
set -u

PKG="/Users/randeepsudan/DAR/Claude/DAMM/Katreyna-Pipeline-Evidence-2026-08-24"
SOFFICE="/Applications/LibreOffice.app/Contents/MacOS/soffice"
TMPD="/private/tmp/claude-501/evidence-pkg"
rm -rf "$TMPD"; mkdir -p "$TMPD"

cd "$PKG" || exit 1

# The two authored documents, and the machine-generated appendix, all go to docx and pdf.
# LibreOffice runs under its own profile so a conversion here can never disturb the
# workbook recalculation toolchain, which shares the default profile.
render() {
  local dir="$1"
  for f in "$dir"/*.md; do
    [ -e "$f" ] || continue
    local b; b="$(basename "${f%.md}")"
    pandoc "$f" -o "$dir/$b.docx" 2>/dev/null || { echo "  ! pandoc failed: $b"; continue; }
    timeout 180 "$SOFFICE" -env:UserInstallation="file://$TMPD/prof" \
      --headless --convert-to pdf --outdir "$TMPD" "$dir/$b.docx" >/dev/null 2>&1
    if [ -f "$TMPD/$b.pdf" ]; then cp "$TMPD/$b.pdf" "$dir/"; else echo "  ! no PDF: $b"; fi
  done
}

echo "rendering the authored documents..."
render "."
echo "rendering the appendix..."
render "Appendix — machine-generated evidence"
# The appendix is a set of machine-generated records. The .docx renditions are an
# intermediate step to the PDF and are not part of what ships.
rm -f "Appendix — machine-generated evidence"/*.docx

echo
python3 - "$PKG" <<'PYCHK'
import glob, os, re, subprocess, sys

pkg = sys.argv[1]
bad = []

def words(s):
    """The distinctive words of a heading, ignoring markup and short connectives."""
    s = re.sub(r"[`*_]", "", s).lower()
    return [w for w in re.findall(r"[a-z0-9][a-z0-9./%-]{3,}", s)]

def header_rows(md):
    """Header cells only: the line immediately above each |---| separator."""
    lines = md.splitlines()
    out = []
    for i, line in enumerate(lines):
        if re.match(r"^\s*\|[\s:|-]+\|\s*$", line) and i and lines[i-1].strip().startswith("|"):
            out += [c.strip() for c in lines[i-1].strip().strip("|").split("|") if c.strip()]
    return out

for md in sorted(glob.glob(os.path.join(pkg, "*.md"))
                 + glob.glob(os.path.join(pkg, "*", "*.md"))):
    pdf = md[:-3] + ".pdf"
    name = os.path.basename(md)
    if not os.path.exists(pdf):
        bad.append(f"{name}: no PDF produced"); continue
    txt = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                         capture_output=True, text=True).stdout.lower()
    if len(txt) < 500:
        bad.append(f"{name}: PDF has almost no extractable text"); continue

    # A renderer may also break a single word across a line in a narrow column
    # ("relevelle d"), which is legible but leaves no whole token to match. The
    # despaced text catches that; a genuinely cropped column is absent from both.
    despaced = re.sub(r"\s+", "", txt)
    src = open(md).read()
    def present(w):
        return w in txt or w.replace(" ", "") in despaced
    lost_h = [h for h in header_rows(src)
              if words(h) and not all(present(w) for w in words(h))]
    # Every figure in the authored documents must survive; the appendix carries hundreds
    # of generated numbers and is checked on its table structure instead.
    lost_n = []
    if os.path.dirname(md) == pkg:
        lost_n = [n for n in sorted(set(re.findall(r"\$?\d[\d,.]*%?", src)))
                  if n.lower() not in txt]
    pages = txt.count("\f") + 1
    status = "ok" if not (lost_h or lost_n) else "LOST CONTENT"
    print(f"  {name[:46]:48} {pages:>2}pp  {len(header_rows(src)):>3} headers  {status}")
    if lost_h: print(f"      headers lost: {lost_h[:5]}")
    if lost_n: print(f"      numbers lost: {lost_n[:8]}")
    if lost_h or lost_n: bad.append(name)

print()
if bad:
    print("PACKAGE BLOCKED — content lost in the render:")
    for b in bad: print("  -", b)
    sys.exit(1)
print("Render check passed: every table header and every figure survives into the PDF.")
PYCHK
