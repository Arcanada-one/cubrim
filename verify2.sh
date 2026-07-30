#!/bin/bash
NEW=/home/dev/cubr-wave3-probes/impl-fh309/code/cubrim-rs/target/release/cubrim
OLD=/home/dev/cubr-cm-poc/code/cubrim-rs/target/release/cubrim
C=/home/dev/cubr-wave3-probes/corpus
W=/home/dev/cubr-wave3-probes/rt2
mkdir -p $W

# 1. x-ray full RT + gain
$NEW compress $C/x-ray $W/xray.new.cbr >/dev/null 2>&1
$NEW decompress $W/xray.new.cbr $W/xray.out >/dev/null 2>&1
cmp -s $C/x-ray $W/xray.out && xrt=OK || xrt=FAIL
xnew=$(wc -c <$W/xray.new.cbr)
xapm=$(od -An -tu1 -j10 -N1 $W/xray.new.cbr | tr -d ' ')  # high byte of width field
echo "x-ray RT=$xrt size=$xnew (shipped 3771607) width_hi_byte=$xapm"

# 2. byte-identity on files that must NOT change (new CLI output == old CLI output)
for f in mr ptt5; do
  $NEW compress $C/$f $W/$f.new.cbr >/dev/null 2>&1
  $OLD compress $C/$f $W/$f.old.cbr >/dev/null 2>&1
  if cmp -s $W/$f.new.cbr $W/$f.old.cbr; then id=IDENTICAL; else id=DIFFERS; fi
  # also RT the new one
  $NEW decompress $W/$f.new.cbr $W/$f.out >/dev/null 2>&1
  cmp -s $C/$f $W/$f.out && rt=OK || rt=FAIL
  echo "$f new-vs-old=$id  RT=$rt  new=$(wc -c <$W/$f.new.cbr) old=$(wc -c <$W/$f.old.cbr)"
done
echo VERIFY2_DONE
