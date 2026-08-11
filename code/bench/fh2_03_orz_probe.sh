#!/usr/bin/env bash
set -euo pipefail

corpus=${CORPUS:-/root/corpus-full/silesia}
results=${RESULTS:-/root/fh2-03-results}
orz=${ORZ:-/root/fh2-03-orz-src/target/release/orz}
limit=${LIMIT:-1048576}
tag=${TAG:-head1m}
read -r -a files <<<"${FILES:-mozilla sao ooffice}"

command -v 7z >/dev/null
test -x "$orz"
mkdir -p "$results"
summary="$results/$tag.tsv"
test ! -e "$summary"
printf 'file\torig\torz_bytes\torz_ratio\torz_rt\tseven_bytes\tseven_ratio\tseven_rt\n' >"$summary"

for name in "${files[@]}"; do
    source_file="$corpus/$name"
    test -f "$source_file"
    run_dir="$results/$tag-$name"
    test ! -e "$run_dir"
    mkdir -p "$run_dir"

    input="$source_file"
    if ((limit > 0)); then
        input="$run_dir/input"
        head -c "$limit" "$source_file" >"$input"
    fi
    orig=$(stat -c %s "$input")
    sha256sum "$input" >"$run_dir/input.sha256"

    # v1.6.2 advertises/defaults to level 3, but its match table accepts only
    # 0..=2; level 2 is therefore the strongest executable configuration.
    /usr/bin/time -f '%e\t%M' -o "$run_dir/orz-encode.time" \
        "$orz" encode -s -l 2 "$input" "$run_dir/orz.bin"
    /usr/bin/time -f '%e\t%M' -o "$run_dir/orz-decode.time" \
        "$orz" decode -s "$run_dir/orz.bin" "$run_dir/orz.out"
    cmp "$input" "$run_dir/orz.out"
    orz_bytes=$(stat -c %s "$run_dir/orz.bin")

    /usr/bin/time -f '%e\t%M' -o "$run_dir/7z-encode.time" \
        7z a -t7z -m0=lzma2 -mx=9 -mmt=1 -bd -y \
        "$run_dir/7z.bin" "$input" >/dev/null
    /usr/bin/time -f '%e\t%M' -o "$run_dir/7z-decode.time" \
        7z e -so "$run_dir/7z.bin" >"$run_dir/7z.out"
    cmp "$input" "$run_dir/7z.out"
    seven_bytes=$(stat -c %s "$run_dir/7z.bin")

    orz_ratio=$(awk -v c="$orz_bytes" -v n="$orig" 'BEGIN { printf "%.9f", c/n }')
    seven_ratio=$(awk -v c="$seven_bytes" -v n="$orig" 'BEGIN { printf "%.9f", c/n }')
    printf '%s\t%s\t%s\t%s\tcmp0\t%s\t%s\tcmp0\n' \
        "$name" "$orig" "$orz_bytes" "$orz_ratio" "$seven_bytes" "$seven_ratio" \
        | tee -a "$summary"
done

sha256sum "$summary"
