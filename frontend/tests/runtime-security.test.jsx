import assert from "node:assert/strict";
import { test } from "node:test";
import dns from "node:dns";
import tls from "node:tls";
import zlib from "node:zlib";

test("Brotli has the patched block-switch error and decodes valid input", () => {
  // Node backports the fix without changing process.versions.brotli.
  assert.equal(zlib.constants.BROTLI_DECODER_ERROR_FORMAT_BLOCK_SWITCH, -17);
  const input = Buffer.from("Raphael HTTPS runtime regression check");
  assert.deepEqual(zlib.brotliDecompressSync(zlib.brotliCompressSync(input)), input);
});

test("TLS rejects noncanonical IP hosts even with matching DNS names", () => {
  for (const hostname of ["１２７.0.0.1", "0127.0.0.1", "127.1"]) {
    const error = tls.checkServerIdentity(hostname, {
      subject: { CN: hostname },
      subjectaltname: `DNS:${hostname}, DNS:127.0.0.1`,
    });
    assert.equal(error?.code, "ERR_TLS_CERT_ALTNAME_INVALID", hostname);
  }
  assert.equal(tls.checkServerIdentity("127.0.0.1", {
    subjectaltname: "IP Address:127.0.0.1",
  }), undefined);
});

test("DNS rejects NUL-containing names before attempting resolution", () => {
  assert.throws(() => dns.resolve("invalid\0.example", () => {}), {
    code: "ERR_INVALID_ARG_VALUE",
  });
});
