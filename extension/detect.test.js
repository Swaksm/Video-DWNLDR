const test = require("node:test");
const assert = require("node:assert");
const { urlExt, classify, totalSize, human, safeName } = require("./detect.js");

test("urlExt", () => {
  assert.strictEqual(urlExt("https://x.com/a/video.MP4?token=1"), "mp4");
  assert.strictEqual(urlExt("https://x.com/stream/master.m3u8"), "m3u8");
  assert.strictEqual(urlExt("https://x.com/watch"), "");
  assert.strictEqual(urlExt("not a url"), "");
});

test("classify matches core.py", () => {
  assert.strictEqual(classify("https://x.com/a.mp4?t=1", ""), "direct");
  assert.strictEqual(classify("https://x.com/a", "video/webm"), "direct");
  assert.strictEqual(classify("https://x.com/a.mp3", "audio/mpeg"), "direct");
  assert.strictEqual(classify("https://x.com/master.m3u8", ""), "manifest");
  assert.strictEqual(classify("https://x.com/a", "application/dash+xml"), "manifest");
  assert.strictEqual(classify("https://x.com/seg-1.ts", ""), null);
  assert.strictEqual(classify("https://x.com/seg-1.m4s", ""), null);
  assert.strictEqual(classify("https://x.com/logo.png", "image/png"), null);
});

test("totalSize prefers content-range", () => {
  assert.strictEqual(totalSize({ "content-range": "bytes 0-9/1234", "content-length": "10" }), 1234);
  assert.strictEqual(totalSize({ "content-length": "99" }), 99);
  assert.strictEqual(totalSize({}), 0);
});

test("human", () => {
  assert.strictEqual(human(0), "?");
  assert.strictEqual(human(1536), "1.5 KB");
  assert.strictEqual(human(5 * 1024 ** 3), "5.0 GB");
});

test("safeName", () => {
  assert.strictEqual(safeName("https://x.com/a/my%20clip.mp4?x=1", "mp4"), "my clip.mp4");
  assert.strictEqual(safeName("https://x.com/a/stream", "mp4"), "stream.mp4");
  assert.strictEqual(safeName("https://x.com/", "mp4"), "video.mp4");
  assert.ok(!safeName("https://x.com/a%2Fb.mp4", "mp4").includes("/"));
});
