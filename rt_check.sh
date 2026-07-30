#!/bin/bash
CLI=/home/dev/cubr-wave3-probes/impl-fh309/code/cubrim-rs/target/release/cubrim
OLD=/home/dev/cubr-cm-poc/code/cubrim-rs/target/release/cubrim
C=/home/dev/cubr-wave3-probes/corpus
W=/home/dev/cubr-wave3-probes/rt
mkdir -p $W
for f in x-ray mr; do
  $CLI compress $C/$f $W/$f.cbr >/dev/null 2>&1; rc1=$?
  $CLI decompress $W/$f.cbr $W/$f.out >/dev/null 2>&1; rc2=$?
  cmp -s $C/$f $W/$f.out; cmpr=$?
  new=$(wc -c < $W/$f.cbr)
  # baseline old CLI size
  $OLD compress $C/$f $W/$f.old.cbr >/dev/null 2>&1
  old=$(wc -c < $W/$f.old.cbr)
  mode=$(od -An -tu1 -j5 -N1 $W/$f.cbr | tr -d ' ')
  apm=$(od -An -tu1 -j13 -N1 $W/$f.cbr | tr -d ' ')
  delta=$(awk "BEGIN{printf \"%.4f\", ($new-$old)/$old*100}")
  echo "$f: enc_rc=$rc1 dec_rc=$rc2 cmp=$cmpr mode=$mode apm=$apm  new=$new old=$old  delta=${delta}%"
done
echo ALL_RT_DONE
