import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("build contains the Auto Calendar application shell", async () => {
  const html = await readFile(new URL("../.next/server/app/index.html", import.meta.url), "utf8");
  assert.match(html, /<title>Auto Calendar · 酒店房态中心<\/title>/i);
  assert.match(html, /正在打开酒店工作台/);
  assert.match(html, /manifest\.webmanifest/);
  assert.doesNotMatch(html, /Your site is taking shape|react-loading-skeleton/);
});
