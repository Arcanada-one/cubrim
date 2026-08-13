// Cubrim Web Profile decoder — JavaScript glue for the WASM reference decoder.
//
// Public API:
//   const cubrim = await CubrimDecoder.load(urlOrBytes);
//   const bytes  = cubrim.cubrimDecode(compressed);   // Uint8Array -> Uint8Array
//
// Single-frame decoding is synchronous by design; the streaming API below is
// an async generator for network bodies.
//
// Works in a browser (fetch + WebAssembly.instantiateStreaming) and in Node
// (pass the bytes in). No bundler, no wasm-bindgen, no dependencies.

const ABI_VERSION = 1;

export class CubrimDecoder {
  constructor(instance) {
    this.exports = instance.exports;
    this.memory = instance.exports.memory;
    const abi = this.exports.cbr_abi_version();
    if (abi !== ABI_VERSION) {
      throw new Error(`cubrim: module ABI ${abi}, expected ${ABI_VERSION}`);
    }
  }

  /** Load from a URL (browser) or from raw module bytes (Node/tests). */
  static async load(source) {
    let instance;
    if (typeof source === 'string') {
      if (typeof WebAssembly.instantiateStreaming === 'function') {
        const result = await WebAssembly.instantiateStreaming(fetch(source), {});
        instance = result.instance;
      } else {
        const bytes = new Uint8Array(await (await fetch(source)).arrayBuffer());
        instance = (await WebAssembly.instantiate(bytes, {})).instance;
      }
    } else {
      instance = (await WebAssembly.instantiate(source, {})).instance;
    }
    return new CubrimDecoder(instance);
  }

  /**
   * Decode one `application/cubrim` frame.
   *
   * @param {Uint8Array} compressed frame bytes
   * @param {number} [maxOutput] byte ceiling for the decoded output; 0 = the
   *   module's own default (64 MiB). A page serving known assets should pass a
   *   real bound — the decoder enforces it before allocating.
   * @returns {Uint8Array} a copy of the decoded bytes, owned by the caller
   */
  cubrimDecode(compressed, maxOutput = 0) {
    const { cbr_alloc, cbr_free, cbr_decode, cbr_out_ptr, cbr_out_len, cbr_out_clear } =
      this.exports;

    const inPtr = cbr_alloc(compressed.length);
    if (inPtr === 0 && compressed.length > 0) {
      throw new Error('cubrim: allocation failed');
    }
    try {
      new Uint8Array(this.memory.buffer, inPtr, compressed.length).set(compressed);
      const ok = cbr_decode(inPtr, compressed.length, maxOutput);
      if (ok !== 1) {
        throw new Error(`cubrim: ${this.#lastError()}`);
      }
      // Read AFTER the call: a growing heap detaches any earlier view.
      const outPtr = cbr_out_ptr();
      const outLen = cbr_out_len();
      const out = new Uint8Array(outLen);
      out.set(new Uint8Array(this.memory.buffer, outPtr, outLen));
      cbr_out_clear();
      return out;
    } finally {
      cbr_free(inPtr, compressed.length);
    }
  }

  /**
   * Decode a frame progressively from a byte stream — a `fetch` body, for
   * instance — yielding each chunk of output as its block completes.
   *
   * Multi-block frames make progress before the response ends; a single-block
   * frame yields everything at the end, which is the honest behaviour rather
   * than a fake trickle.
   *
   * **Integrity:** bytes yielded before completion are not yet verified against
   * the frame checksum. The generator throws if the final verification fails,
   * so a consumer that has already rendered early bytes must be prepared to
   * discard them. Use `cubrimDecode` when that is unacceptable.
   *
   * @param {ReadableStream<Uint8Array>|AsyncIterable<Uint8Array>} source
   * @param {number} [maxOutput]
   * @returns {AsyncGenerator<Uint8Array, Uint8Array>} chunks, then the whole
   */
  async *cubrimDecodeStream(source, maxOutput = 0) {
    const {
      cbr_alloc, cbr_free, cbr_stream_open, cbr_stream_push,
      cbr_stream_fresh_ptr, cbr_stream_fresh_len, cbr_stream_finish,
      cbr_stream_close, cbr_out_ptr, cbr_out_len, cbr_out_clear,
    } = this.exports;

    cbr_stream_open(maxOutput);
    try {
      for await (const chunk of iterate(source)) {
        const ptr = cbr_alloc(chunk.length);
        if (ptr === 0 && chunk.length > 0) {
          throw new Error('cubrim: allocation failed');
        }
        try {
          new Uint8Array(this.memory.buffer, ptr, chunk.length).set(chunk);
          if (cbr_stream_push(ptr, chunk.length) !== 1) {
            throw new Error(`cubrim: ${this.#lastError()}`);
          }
        } finally {
          cbr_free(ptr, chunk.length);
        }
        // Read AFTER the call: a grown heap detaches earlier views.
        const freshLen = cbr_stream_fresh_len();
        if (freshLen > 0) {
          const fresh = new Uint8Array(freshLen);
          fresh.set(new Uint8Array(this.memory.buffer, cbr_stream_fresh_ptr(), freshLen));
          yield fresh;
        }
      }
      if (cbr_stream_finish() !== 1) {
        throw new Error(`cubrim: ${this.#lastError()}`);
      }
      const all = new Uint8Array(cbr_out_len());
      all.set(new Uint8Array(this.memory.buffer, cbr_out_ptr(), all.length));
      cbr_out_clear();
      return all;
    } finally {
      cbr_stream_close();
    }
  }

  #lastError() {
    const ptr = this.exports.cbr_last_error_ptr();
    const len = this.exports.cbr_last_error_len();
    if (len === 0) return 'unknown error';
    const bytes = new Uint8Array(this.memory.buffer, ptr, len);
    return new TextDecoder().decode(bytes);
  }
}

/** Iterate a ReadableStream or any async iterable of Uint8Array uniformly. */
async function* iterate(source) {
  if (source && typeof source.getReader === 'function') {
    const reader = source.getReader();
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) return;
        yield value;
      }
    } finally {
      reader.releaseLock();
    }
  } else {
    yield* source;
  }
}

export default CubrimDecoder;
