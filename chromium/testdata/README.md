# Golden vectors for the CbmSourceStream unittests (CUBR-0079)

`golden-manifest.tsv` pins, per census asset: original size + sha256 and the
single-block Web Profile frame's size + sha256. Frames are NOT committed —
they regenerate deterministically from the pinned corpus with the in-repo
encoder:

```sh
cd code/cubrim-web-decoder
cargo run --release --example make_web_fixtures -- ../../bench/web-corpus/payloads-v2 <out-dir>
```

Generated at cubrim main `53276b3` (encoder unchanged since `cedc11d`; the
two commits between are JS/proxy only). If regeneration ever produces frames
whose sha256 differs from this manifest, the ENCODER changed — regenerate the
manifest in the same change and say so in its commit, or the Chromium-side
golden tests will chase phantom corruption.
