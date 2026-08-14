/**
 * Rasterise `public/mark.svg` into the icon files browsers still ask for.
 *
 * The site ships no imagery, deliberately, and a test enforces it — a raster
 * has no source to compare against, so it goes stale silently while everything
 * else on the page is pinned to something. These three are the exception and
 * this file is why they are allowed to be: they are not content, they are
 * browser chrome, and they are generated from the mark rather than drawn.
 *
 * Not byte-checked against a rebuild, unlike the fixtures and the notices.
 * PNG encoders differ between Chrome versions and a check that fails on a
 * browser upgrade is a check people learn to skip. What is checked is that the
 * source is the mark and that this generator exists.
 *
 *     node tools/build_icons.mjs
 */

import { chromium } from "playwright";
import { readFileSync, writeFileSync } from "node:fs";

const SIZES = [
  [180, "public/apple-touch-icon.png"],
  [32, "public/icon-32.png"],
  [16, "public/icon-16.png"],
];

const mark = readFileSync("public/mark.svg", "utf8");
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage();

for (const [size, file] of SIZES) {
  await page.setViewportSize({ width: size, height: size });
  /*
   * On the ink ground, not transparent. The mark is a stroke drawing in
   * `currentColor`; rasterised on transparency it is invisible against a dark
   * tab strip, which is where a favicon spends most of its life.
   */
  await page.setContent(
    `<body style="margin:0;background:#0e1116;display:flex;align-items:center;` +
      `justify-content:center;width:${size}px;height:${size}px">` +
      `<div style="width:${Math.round(size * 0.68)}px;height:${Math.round(size * 0.68)}px;` +
      `color:#4ed8ea">${mark.replace("<svg", '<svg width="100%" height="100%"')}</div></body>`,
  );
  await page.waitForTimeout(120);
  writeFileSync(file, await page.screenshot());
  console.log(`  ${file} ${size}x${size}`);
}

await browser.close();

/*
 * The .ico, assembled by hand.
 *
 * It is a tiny container — a header, one 16-byte entry per image, then the
 * images — and PNG-in-ICO is understood everywhere that still requests this
 * path, so the two rasters go in as they are rather than being re-encoded to
 * BMP. No dependency for eleven lines.
 */
const entries = [
  [16, readFileSync("public/icon-16.png")],
  [32, readFileSync("public/icon-32.png")],
];
const header = Buffer.alloc(6);
header.writeUInt16LE(0, 0);
header.writeUInt16LE(1, 2);
header.writeUInt16LE(entries.length, 4);

let offset = header.length + 16 * entries.length;
const directory = [];
for (const [size, data] of entries) {
  const row = Buffer.alloc(16);
  row.writeUInt8(size, 0);
  row.writeUInt8(size, 1);
  row.writeUInt16LE(1, 4);
  row.writeUInt16LE(32, 6);
  row.writeUInt32LE(data.length, 8);
  row.writeUInt32LE(offset, 12);
  directory.push(row);
  offset += data.length;
}

writeFileSync(
  "public/favicon.ico",
  Buffer.concat([header, ...directory, ...entries.map(([, data]) => data)]),
);
console.log("  public/favicon.ico");
