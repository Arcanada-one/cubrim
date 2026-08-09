#!/usr/bin/env bash
# Preregistered, single-use eight-cell zero-representation matrix runner.
set -euo pipefail

readonly CARGO=/root/.cargo/bin/cargo
readonly CARGO_PROGRAM=${CARGO##*/}
[[ -x "$CARGO" ]] || { printf 'CARGO not executable: %s\n' "$CARGO" >&2; exit 1; }
CARGO_VERSION=$("$CARGO" --version) || { printf 'CARGO version check failed: %s\n' "$CARGO" >&2; exit 1; }
readonly CARGO_VERSION_PREFIX="$CARGO_PROGRAM 1.96.1"
readonly PROGRAM_IDENTIFIER_LINES_SHA256=105222ab0ab9a0dac70385b83175d5416926a214fc28d8fa11fcd64bd1cedd31
if [[ $CARGO_VERSION != "$CARGO_VERSION_PREFIX" && $CARGO_VERSION != "$CARGO_VERSION_PREFIX "* ]]; then
 printf 'wrong CARGO version: %s\n' "$CARGO_VERSION" >&2
 exit 1
fi
readonly CARGO_VERSION

OUT=/root/cubr-levers/zerorep-matrix-g3-20260809
INPUT=/root/cubr-levers/bench
CANON=/root/cubr-levers/preset-rss
BASE_ROOT=/root/cubr-levers/zerorep-baseline-e70
CURRENT_ROOT=/root/cubr-levers/zerorep-current-49e
ZERO_ROOT=/root/cubr-levers/zerorep-matrix-g3-code
BASE="$BASE_ROOT/code/cubrim-rs/target/release/cubrim"
CURRENT="$CURRENT_ROOT/code/cubrim-rs/target/release/cubrim"
ZERO="$ZERO_ROOT/code/cubrim-rs/target/release/cubrim"
PIN=0-15
RUNNER_REL=documentation/ephemeral/research/CUBR-ZEROREP-MATRIX-G3-20260809/zerorep-matrix-g3-run.sh
EVIDENCE_REL=documentation/ephemeral/research/CUBR-ZEROREP-20260808/tdd-local-gates.md

BASE_SOURCE=e70d1cdca6226e994c0393149e364f252f7c0a1f
CURRENT_SOURCE=49e429e58722f730c4f3cbb0a69731fec430bb56
ZERO_ANCHOR=189a09308d38805f67c6263f5cc98793fb485e27
BASE_SHA=a195c2271a8aafbe9363d89d4047db4554e0e8840869997072d0c011086a7fbd
CURRENT_SHA=12eaff4d9df9e3b8f51567cd930311f343680b5cc55e3426f30a78456fc5830c
ZERO_SHA=771fdb0f091df2e419d66ae9b28169a2dc69f1d57cab62d948a9ef716dac6e20
ZERO_CM2_SHA=1594578cc98f4ef55ae102cbe31fc5cdde02d6c647941787cc009464abe8addf
EVIDENCE_SHA=358b057f3991ddc0ea97944d5e5854fb5b64a325800c33890ce2534b89807cfb
readonly G1_OUT=/root/cubr-levers/zerorep-matrix-20260809
readonly G1_EMPTY_DIR=timing_logs
readonly -a G1_MANIFEST=(
 'b6b96126eefa1a9b00581b1c7f2439ca5c605e1b8b4dceb14d4757a28c9fefbf HASHES.tsv'
 "012a973200c31c92f5447961e7915735a7ae0311f628d9f7a89c375fcc998615 ${CARGO_PROGRAM}-test-release.log"
 '7ffd8ea16586b73ca67e645fb79d68e6b83dd647b2068bdeb256e4708e4ae2d4 journal.log'
 '544748ffc2ffbcd9218ff43f09b7292811d6ab00e1fad789105adfc5d31fd19f results.tsv'
 '7ae44fbaaaf4cf26cc68d1643cc49da562434914dbade295605aaf5972944cdf roundtrips.tsv'
)

# G3-BEGIN preservation-and-side-effect-contract
readonly G2_OUT=/root/cubr-levers/zerorep-matrix-g2-20260809
readonly G2_EMPTY_DIR=timing_logs
readonly -a G2_MANIFEST=(
 'd32843c23b9540f01fc512b7e59dfd0d50ee7a4fdb9b90f0c85a81db590cea04 HASHES.tsv'
 "113976d8d42347ef3fb5d64c103dcf9c080fea8cbce4e97363e4caf4958b39a6 ${CARGO##*/}-test-release.log"
 "630ac2f25e566bcb876f45a3d5d7c012c7bac5b273cd1d99ffc714ac7014bbc4 ${CARGO##*/}-test-scheme-roundtrip.log"
 '365837f292ec206257ecb1e1d98ff9a54efe8d43c3dfb3d86465d446524e9b7b journal.log'
 '544748ffc2ffbcd9218ff43f09b7292811d6ab00e1fad789105adfc5d31fd19f results.tsv'
 '7ae44fbaaaf4cf26cc68d1643cc49da562434914dbade295605aaf5972944cdf roundtrips.tsv'
)
readonly SIDE_EFFECT_28=documentation/ephemeral/research/CUBR-0028-bench.json
readonly SIDE_EFFECT_31=documentation/ephemeral/research/CUBR-0031-bench.json
readonly SIDE_EFFECT_28_HEAD_SHA=5d1313d8b3537ed276280ac587b3c94d181965fd35b60ac30b82c782e6b4ee1f
readonly SIDE_EFFECT_31_HEAD_SHA=98bc95cf2bf500c50f6f34887d4b02d078852795162f5ad884a3b7ab239e6c0b
readonly -a SIDE_EFFECT_SPECS=(
 "$SIDE_EFFECT_28_HEAD_SHA $SIDE_EFFECT_28"
 "$SIDE_EFFECT_31_HEAD_SHA $SIDE_EFFECT_31"
)
readonly POST_RESTORE_GATE_LINES_SHA256=846b30635c2fc2ef20f5ef5e0b21b485ae062fd9b8b34d8feef20347f8c8778a
readonly CLEAN_BLOCK_SHA256=5b1286bf098d721759604104f3be900b17a23694f1932c1ff298779ee9f3a61a
readonly HELPERS_BLOCK_SHA256=d7da850d7392b4c6db19039545e7685455f5a69ec22bfddb9ca325229f8cfe6e
readonly LIVE_BLOCK_SHA256=390d66a0f5f189c70ff0231c0493a22a4d9084da2361d11f29138646fbdddc7c
# G3-END preservation-and-side-effect-contract

export CUBR_THREADS=4 RAYON_NUM_THREADS=4 OMP_NUM_THREADS=4 CUBRIM_ACCEPT_LICENSE=1

# file preset canonical-bytes canonical-sha accounting-E-MiB accounting-T-MiB
CELLS=(
 'nci balanced 108014 c812943fd63414bf4ec185ee048b6550cc6b1a0a523dd3a63afe242bdf133066 736 1472'
 'nci web 108624 2caaa78101082ccfb753909440a60e7381f94210fd8817ac89ccc02d7b6d6848 46 92'
 'dickens max 461437 c8aed8ae4c39d8a463e3d2bcb3fd082ec955d60fd320bbeec41af7a65922285e 768 1536'
 'dickens balanced 472253 25378abf1cbe18e016143c0f0401aac055db8fb1c2964e5a4525371ba400a5ad 736 1472'
 'dickens web 487506 0f3677eeadf937facb8c3b3fd79d6fc04677f19e0b648b983dd732db8a92ba0f 46 92'
 'ooffice max 677605 4d563b48ae509f11b65b0c71929e0b0375b2322b26aefc489b36aefeeacd60be 736 1472'
 'ooffice balanced 677605 4d563b48ae509f11b65b0c71929e0b0375b2322b26aefc489b36aefeeacd60be 736 1472'
 'ooffice web 704087 a8e04efd9c890c8f72a645571ebfd230774e638e9bef7c3118d22a5fffeb0be4 46 92'
)
declare -A INPUT_SHA=(
 [nci]=6788fcc1527c0f62709103e68ac9ab9416461ab00ed1f529b3cf2ae4ab06221e
 [dickens]=df925056e0779c51cb2a27c014e8fc6d25d28ef2fac5b8ce4632d93b86860603
 [ooffice]=5041e86f07bf17d7a8b3b0ab496a1b6413256399848709f8be543bbdca12de09
)

LOG=/dev/stderr
journal() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >>"$LOG"; }
die() { journal "FAIL: $*"; exit 1; }
sha() { sha256sum "$1" | awk '{print $1}'; }
need_sha() { [[ -f $1 && $(sha "$1") == "$2" ]] || die "sha256 mismatch: $1"; }
# G3-FROZEN-BEGIN inherited-clean
clean() {
 local checkout=$1 status
 if ! status=$(git -C "$checkout" status --porcelain); then die "git status failed: $checkout"; fi
 [[ -z $status ]] || die "dirty checkout: $checkout"
}
# G3-FROZEN-END inherited-clean
suite_contract_lines() {
 local dollar='$' double_quote='"' quote="'" command_ref prefix release_tail scheme_tail
 command_ref="${double_quote}${dollar}CARGO${double_quote}"
 prefix="( cd ${double_quote}${dollar}ZERO_ROOT/code/cubrim-rs${double_quote} && "
 release_tail=" test --release ) >\"\$OUT/\${CARGO_PROGRAM}-test-release.log\" 2>&1 || die ${quote}Cargo test --release${quote}"
 scheme_tail=" test --release --test scheme_roundtrip ) >\"\$OUT/\${CARGO_PROGRAM}-test-scheme-roundtrip.log\" 2>&1 || die ${quote}scheme roundtrip test${quote}"
 printf '%s\n' "$prefix$command_ref$release_tail" "$prefix$command_ref$scheme_tail"
}
suite_lines_exact_once() {
 local source=$1 expected line_count
 local -a suite_lines
 mapfile -t suite_lines < <(suite_contract_lines)
 [[ ${#suite_lines[@]} == 2 ]] || return 1
 for expected in "${suite_lines[@]}"; do
  line_count=$(awk -v expected="$expected" '$0 == expected { count++ } END { print count + 0 }' "$source") || return 1
  [[ $line_count == 1 ]] || return 1
 done
}
program_command_refs_absent() {
 local source=$1 identifier='CARGO_' prefix reference suffix pattern status
 identifier+='PROGRAM'
 prefix='(^[[:space:]]*|(^|[;&|()])[[:space:]]*|(^|[[:space:]])(if|then|elif|while|until|do|!|time|command)[[:space:]]+|(^|[[:space:]])env([[:space:]]+[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]+)*[[:space:]]+)'
 reference="\"?\\\$(\\{${identifier}\\}|${identifier})\"?"
 suffix='([[:space:];&|()]|$)'
 pattern="${prefix}${reference}${suffix}"
 if grep -nE "$pattern" "$source" >/dev/null; then return 1; else status=$?; fi
 [[ $status == 1 ]]
}
identifier_lines_digest() {
 local source=$1 identifier='CARGO_'
 identifier+='PROGRAM'
 LC_ALL=C awk -v identifier="$identifier" 'index($0, identifier) { print }' "$source" | sha256sum | awk '{print $1}'
}
identifier_lines_allowed() {
 local digest
 digest=$(identifier_lines_digest "$1") || return 1
 [[ $digest == "$PROGRAM_IDENTIFIER_LINES_SHA256" ]]
}
source_contract() {
 local source=$1 count identifier='CARGO_' identifier_count
 identifier+='PROGRAM'
 count=$(grep -oF "$CARGO_PROGRAM" "$source" | wc -l) || return 1
 [[ $count == 2 ]] || return 1
 grep -Fxq "readonly CARGO=/root/.$CARGO_PROGRAM/bin/$CARGO_PROGRAM" "$source" || return 1
 identifier_count=$(grep -oF "$identifier" "$source" | wc -l) || return 1
 [[ $identifier_count == 15 ]] || return 1
 identifier_lines_allowed "$source" || return 1
 program_command_refs_absent "$source" || return 1
 # G3-BEGIN source-contract-extension
 frozen_blocks_allowed "$source" || return 1
 post_restore_gate_allowed "$source" || return 1
 # G3-END source-contract-extension
 suite_lines_exact_once "$source"
}
mutate_exact_line() {
 local source=$1 expected=$2 replacement=$3 output=$4
 awk -v expected="$expected" -v replacement="$replacement" '
  $0 == expected { print replacement; count++; next }
  { print }
  END { if (count != 1) exit 1 }
 ' "$source" >"$output"
}
verify_exact_manifest() (
 local root=$1 empty_dir=$2 spec expected name extra path actual first_entry
 shift 2
 local -a entries
 shopt -s dotglob nullglob
 entries=("$root"/*)
 [[ -d $root && ! -L $root && -r $root && -x $root && ${#entries[@]} -eq $(($# + 1)) ]] || return 1
 path="$root/$empty_dir"
 [[ -d $path && ! -L $path && -r $path && -x $path ]] || return 1
 first_entry=$(find "$path" -mindepth 1 -maxdepth 1 -print -quit) || return 1
 [[ -z $first_entry ]] || return 1
 for spec in "$@"; do
  read -r expected name extra <<<"$spec"
  [[ -n $expected && -n $name && -z $extra ]] || return 1
  path="$root/$name"
  [[ -f $path && ! -L $path ]] || return 1
  actual=$(sha "$path") || return 1
  [[ $actual == "$expected" ]] || return 1
 done
)
verify_g1_manifest() { verify_exact_manifest "$G1_OUT" "$G1_EMPTY_DIR" "${G1_MANIFEST[@]}"; }
# G3-BEGIN preservation-and-side-effect-functions
verify_g2_manifest() { verify_exact_manifest "$G2_OUT" "$G2_EMPTY_DIR" "${G2_MANIFEST[@]}"; }
marker_block_digest() {
 local source=$1 begin=$2 end=$3
 LC_ALL=C awk -v begin="$begin" -v end="$end" '
  $0 == begin { begin_count++; if (!begin_line) begin_line=NR }
  $0 == end { end_count++; if (!end_line) end_line=NR }
  { lines[NR]=$0 }
  END {
   if (begin_count != 1 || end_count != 1 || begin_line >= end_line) exit 1
   for (line=begin_line; line<=end_line; line++) print lines[line]
  }
 ' "$source" | sha256sum | awk '{print $1}'
}
frozen_blocks_allowed() {
 local source=$1 prefix='# G3-FROZEN-' clean_begin clean_end helper_begin helper_end live_begin live_end digest
 clean_begin="${prefix}BEGIN inherited-clean"; clean_end="${prefix}END inherited-clean"
 helper_begin='# G3-BEGIN '; helper_begin+='preservation-and-side-effect-functions'
 helper_end='# G3-END '; helper_end+='preservation-and-side-effect-functions'
 live_begin="${prefix}BEGIN live-restore-clean-rehash"; live_end="${prefix}END live-restore-clean-rehash"
 digest=$(marker_block_digest "$source" "$clean_begin" "$clean_end") || return 1
 [[ $digest == "$CLEAN_BLOCK_SHA256" ]] || return 1
 digest=$(marker_block_digest "$source" "$helper_begin" "$helper_end") || return 1
 [[ $digest == "$HELPERS_BLOCK_SHA256" ]] || return 1
 digest=$(marker_block_digest "$source" "$live_begin" "$live_end") || return 1
 [[ $digest == "$LIVE_BLOCK_SHA256" ]]
}
repo_status() { git -C "$1" status --porcelain; }
head_blob_sha() { git -C "$1" show "HEAD:$2" | sha256sum | awk '{print $1}'; }
worktree_file_sha() {
 local root=$1 path=$2
 [[ -f $root/$path && ! -L $root/$path ]] || return 1
 sha "$root/$path"
}
verify_head_side_effects() {
 local root=$1 spec expected path extra actual
 shift
 for spec in "$@"; do
  read -r expected path extra <<<"$spec"
  [[ -n $expected && -n $path && -z $extra ]] || return 1
  actual=$(head_blob_sha "$root" "$path") || return 1
  [[ $actual == "$expected" ]] || return 1
 done
}
classify_side_effect_status() {
 local status=$1 spec expected_hash path extra line seen_count=0
 shift
 [[ $# == 2 ]] || return 1
 local -A expected_lines=()
 for spec in "$@"; do
  read -r expected_hash path extra <<<"$spec"
  [[ -n $expected_hash && -n $path && -z $extra ]] || return 1
  line=" M $path"
  [[ ! -v expected_lines["$line"] ]] || return 1
  expected_lines["$line"]=0
 done
 while IFS= read -r line; do
  [[ -n $line ]] || continue
  [[ -v expected_lines["$line"] && ${expected_lines["$line"]} == 0 ]] || return 1
  expected_lines["$line"]=1
  seen_count=$((seen_count + 1))
 done <<<"$status"
 [[ $seen_count == 2 ]] || return 1
 for line in "${!expected_lines[@]}"; do [[ ${expected_lines["$line"]} == 1 ]] || return 1; done
}
head_blob_to_temp() { git -C "$1" show "HEAD:$2" >"$3"; }
atomic_install() { mv -- "$1" "$2"; }
restore_one_head_blob() {
 local root=$1 spec=$2 expected path extra destination temporary actual mode
 read -r expected path extra <<<"$spec"
 [[ -n $expected && -n $path && -z $extra ]] || return 1
 destination="$root/$path"; temporary="$destination.g3restore-tmp"
 [[ -f $destination && ! -L $destination && ! -e $temporary && ! -L $temporary ]] || return 1
 if ! head_blob_to_temp "$root" "$path" "$temporary"; then rm -f -- "$temporary"; return 1; fi
 if ! chmod 0644 "$temporary"; then rm -f -- "$temporary"; return 1; fi
 mode=$(stat -c %a "$temporary") || { rm -f -- "$temporary"; return 1; }
 [[ $mode == 644 ]] || { rm -f -- "$temporary"; return 1; }
 actual=$(sha "$temporary") || { rm -f -- "$temporary"; return 1; }
 [[ $actual == "$expected" ]] || { rm -f -- "$temporary"; return 1; }
 if ! atomic_install "$temporary" "$destination"; then rm -f -- "$temporary"; return 1; fi
 [[ ! -e $temporary && ! -L $temporary ]] || { rm -f -- "$temporary"; return 1; }
 actual=$(worktree_file_sha "$root" "$path") || return 1
 [[ $actual == "$expected" && $(stat -c %a "$destination") == 644 ]]
}
after_restore_hook() { :; }
post_restore_clean_gate() {
 local root=$1 status
 if ! status=$(repo_status "$root"); then return 1; fi
 [[ -z $status ]]
}
post_restore_hashes_match() {
 local root=$1 spec expected path extra actual
 shift
 for spec in "$@"; do
  read -r expected path extra <<<"$spec"
  [[ -n $expected && -n $path && -z $extra ]] || return 1
  actual=$(worktree_file_sha "$root" "$path") || return 1
  [[ $actual == "$expected" ]] || return 1
 done
}
restore_suite_side_effects() {
 local root=$1 log=$2 status spec expected path extra prehash28 prehash31 posthash28 posthash31
 shift 2
 [[ $# == 2 ]] || return 1
 if ! status=$(repo_status "$root"); then return 1; fi
 classify_side_effect_status "$status" "$@" || return 1
 read -r expected path extra <<<"$1"; prehash28=$(worktree_file_sha "$root" "$path") || return 1
 read -r expected path extra <<<"$2"; prehash31=$(worktree_file_sha "$root" "$path") || return 1
 for spec in "$@"; do restore_one_head_blob "$root" "$spec" || return 1; done
 after_restore_hook "$root" || return 1
 post_restore_clean_gate "$root" || return 1
 post_restore_hashes_match "$root" "$@" || return 1
 read -r expected path extra <<<"$1"; posthash28=$(worktree_file_sha "$root" "$path") || return 1
 read -r expected path extra <<<"$2"; posthash31=$(worktree_file_sha "$root" "$path") || return 1
 printf 'prehash28=%s prehash31=%s post_status_rc=0 posthash28=%s posthash31=%s\n' "$prehash28" "$prehash31" "$posthash28" "$posthash31" >"$log"
 [[ $(wc -l <"$log") == 1 ]]
}
post_restore_gate_digest() {
 local source=$1 marker='post_restore_'
 marker+='clean_gate'
 LC_ALL=C awk -v marker="$marker" 'index($0, marker) { print NR ":" $0 }' "$source" | sha256sum | awk '{print $1}'
}
post_restore_gate_allowed() {
 local digest
 digest=$(post_restore_gate_digest "$1") || return 1
 [[ $digest == "$POST_RESTORE_GATE_LINES_SHA256" ]]
}
# G3-END preservation-and-side-effect-functions
bin_for() { case "$1" in base) printf %s "$BASE";; current) printf %s "$CURRENT";; zero) printf %s "$ZERO";; *) die "invalid build: $1";; esac; }
input_for() { printf '%s/%s.2m' "$INPUT" "$1"; }
canon_for() { printf '%s/%s.%s.base.cbr' "$CANON" "$1" "$2"; }
sample_order() { case "$1" in 1) printf '%s\n' base current zero;; 2) printf '%s\n' current zero base;; 3) printf '%s\n' zero base current;; *) return 1;; esac; }
load_below_limit() {
 python3 - "$1" <<'PY'
import math,sys
try: value=float(sys.argv[1])
except ValueError: raise SystemExit(1)
raise SystemExit(0 if math.isfinite(value) and value < 2.0 else 1)
PY
}
detect_cubrim_processes() {
 awk -v self="$$" -v parent="$PPID" '
 $1 == self || $1 == parent { next }
 $2 == "cubrim" || $2 ~ /^cubrim-/ { print; found=1; next }
 { for (i=3; i<=NF; i++) if ($i ~ /\/cubrim(-[^\/]*)?$/) { print; found=1; next } }
 END { exit(found ? 1 : 0) }
 '
}
stabilization_step() {
 local load=$1 competitors=$2 consecutive=$3
 [[ $competitors == 0 ]] || return 2
 if load_below_limit "$load"; then printf '%s\n' "$((consecutive + 1))"; else printf '0\n'; fi
}
stabilization_sleep_seconds() {
 local elapsed=$1 remaining
 [[ $elapsed =~ ^[0-9]+$ && $elapsed -lt 180 ]] || return 1
 remaining=$((180 - elapsed)); (( remaining < 15 )) && printf '%s\n' "$remaining" || printf '15\n'
}
wall_rss() {
 python3 - "$1" <<'PY'
import re, sys
s=open(sys.argv[1], encoding='utf-8').read()
w=re.search(r'^\s*Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):\s*([0-9]+:[0-5][0-9](?:\.[0-9]+)?|[0-9]+:[0-5][0-9]:[0-5][0-9](?:\.[0-9]+)?)\s*$',s,re.M); r=re.search(r'^\s*Maximum resident set size \(kbytes\):\s*(\d+)\s*$',s,re.M)
if not w or not r: raise SystemExit('missing GNU time fields')
p=[float(x) for x in w.group(1).strip().split(':')]
if len(p) not in (2,3): raise SystemExit('invalid elapsed value')
v=p[-1]+(p[-2]*60 if len(p)>1 else 0)+(p[-3]*3600 if len(p)>2 else 0)
print(f'{v:.6f}\t{r.group(1)}')
PY
}
parse_verdicts() {
 python3 - "$@" <<'PY'
import csv,json,statistics,sys
results,roundtrips,out_json,out_tsv=sys.argv[1:]
cells=[('nci','balanced',736,1472),('nci','web',46,92),('dickens','max',768,1536),('dickens','balanced',736,1472),('dickens','web',46,92),('ooffice','max',736,1472),('ooffice','balanced',736,1472),('ooffice','web',46,92)]
orders={1:('base','current','zero'),2:('current','zero','base'),3:('zero','base','current')}
expected=[]
for f,p,_,_ in cells:
 cell=f'{f}/{p}'; expected += [(cell,'warmup','1',b) for b in ('base','current','zero')]
 expected += [(cell,'timed',str(n),b) for n in range(1,4) for b in orders[n]]
with open(roundtrips,newline='',encoding='utf8') as h: rows=list(csv.DictReader(h,delimiter='\t'))
seen=[(r.get('cell'),r.get('phase'),r.get('sample'),r.get('build')) for r in rows]
if len(rows)!=96 or len(set(seen))!=96 or seen!=expected or any(r.get('cmp')!='PASS' for r in rows): raise SystemExit('invalid roundtrip schedule')
with open(results,newline='',encoding='utf8') as h: rr=list(csv.DictReader(h,delimiter='\t'))
exp_results=[(f'{f}/{p}','timed',str(n),b) for f,p,_,_ in cells for n in range(1,4) for b in orders[n]]
keys=[(r.get('cell'),r.get('step'),r.get('sample'),r.get('build')) for r in rr]
if len(rr)!=72 or len(set(keys))!=72 or keys!=exp_results: raise SystemExit('invalid timed schedule')
data={}
for f,p,e,t in cells:
 cell=f'{f}/{p}'; g={b:[] for b in ('base','current','zero')}
 for r in rr:
  if r['cell']==cell:
   if r['wall_s']=='' or r['peak_rss_kib']=='': raise SystemExit('missing measurement')
   g[r['build']].append((float(r['wall_s']),int(r['peak_rss_kib'])))
 if any(len(g[b])!=3 for b in g): raise SystemExit('missing build samples')
 m={b:(statistics.median(x[0] for x in g[b]),statistics.median(x[1] for x in g[b])) for b in g}
 P=m['current'][1]-m['base'][1]; R=m['current'][1]-m['zero'][1]; B=m['base'][1]-m['zero'][1]
 reclaim_fraction=R/P if P>0 else None; residual=m['zero'][1]-m['base'][1]
 zero_current_ratio=m['zero'][0]/m['current'][0]; base_zero_speedup=m['base'][0]/m['zero'][0]
 c_positive=P>0; c_reclaim=reclaim_fraction is not None and reclaim_fraction>=.75; c_residual=residual<=65536; c_zero_current=zero_current_ratio<=1.05; c_base_zero=base_zero_speedup>=1.10
 product=c_positive and c_reclaim and c_residual and c_zero_current and c_base_zero
 accounting=R<=t*1024 and (B<=0 or B<=e*1024)
 data[cell]={'medians':{b:{'wall_s':m[b][0],'peak_rss_kib':m[b][1]} for b in m},'P_kib':P,'R_kib':R,'B_kib':B,'reclaim_fraction':reclaim_fraction,'residual_kib':residual,'zero_current_time_ratio':zero_current_ratio,'base_zero_speedup':base_zero_speedup,'conditions':{'positive_P':c_positive,'reclaim_fraction_at_least_075':c_reclaim,'residual_at_most_65536_kib':c_residual,'zero_current_time_ratio_at_most_1_05':c_zero_current,'base_zero_speedup_at_least_1_10':c_base_zero},'E_ceiling_kib':e*1024,'T_ceiling_kib':t*1024,'R_fraction_of_T':R/(t*1024),'B_fraction_of_E':None if B<=0 else B/(e*1024),'accounting_values':{'R_at_most_T':R<=t*1024,'B_nonpositive_or_at_most_E':B<=0 or B<=e*1024},'verdict':'PASS' if product else 'REFUTED','accounting':'ACCOUNTING_CONSISTENT' if accounting else 'EXPLANATION_INCOMPLETE'}
with open(out_json,'w',encoding='utf8') as h: json.dump(data,h,indent=2,sort_keys=True); h.write('\n')
with open(out_tsv,'w',newline='',encoding='utf8') as h:
 w=csv.writer(h,delimiter='\t',lineterminator='\n'); w.writerow(['cell','base_wall_s','current_wall_s','zero_wall_s','base_rss_kib','current_rss_kib','zero_rss_kib','P_kib','R_kib','B_kib','reclaim_fraction','residual_kib','zero_current_time_ratio','base_zero_speedup','positive_P','reclaim_ge_075','residual_le_65536','zero_current_le_1_05','base_zero_ge_1_10','E_ceiling_kib','T_ceiling_kib','R_fraction_of_T','B_fraction_of_E','verdict','accounting'])
 for c,d in data.items():
  m=d['medians'];q=d['conditions'];w.writerow([c,m['base']['wall_s'],m['current']['wall_s'],m['zero']['wall_s'],m['base']['peak_rss_kib'],m['current']['peak_rss_kib'],m['zero']['peak_rss_kib'],d['P_kib'],d['R_kib'],d['B_kib'],d['reclaim_fraction'],d['residual_kib'],d['zero_current_time_ratio'],d['base_zero_speedup'],q['positive_P'],q['reclaim_fraction_at_least_075'],q['residual_at_most_65536_kib'],q['zero_current_time_ratio_at_most_1_05'],q['base_zero_speedup_at_least_1_10'],d['E_ceiling_kib'],d['T_ceiling_kib'],d['R_fraction_of_T'],d['B_fraction_of_E'],d['verdict'],d['accounting']])
PY
}
# G3-BEGIN isolated-side-effect-self-test
g3_dirty_side_effects() {
 local root=$1
 printf 'suite mutation 28\n' >>"$root/$SIDE_EFFECT_28"
 printf 'suite mutation 31\n' >>"$root/$SIDE_EFFECT_31"
}
g3_clone_dirty_repo() {
 local template=$1 clone=$2
 git clone -q "$template" "$clone" || return 1
 g3_dirty_side_effects "$clone"
}
g3_self_test() {
 local d=$1 template="$1/g3-template" repo status log hash28 hash31 expected_log mutation_source mutation_source2 gate_name live_gate_call
 local clean_line clean_mutant post_line post_mutant marker_prefix clean_begin clean_end dollar='$'
 local spec28 spec31
 local -a specs
 mkdir -p "$template/$(dirname "$SIDE_EFFECT_28")" || return 1
 git -C "$template" init -q || return 1
 git -C "$template" config user.name 'G3 Self Test' || return 1
 git -C "$template" config user.email 'g3-self-test@example.invalid' || return 1
 printf 'committed 28\n' >"$template/$SIDE_EFFECT_28"
 printf 'committed 31\n' >"$template/$SIDE_EFFECT_31"
 git -C "$template" add "$SIDE_EFFECT_28" "$SIDE_EFFECT_31" || return 1
 git -C "$template" commit -qm seed || return 1
 hash28=$(worktree_file_sha "$template" "$SIDE_EFFECT_28") || return 1
 hash31=$(worktree_file_sha "$template" "$SIDE_EFFECT_31") || return 1
 spec28="$hash28 $SIDE_EFFECT_28"; spec31="$hash31 $SIDE_EFFECT_31"; specs=("$spec28" "$spec31")
 verify_head_side_effects "$template" "${specs[@]}" || return 1
 ! verify_head_side_effects "$template" "0$hash28 $SIDE_EFFECT_28" "$spec31" || return 1

 status=$(printf ' M %s\n M %s\n' "$SIDE_EFFECT_31" "$SIDE_EFFECT_28")
 classify_side_effect_status "$status" "${specs[@]}" || return 1
 ! classify_side_effect_status " M $SIDE_EFFECT_28" "${specs[@]}" || return 1
 ! classify_side_effect_status " M $SIDE_EFFECT_31" "${specs[@]}" || return 1
 ! classify_side_effect_status "$(printf '%s\n M %s\n' "$status" "$SIDE_EFFECT_28")" "${specs[@]}" || return 1
 ! classify_side_effect_status "$(printf ' M %s\n M %s\n' "$SIDE_EFFECT_28" documentation/ephemeral/research/unexpected.json)" "${specs[@]}" || return 1
 ! classify_side_effect_status "$(printf 'M  %s\n M %s\n' "$SIDE_EFFECT_28" "$SIDE_EFFECT_31")" "${specs[@]}" || return 1
 ! classify_side_effect_status "$(printf '?? %s\n M %s\n' "$SIDE_EFFECT_28" "$SIDE_EFFECT_31")" "${specs[@]}" || return 1
 ! classify_side_effect_status "$(printf 'R  old.json -> %s\n M %s\n' "$SIDE_EFFECT_28" "$SIDE_EFFECT_31")" "${specs[@]}" || return 1

 repo="$d/g3-positive"; g3_clone_dirty_repo "$template" "$repo" || return 1
 local observed28 observed31
 observed28=$(worktree_file_sha "$repo" "$SIDE_EFFECT_28") || return 1
 observed31=$(worktree_file_sha "$repo" "$SIDE_EFFECT_31") || return 1
 log="$d/positive-side-effect-restore.log"
 restore_suite_side_effects "$repo" "$log" "${specs[@]}" || return 1
 clean "$repo"
 [[ $(worktree_file_sha "$repo" "$SIDE_EFFECT_28") == "$hash28" && $(worktree_file_sha "$repo" "$SIDE_EFFECT_31") == "$hash31" ]] || return 1
 [[ $(stat -c %a "$repo/$SIDE_EFFECT_28") == 644 && $(stat -c %a "$repo/$SIDE_EFFECT_31") == 644 ]] || return 1
 [[ ! -e $repo/$SIDE_EFFECT_28.g3restore-tmp && ! -L $repo/$SIDE_EFFECT_28.g3restore-tmp ]] || return 1
 [[ ! -e $repo/$SIDE_EFFECT_31.g3restore-tmp && ! -L $repo/$SIDE_EFFECT_31.g3restore-tmp ]] || return 1
 expected_log="prehash28=$observed28 prehash31=$observed31 post_status_rc=0 posthash28=$hash28 posthash31=$hash31"
 [[ $(wc -l <"$log") == 1 && $(<"$log") == "$expected_log" ]] || return 1

 repo="$d/g3-show-failure"; g3_clone_dirty_repo "$template" "$repo" || return 1
 if ( head_blob_to_temp() { return 1; }; restore_suite_side_effects "$repo" "$d/show.log" "${specs[@]}" ) >/dev/null 2>&1; then return 1; fi
 repo="$d/g3-mv-removed"; g3_clone_dirty_repo "$template" "$repo" || return 1
 cp "$repo/$SIDE_EFFECT_28" "$d/mv-modified.saved" || return 1
 if ( atomic_install() { :; }; restore_suite_side_effects "$repo" "$d/mv.log" "${specs[@]}" ) >/dev/null 2>&1; then return 1; fi
 cmp -s "$repo/$SIDE_EFFECT_28" "$d/mv-modified.saved" || return 1
 repo="$d/g3-dirty-after"; g3_clone_dirty_repo "$template" "$repo" || return 1
 if ( after_restore_hook() { printf 'stray\n' >"$1/g3-stray"; }; restore_suite_side_effects "$repo" "$d/dirty.log" "${specs[@]}" ) >/dev/null 2>&1; then return 1; fi
 gate_name='post_restore_'; gate_name+='clean_gate'
 repo="$d/g3-posthash"; g3_clone_dirty_repo "$template" "$repo" || return 1
 if ( eval "$gate_name() { :; }"; after_restore_hook() { printf 'corrupt\n' >>"$1/$SIDE_EFFECT_28"; }; restore_suite_side_effects "$repo" "$d/posthash.log" "${specs[@]}" ) >/dev/null 2>&1; then return 1; fi
 repo="$d/g3-status-failure"; g3_clone_dirty_repo "$template" "$repo" || return 1
 if ( repo_status() { if git -C "$1" diff --quiet; then return 1; fi; git -C "$1" status --porcelain; }; restore_suite_side_effects "$repo" "$d/status.log" "${specs[@]}" ) >/dev/null 2>&1; then return 1; fi
 repo="$d/g3-temp-present"; g3_clone_dirty_repo "$template" "$repo" || return 1
 printf 'unexpected temp\n' >"$repo/$SIDE_EFFECT_28.g3restore-tmp"
 ! restore_one_head_blob "$repo" "$spec28" || return 1

 live_gate_call=" ${gate_name} \"\$root\" || return 1"
 mutation_source="$d/post-restore-gate-bypass.sh"
 mutate_exact_line "${BASH_SOURCE[0]}" "$live_gate_call" ' :' "$mutation_source" || return 1
 printf '\nif false; then\n%s\nfi\n' "$live_gate_call" >>"$mutation_source"
 [[ $(awk -v expected="$live_gate_call" '$0 == expected { count++ } END { print count + 0 }' "$mutation_source") == 1 ]] || return 1
 suite_lines_exact_once "$mutation_source" || return 1
 identifier_lines_allowed "$mutation_source" || return 1
 ! source_contract "$mutation_source" || return 1

 clean_line=" [[ -z ${dollar}status ]] || die \"dirty checkout: ${dollar}checkout\""
 clean_mutant=" [[ -z ${dollar}status || ${dollar}checkout == \"${dollar}ZERO_ROOT\" ]] || die \"dirty checkout: ${dollar}checkout\""
 mutation_source="$d/live-root-clean-bypass.sh"
 mutate_exact_line "${BASH_SOURCE[0]}" "$clean_line" "$clean_mutant" "$mutation_source" || return 1
 ! source_contract "$mutation_source" || return 1
 post_line=" [[ -z ${dollar}status ]]"
 post_mutant=" [[ -z ${dollar}status || ${dollar}root == \"${dollar}ZERO_ROOT\" ]]"
 mutation_source="$d/live-root-post-restore-bypass.sh"
 mutate_exact_line "${BASH_SOURCE[0]}" "$post_line" "$post_mutant" "$mutation_source" || return 1
 ! source_contract "$mutation_source" || return 1

 marker_prefix='# G3-FROZEN-'; clean_begin="${marker_prefix}BEGIN inherited-clean"; clean_end="${marker_prefix}END inherited-clean"
 mutation_source="$d/marker-decoy-duplicate.sh"
 cp "${BASH_SOURCE[0]}" "$mutation_source" || return 1
 printf '\nif false; then\n%s\n%s\nfi\n' "$clean_begin" "$clean_end" >>"$mutation_source"
 ! source_contract "$mutation_source" || return 1
 mutation_source="$d/marker-order-first.sh"; mutation_source2="$d/marker-order-second.sh"
 mutate_exact_line "${BASH_SOURCE[0]}" "$clean_begin" '# G3-ORDER-SWAP-TEMP' "$mutation_source" || return 1
 mutate_exact_line "$mutation_source" "$clean_end" "$clean_begin" "$mutation_source2" || return 1
 mutate_exact_line "$mutation_source2" '# G3-ORDER-SWAP-TEMP' "$clean_end" "$mutation_source" || return 1
 ! source_contract "$mutation_source" || return 1
}
# G3-END isolated-side-effect-self-test
self_test() {
 local d; d=$(mktemp -d); trap 'rm -rf "$d"' RETURN
 source_contract "${BASH_SOURCE[0]}" || return 1
 local mutation_index=0 unsafe_form mutation_source suite_line replacement dollar='$' double_quote='"' command_ref program_ref program_name=${CARGO##*/}
 local -a suite_lines
 command_ref="${double_quote}${dollar}CARGO${double_quote}"; program_ref="${double_quote}${dollar}CARGO_PROGRAM${double_quote}"
 mapfile -t suite_lines < <(suite_contract_lines); [[ ${#suite_lines[@]} == 2 ]] || return 1
 for suite_line in "${suite_lines[@]}"; do
  mutation_index=$((mutation_index + 1)); mutation_source="$d/suite-command-mutation-$mutation_index.sh"
  replacement=${suite_line/"$command_ref"/"$program_ref"}
  [[ $replacement != "$suite_line" && $replacement == *"$program_ref"* ]] || return 1
  mutate_exact_line "${BASH_SOURCE[0]}" "$suite_line" "$replacement" "$mutation_source" || return 1
  [[ $(grep -oF "$CARGO_PROGRAM" "$mutation_source" | wc -l) == 2 ]] || return 1
  grep -Fxq "readonly CARGO=/root/.$CARGO_PROGRAM/bin/$CARGO_PROGRAM" "$mutation_source" || return 1
  ! source_contract "$mutation_source" || return 1
 done
 local identifier='CARGO_' combined_first combined_source
 identifier+='PROGRAM'
 local -a command_refs=(
  "${double_quote}${dollar}${identifier}${double_quote}"
  "${double_quote}${dollar}{${identifier}}${double_quote}"
  "${dollar}${identifier}"
  "${dollar}{${identifier}}"
 )
 for program_ref in "${command_refs[@]}"; do
  mutation_index=$((mutation_index + 1)); mutation_source="$d/variable-command-mutation-$mutation_index.sh"
  cp "${BASH_SOURCE[0]}" "$mutation_source"; printf '\n%s --version\n' "$program_ref" >>"$mutation_source"
  ! program_command_refs_absent "$mutation_source" || return 1
  ! source_contract "$mutation_source" || return 1
 done
 combined_first="$d/combined-first.sh"; combined_source="$d/combined-dead-branch.sh"
 replacement=${suite_lines[0]/"$command_ref"/"${command_refs[0]}"}
 mutate_exact_line "${BASH_SOURCE[0]}" "${suite_lines[0]}" "$replacement" "$combined_first" || return 1
 replacement=${suite_lines[1]/"$command_ref"/"${command_refs[0]}"}
 mutate_exact_line "$combined_first" "${suite_lines[1]}" "$replacement" "$combined_source" || return 1
 printf '\nif false; then\n%s\n%s\nfi\n' "${suite_lines[0]}" "${suite_lines[1]}" >>"$combined_source"
 suite_lines_exact_once "$combined_source" || return 1
 ! program_command_refs_absent "$combined_source" || return 1
 ! source_contract "$combined_source" || return 1
 local braced_ref value_ref manifest_allowed manifest_value balanced_form
 braced_ref="${dollar}{${identifier}}"; value_ref="${dollar}{CARGO##*/}"
 manifest_allowed=" ${double_quote}012a973200c31c92f5447961e7915735a7ae0311f628d9f7a89c375fcc998615 ${braced_ref}-test-release.log${double_quote}"
 manifest_value=" ${double_quote}012a973200c31c92f5447961e7915735a7ae0311f628d9f7a89c375fcc998615 ${value_ref}-test-release.log${double_quote}"
 local -a balanced_forms=(
  "else ${command_refs[0]}"
  "exec ${command_refs[0]}"
  "X=1 ${command_refs[0]}"
  "X=1 ${command_refs[1]}"
  "X=1 ${command_refs[2]}"
  "X=1 ${command_refs[3]}"
  ">out ${command_refs[0]} test"
 )
 for balanced_form in "${balanced_forms[@]}"; do
  mutation_index=$((mutation_index + 1)); mutation_source="$d/balanced-allowlist-mutation-$mutation_index.sh"
  mutate_exact_line "${BASH_SOURCE[0]}" "$manifest_allowed" "$manifest_value" "$mutation_source" || return 1
  printf '\n%s\n' "$balanced_form" >>"$mutation_source"
  [[ $(grep -oF "$identifier" "$mutation_source" | wc -l) == 15 ]] || return 1
  grep -Fxq "readonly CARGO=/root/.$program_name/bin/$program_name" "$mutation_source" || return 1
  suite_lines_exact_once "$mutation_source" || return 1
  program_command_refs_absent "$mutation_source" || return 1
  ! identifier_lines_allowed "$mutation_source" || return 1
  ! source_contract "$mutation_source" || return 1
 done
 local -a unsafe_forms=(
  "if $program_name; then :; fi"
  "! $program_name"
  "( $program_name )"
  "time $program_name"
  "command $program_name"
  "env X=1 $program_name"
 )
 for unsafe_form in "${unsafe_forms[@]}"; do
  mutation_index=$((mutation_index + 1)); mutation_source="$d/source-mutation-$mutation_index.sh"
  cp "${BASH_SOURCE[0]}" "$mutation_source"; printf '\n%s\n' "$unsafe_form" >>"$mutation_source"
  ! source_contract "$mutation_source" || return 1
 done
 mutation_source="$d/source-declaration-mutation.sh"; cp "${BASH_SOURCE[0]}" "$mutation_source"
 sed -i 's/^readonly CARGO=/CARGO=/' "$mutation_source"; ! source_contract "$mutation_source" || return 1
 # G3-BEGIN isolated-side-effect-self-test-call
 g3_self_test "$d" || return 1
 # G3-END isolated-side-effect-self-test-call
 mkdir "$d/clean-repo"; git -C "$d/clean-repo" init -q
 clean "$d/clean-repo"
 if ( clean "$d/not-a-repository" ) >/dev/null 2>&1; then return 1; fi
 printf 'dirty\n' >"$d/clean-repo/untracked"; if ( clean "$d/clean-repo" ) >/dev/null 2>&1; then return 1; fi
 local manifest_dir="$d/g1-manifest" manifest_name manifest_hash
 local -a manifest_names=(HASHES.tsv "${CARGO_PROGRAM}-test-release.log" journal.log results.tsv roundtrips.tsv) test_manifest=()
 mkdir "$manifest_dir" "$manifest_dir/$G1_EMPTY_DIR"
 for manifest_name in "${manifest_names[@]}"; do
  printf '%s\n' "$manifest_name" >"$manifest_dir/$manifest_name"
  manifest_hash=$(sha "$manifest_dir/$manifest_name") || return 1
  test_manifest+=("$manifest_hash $manifest_name")
 done
 verify_exact_manifest "$manifest_dir" "$G1_EMPTY_DIR" "${test_manifest[@]}" || return 1
 printf 'changed\n' >>"$manifest_dir/results.tsv"; ! verify_exact_manifest "$manifest_dir" "$G1_EMPTY_DIR" "${test_manifest[@]}" || return 1
 printf '%s\n' results.tsv >"$manifest_dir/results.tsv"; verify_exact_manifest "$manifest_dir" "$G1_EMPTY_DIR" "${test_manifest[@]}" || return 1
 mv "$manifest_dir/HASHES.tsv" "$d/HASHES.tsv.saved"; ! verify_exact_manifest "$manifest_dir" "$G1_EMPTY_DIR" "${test_manifest[@]}" || return 1
 mv "$d/HASHES.tsv.saved" "$manifest_dir/HASHES.tsv"; verify_exact_manifest "$manifest_dir" "$G1_EMPTY_DIR" "${test_manifest[@]}" || return 1
 printf 'extra\n' >"$manifest_dir/extra"; ! verify_exact_manifest "$manifest_dir" "$G1_EMPTY_DIR" "${test_manifest[@]}" || return 1
 unlink "$manifest_dir/extra"; verify_exact_manifest "$manifest_dir" "$G1_EMPTY_DIR" "${test_manifest[@]}" || return 1
 mv "$manifest_dir/HASHES.tsv" "$d/HASHES.tsv.saved"; ln -s "$d/HASHES.tsv.saved" "$manifest_dir/HASHES.tsv"
 ! verify_exact_manifest "$manifest_dir" "$G1_EMPTY_DIR" "${test_manifest[@]}" || return 1
 unlink "$manifest_dir/HASHES.tsv"; mv "$d/HASHES.tsv.saved" "$manifest_dir/HASHES.tsv"
 mv "$manifest_dir/$G1_EMPTY_DIR" "$d/$G1_EMPTY_DIR.saved"; ! verify_exact_manifest "$manifest_dir" "$G1_EMPTY_DIR" "${test_manifest[@]}" || return 1
 mv "$d/$G1_EMPTY_DIR.saved" "$manifest_dir/$G1_EMPTY_DIR"; verify_exact_manifest "$manifest_dir" "$G1_EMPTY_DIR" "${test_manifest[@]}" || return 1
 rmdir "$manifest_dir/$G1_EMPTY_DIR"; mkdir "$d/alternate-empty-dir"; ln -s "$d/alternate-empty-dir" "$manifest_dir/$G1_EMPTY_DIR"
 ! verify_exact_manifest "$manifest_dir" "$G1_EMPTY_DIR" "${test_manifest[@]}" || return 1
 unlink "$manifest_dir/$G1_EMPTY_DIR"; mkdir "$manifest_dir/$G1_EMPTY_DIR"
 printf 'not empty\n' >"$manifest_dir/$G1_EMPTY_DIR/entry"; ! verify_exact_manifest "$manifest_dir" "$G1_EMPTY_DIR" "${test_manifest[@]}" || return 1
 unlink "$manifest_dir/$G1_EMPTY_DIR/entry"; verify_exact_manifest "$manifest_dir" "$G1_EMPTY_DIR" "${test_manifest[@]}" || return 1
 [[ ${CELLS[*]} == 'nci balanced 108014 c812943fd63414bf4ec185ee048b6550cc6b1a0a523dd3a63afe242bdf133066 736 1472 nci web 108624 2caaa78101082ccfb753909440a60e7381f94210fd8817ac89ccc02d7b6d6848 46 92 dickens max 461437 c8aed8ae4c39d8a463e3d2bcb3fd082ec955d60fd320bbeec41af7a65922285e 768 1536 dickens balanced 472253 25378abf1cbe18e016143c0f0401aac055db8fb1c2964e5a4525371ba400a5ad 736 1472 dickens web 487506 0f3677eeadf937facb8c3b3fd79d6fc04677f19e0b648b983dd732db8a92ba0f 46 92 ooffice max 677605 4d563b48ae509f11b65b0c71929e0b0375b2322b26aefc489b36aefeeacd60be 736 1472 ooffice balanced 677605 4d563b48ae509f11b65b0c71929e0b0375b2322b26aefc489b36aefeeacd60be 736 1472 ooffice web 704087 a8e04efd9c890c8f72a645571ebfd230774e638e9bef7c3118d22a5fffeb0be4 46 92' ]] || return 1
 [[ ${INPUT_SHA[nci]} == 6788fcc1527c0f62709103e68ac9ab9416461ab00ed1f529b3cf2ae4ab06221e && ${INPUT_SHA[dickens]} == df925056e0779c51cb2a27c014e8fc6d25d28ef2fac5b8ce4632d93b86860603 && ${INPUT_SHA[ooffice]} == 5041e86f07bf17d7a8b3b0ab496a1b6413256399848709f8be543bbdca12de09 ]] || return 1
 [[ $(sample_order 1 | paste -sd /) == base/current/zero && $(sample_order 2 | paste -sd /) == current/zero/base && $(sample_order 3 | paste -sd /) == zero/base/current ]] || return 1
 load_below_limit 0 && load_below_limit 1.999 || return 1
 ! load_below_limit 2.0 && ! load_below_limit 2.001 || return 1
 printf '101 bash /usr/bin/harmless\n102 worker /tmp/enc\n' | detect_cubrim_processes || return 1
 ! printf '101 cubrim-worker /usr/bin/worker\n' | detect_cubrim_processes >/dev/null || return 1
 ! printf '101 python python /opt/tools/cubrim-alt\n' | detect_cubrim_processes >/dev/null || return 1
 [[ $(stabilization_step 1.9 0 0) == 1 && $(stabilization_step 1.8 0 1) == 2 && $(stabilization_step 2.0 0 1) == 0 ]] || return 1
 ! stabilization_step 1.0 1 0 >/dev/null || return 1
 [[ $(stabilization_sleep_seconds 0) == 15 && $(stabilization_sleep_seconds 166) == 14 && $(stabilization_sleep_seconds 179) == 1 ]] || return 1
 ! stabilization_sleep_seconds 180 >/dev/null || return 1
 printf 'Elapsed (wall clock) time (h:mm:ss or m:ss): 1:02.50\nMaximum resident set size (kbytes): 123\n' >"$d/time-m.log"
 [[ $(wall_rss "$d/time-m.log") == $'62.500000\t123' ]] || return 1
 printf 'Elapsed (wall clock) time (h:mm:ss or m:ss): 1:02:03.25\nMaximum resident set size (kbytes): 456\n' >"$d/time-h.log"
 [[ $(wall_rss "$d/time-h.log") == $'3723.250000\t456' ]] || return 1
 printf 'Elapsed (wall clock): 1:02\nMaximum resident set size (kbytes): 1\n' >"$d/time-bad.log"
 ! wall_rss "$d/time-bad.log" >/dev/null 2>&1 || return 1
 printf 'cell\tstep\tsample\tbuild\twall_s\tpeak_rss_kib\n' >"$d/results.tsv"
 printf 'cell\tphase\tsample\tbuild\tcmp\n' >"$d/roundtrips.tsv"
 local line f p bytes sum cell b s wall rss order_text; local -a order
 for line in "${CELLS[@]}"; do read -r f p bytes sum _ _ <<<"$line"; cell="$f/$p"; for b in base current zero; do printf '%s\twarmup\t1\t%s\tPASS\n' "$cell" "$b" >>"$d/roundtrips.tsv"; done; for s in 1 2 3; do order_text=$(sample_order "$s") || return 1; mapfile -t order <<<"$order_text"; for b in "${order[@]}"; do case "$b" in base) wall=1.20; rss=100000;; current) wall=1.00; rss=200000;; zero) wall=1.00; rss=120000;; esac; printf '%s\ttimed\t%s\t%s\t%s\t%s\n' "$cell" "$s" "$b" "$wall" "$rss" >>"$d/results.tsv"; printf '%s\ttimed\t%s\t%s\tPASS\n' "$cell" "$s" "$b" >>"$d/roundtrips.tsv"; done; done; done
 parse_verdicts "$d/results.tsv" "$d/roundtrips.tsv" "$d/v.json" "$d/v.tsv"
 [[ $(grep -c $'\tPASS\tACCOUNTING_CONSISTENT$' "$d/v.tsv") == 8 ]] || return 1
 cp "$d/roundtrips.tsv" "$d/good-rt.tsv"
 sed '$d' "$d/good-rt.tsv" >"$d/missing.tsv"; ! parse_verdicts "$d/results.tsv" "$d/missing.tsv" "$d/x" "$d/y" 2>/dev/null || return 1
 cp "$d/good-rt.tsv" "$d/duplicate.tsv"; sed -n '2p' "$d/good-rt.tsv" >>"$d/duplicate.tsv"; ! parse_verdicts "$d/results.tsv" "$d/duplicate.tsv" "$d/x" "$d/y" 2>/dev/null || return 1
 sed '2s/PASS/FAIL/' "$d/good-rt.tsv" >"$d/nonpass.tsv"; ! parse_verdicts "$d/results.tsv" "$d/nonpass.tsv" "$d/x" "$d/y" 2>/dev/null || return 1
 awk 'NR==2{a=$0;next} NR==3{print;print a;next} {print}' "$d/good-rt.tsv" >"$d/swapped.tsv"; ! parse_verdicts "$d/results.tsv" "$d/swapped.tsv" "$d/x" "$d/y" 2>/dev/null || return 1
 awk 'NR==2{a=$0;next} NR==3{print;print a;next} {print}' "$d/results.tsv" >"$d/swapped-results.tsv"; ! parse_verdicts "$d/swapped-results.tsv" "$d/good-rt.tsv" "$d/x" "$d/y" 2>/dev/null || return 1
 cp "$d/results.tsv" "$d/nonpositive.tsv"; sed -i '/^nci\/balanced.*\tbase\t/s/100000/200000/' "$d/nonpositive.tsv"; parse_verdicts "$d/nonpositive.tsv" "$d/good-rt.tsv" "$d/nonpositive.json" "$d/nonpositive.out"
 grep -q '^nci/balanced.*REFUTED' "$d/nonpositive.out" || return 1
 cp "$d/results.tsv" "$d/slow.tsv"; sed -i '/\tzero\t1.00\t120000$/s/1.00/1.06/' "$d/slow.tsv"; parse_verdicts "$d/slow.tsv" "$d/good-rt.tsv" "$d/slow.json" "$d/slow.out"
 grep -q '^nci/balanced.*REFUTED' "$d/slow.out" || return 1
 printf 'SELF_TEST_ONLY: whole-source Cargo, clean-status, exact-manifest, suite-side-effect restore, 72/96 structures, rejection controls, and parser cases passed\n'
}

[[ $# -le 1 ]] || die 'unknown arguments'
if [[ ${1:-} == --self-test ]]; then self_test; exit 0; fi
[[ $# == 0 ]] || die 'unknown argument'

# Nothing above this point touches the live campaign paths.
[[ $(hostname -s) == dev-ai ]] || die 'hostname admission'
[[ ! -e $OUT ]] || die "output exists: $OUT"
load1=$(awk '{print $1}' /proc/loadavg) || die 'load read'; load_below_limit "$load1" || die "load admission: $load1"
process_snapshot=$(ps -eo pid=,comm=,args=) || die 'process snapshot'
if process_hits=$(detect_cubrim_processes <<<"$process_snapshot"); then :; else journal "competing Cubrim processes: $process_hits"; die 'competing Cubrim workload'; fi
[[ $PIN == 0-15 && $CUBR_THREADS == 4 && $CUBRIM_ACCEPT_LICENSE == 1 ]] || die 'runtime setting admission'
[[ $(git -C "$BASE_ROOT" rev-parse HEAD) == "$BASE_SOURCE" ]] || die 'base source'
[[ $(git -C "$CURRENT_ROOT" rev-parse HEAD) == "$CURRENT_SOURCE" ]] || die 'current source'
timeout 60 git -C "$ZERO_ROOT" fetch --quiet origin main || die 'fresh origin/main fetch'
candidate_head=$(git -C "$ZERO_ROOT" rev-parse HEAD) || die 'candidate HEAD unavailable'
fetched_sha=$(git -C "$ZERO_ROOT" rev-parse FETCH_HEAD) || die 'FETCH_HEAD unavailable'
[[ $candidate_head == "$fetched_sha" ]] || die 'candidate HEAD is not freshly fetched main'
git -C "$ZERO_ROOT" merge-base --is-ancestor "$ZERO_ANCHOR" HEAD || die 'zero anchor absent'
git -C "$ZERO_ROOT" diff --quiet "$ZERO_ANCHOR"..HEAD -- code/cubrim-rs || die 'zero code differs from anchor'
clean "$BASE_ROOT"; clean "$CURRENT_ROOT"; clean "$ZERO_ROOT"
# G3-BEGIN head-blob-admission
verify_head_side_effects "$ZERO_ROOT" "${SIDE_EFFECT_SPECS[@]}" || die 'suite side-effect HEAD blobs'
# G3-END head-blob-admission
need_sha "$BASE" "$BASE_SHA"; need_sha "$CURRENT" "$CURRENT_SHA"; need_sha "$ZERO" "$ZERO_SHA"
need_sha "$ZERO_ROOT/code/cubrim-rs/src/cm2.rs" "$ZERO_CM2_SHA"; need_sha "$ZERO_ROOT/$EVIDENCE_REL" "$EVIDENCE_SHA"
[[ $(sha "$ZERO_ROOT/$RUNNER_REL") == $(git -C "$ZERO_ROOT" show "HEAD:$RUNNER_REL" | sha256sum | awk '{print $1}') ]] || die 'runner not committed'
for f in nci dickens ooffice; do need_sha "$(input_for "$f")" "${INPUT_SHA[$f]}"; done
for line in "${CELLS[@]}"; do read -r f p bytes sum _ _ <<<"$line"; need_sha "$(canon_for "$f" "$p")" "$sum"; [[ $(stat -c %s "$(canon_for "$f" "$p")") == "$bytes" ]] || die "canonical bytes $f/$p"; done
verify_g1_manifest || die 'generation-1 preservation manifest'
# G3-BEGIN generation-2-preservation
verify_g2_manifest || die 'generation-2 preservation manifest'
# G3-END generation-2-preservation

on_error() { local status=$?; journal "FAIL: rc=$status line=$1 command=$2"; return "$status"; }
on_exit() { local status=$?; if [[ ${completed:-0} -ne 1 ]]; then rm -f "$OUT/DONE.STAMP" "$OUT/.DONE.STAMP.tmp" || journal 'FAIL: incomplete marker cleanup'; fi; if [[ $status -ne 0 && ${completed:-0} -ne 1 ]]; then journal "FAIL: unexpected exit rc=$status"; fi; return "$status"; }
mkdir -p "$OUT/timing_logs"; LOG="$OUT/journal.log"; completed=0
trap 'on_error "$LINENO" "$BASH_COMMAND"' ERR
trap on_exit EXIT
runner_committed_sha=$(git -C "$ZERO_ROOT" show "HEAD:$RUNNER_REL" | sha256sum | awk '{print $1}')
{
 printf 'kind\tname\tvalue\n'
 printf 'source\tbase\t%s\nsource\tcurrent\t%s\nsource\tzero-anchor\t%s\nsource\tcandidate-head\t%s\nsource\tfetched-FETCH_HEAD\t%s\n' "$BASE_SOURCE" "$CURRENT_SOURCE" "$ZERO_ANCHOR" "$candidate_head" "$fetched_sha"
 printf 'runner\tcommitted-sha256\t%s\n' "$runner_committed_sha"
 printf 'binary\tbase\t%s\nbinary\tcurrent\t%s\nbinary\tzero\t%s\n' "$BASE_SHA" "$CURRENT_SHA" "$ZERO_SHA"
 # G3-BEGIN head-blob-evidence
 for spec in "${SIDE_EFFECT_SPECS[@]}"; do read -r expected path extra <<<"$spec"; printf 'suite-head-blob\t%s\t%s\n' "$path" "$expected"; done
 # G3-END head-blob-evidence
 for f in nci dickens ooffice; do printf 'input\t%s\t%s\n' "$f" "${INPUT_SHA[$f]}"; done
 for line in "${CELLS[@]}"; do read -r f p bytes sum _ _ <<<"$line"; printf 'canonical\t%s/%s\tbytes=%s sha256=%s\n' "$f" "$p" "$bytes" "$sum"; done
} >"$OUT/HASHES.tsv"
journal "admission load1=$load1 pin=$PIN threads=$CUBR_THREADS candidate_head=$candidate_head"
{ printf 'cell\tstep\tsample\tbuild\twall_s\tpeak_rss_kib\n' >"$OUT/results.tsv"; printf 'cell\tphase\tsample\tbuild\tcmp\n' >"$OUT/roundtrips.tsv"; }
( cd "$ZERO_ROOT/code/cubrim-rs" && "$CARGO" test --release ) >"$OUT/${CARGO_PROGRAM}-test-release.log" 2>&1 || die 'Cargo test --release'
( cd "$ZERO_ROOT/code/cubrim-rs" && "$CARGO" test --release --test scheme_roundtrip ) >"$OUT/${CARGO_PROGRAM}-test-scheme-roundtrip.log" 2>&1 || die 'scheme roundtrip test'
# G3-FROZEN-BEGIN live-restore-clean-rehash
restore_suite_side_effects "$ZERO_ROOT" "$OUT/side-effect-restore.log" "${SIDE_EFFECT_SPECS[@]}" || die 'suite side-effect restore'
clean "$ZERO_ROOT"
need_sha "$ZERO" "$ZERO_SHA"; need_sha "$ZERO_ROOT/code/cubrim-rs/src/cm2.rs" "$ZERO_CM2_SHA"
[[ $(git -C "$ZERO_ROOT" show "HEAD:$RUNNER_REL" | sha256sum | awk '{print $1}') == "$runner_committed_sha" ]] || die 'runner changed during suite'
[[ $(git -C "$ZERO_ROOT" rev-parse HEAD) == "$candidate_head" && $(git -C "$ZERO_ROOT" rev-parse FETCH_HEAD) == "$fetched_sha" && $candidate_head == "$fetched_sha" ]] || die 'candidate identity changed during suite'
git -C "$ZERO_ROOT" diff --quiet "$ZERO_ANCHOR"..HEAD -- code/cubrim-rs || die 'zero code changed during suite'
# G3-FROZEN-END live-restore-clean-rehash
journal 'suite completion: Cargo test --release and scheme_roundtrip passed'
stabilization_start=$SECONDS; quiet_samples=0
while (( SECONDS - stabilization_start <= 180 )); do
 stabilization_load=$(awk '{print $1}' /proc/loadavg) || die 'stabilization load read'
 stabilization_ps=$(ps -eo pid=,comm=,args=) || die 'stabilization process snapshot'
 if stabilization_hits=$(detect_cubrim_processes <<<"$stabilization_ps"); then competitors=0; else journal "stabilization competitor: $stabilization_hits"; die 'Cubrim workload appeared during stabilization'; fi
 quiet_samples=$(stabilization_step "$stabilization_load" "$competitors" "$quiet_samples") || die 'stabilization decision'
 stabilization_elapsed=$((SECONDS - stabilization_start)); journal "stabilization sample elapsed=${stabilization_elapsed}s load1=$stabilization_load quiet_consecutive=$quiet_samples"
 if (( quiet_samples >= 2 )); then break; fi
 if (( stabilization_elapsed >= 180 )); then break; fi
 stabilization_sleep=$(stabilization_sleep_seconds "$stabilization_elapsed") || die 'stabilization sleep deadline'
 journal "stabilization wait=${stabilization_sleep}s"; sleep "$stabilization_sleep"
done
(( quiet_samples >= 2 )) || die 'post-suite stabilization timed out after 180s'
journal "stabilization complete elapsed=$((SECONDS - stabilization_start))s quiet_consecutive=$quiet_samples"
for line in "${CELLS[@]}"; do
 read -r f p bytes sum _ _ <<<"$line"; cell="$f/$p"; input=$(input_for "$f"); canon=$(canon_for "$f" "$p")
 for b in base current zero; do binary=$(bin_for "$b"); archive="$OUT/$f.$p.$b.cbr"; timeout 1800 taskset -c "$PIN" "$binary" compress --preset "$p" --quiet "$input" "$archive" || die "compression $cell/$b"; need_sha "$archive" "$sum"; [[ $(stat -c %s "$archive") == "$bytes" ]] || die "archive bytes $cell/$b"; cmp -s "$archive" "$canon" || die "canonical cmp $cell/$b"; done
 if ! cmp -s "$OUT/$f.$p.base.cbr" "$OUT/$f.$p.current.cbr" || ! cmp -s "$OUT/$f.$p.base.cbr" "$OUT/$f.$p.zero.cbr"; then die "fresh archive equality $cell"; fi
 for b in base current zero; do binary=$(bin_for "$b"); back="$OUT/$f.$p.$b.warmup.back"; wl="$OUT/timing_logs/$f.$p.$b.warmup.1.stderr.log"; taskset -c "$PIN" timeout 300 "$binary" decompress "$OUT/$f.$p.$b.cbr" "$back" >/dev/null 2>"$wl" || die "warmup $cell/$b"; cmp -s "$input" "$back" || die "warmup roundtrip $cell/$b"; printf '%s\twarmup\t1\t%s\tPASS\n' "$cell" "$b" >>"$OUT/roundtrips.tsv"; rm -f "$back"; done
 for s in 1 2 3; do order_text=$(sample_order "$s") || die "sample order $s"; mapfile -t order <<<"$order_text"; phase=timed; for b in "${order[@]}"; do binary=$(bin_for "$b"); back="$OUT/$f.$p.$b.$phase.$s.back"; tl="$OUT/timing_logs/$f.$p.$b.$phase.$s.log"; taskset -c "$PIN" /usr/bin/time -v timeout 300 "$binary" decompress "$OUT/$f.$p.$b.cbr" "$back" >/dev/null 2>"$tl" || die "decode $cell/$b/$s"; cmp -s "$input" "$back" || die "roundtrip $cell/$b/$s"; metrics=$(wall_rss "$tl") || die "time parser $cell/$b/$s"; read -r wall rss <<<"$metrics"; [[ $wall =~ ^[0-9]+(\.[0-9]+)?$ && $rss =~ ^[0-9]+$ ]] || die "invalid metrics $cell/$b/$s"; printf '%s\ttimed\t%s\t%s\t%s\t%s\n' "$cell" "$s" "$b" "$wall" "$rss" >>"$OUT/results.tsv"; printf '%s\ttimed\t%s\t%s\tPASS\n' "$cell" "$s" "$b" >>"$OUT/roundtrips.tsv"; rm -f "$back"; done; done
done
parse_verdicts "$OUT/results.tsv" "$OUT/roundtrips.tsv" "$OUT/verdict.json" "$OUT/verdicts.tsv" || die 'final parser and schedule validation'
if [[ $(tail -n +2 "$OUT/results.tsv" | wc -l) != 72 || $(tail -n +2 "$OUT/roundtrips.tsv" | wc -l) != 96 || $(tail -n +2 "$OUT/verdicts.tsv" | wc -l) != 8 ]]; then die 'final structural counts'; fi
completion_utc=$(date -u +%FT%TZ) || die 'completion timestamp'
journal 'completion gates passed; installing marker'
printf 'candidate_sha=%s\ncompletion_utc=%s\nresults=72\nroundtrips=96\nverdicts=8\n' "$candidate_head" "$completion_utc" >"$OUT/.DONE.STAMP.tmp" || die 'DONE.STAMP write'
sync -f "$OUT/.DONE.STAMP.tmp" || die 'DONE.STAMP file durability'
mv "$OUT/.DONE.STAMP.tmp" "$OUT/DONE.STAMP" || die 'DONE.STAMP atomic install'
sync -f "$OUT" || die 'DONE.STAMP directory durability'
completed=1
