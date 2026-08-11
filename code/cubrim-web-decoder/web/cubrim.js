// Cubrim Web Profile decoder — JavaScript glue for the WASM reference decoder.
//
// Public API:
//   const cubrim = await CubrimDecoder.load(urlOrBytes);
//   const bytes  = cubrim.cubrimDecode(compressed);   // Uint8Array -> Uint8Array
//
// Synchronous by design, per CUBR-0077: a streaming API is out of scope and is
// sketched in the task's docs instead of half-built here.
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

  #lastError() {
    const ptr = this.exports.cbr_last_error_ptr();
    const len = this.exports.cbr_last_error_len();
    if (len === 0) return 'unknown error';
    const bytes = new Uint8Array(this.memory.buffer, ptr, len);
    return new TextDecoder().decode(bytes);
  }
}

export default CubrimDecoder;
