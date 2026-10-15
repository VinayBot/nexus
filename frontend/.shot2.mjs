import { chromium } from "@playwright/test";
const [,, url, out, clickText] = process.argv;
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1600, height: 1000 } });
const errs = [];
p.on("pageerror", e => errs.push(String(e)));
p.on("console", m => m.type() === "error" && errs.push(m.text()));
await p.goto(url, { waitUntil: "networkidle" });
await p.waitForTimeout(4000);
if (clickText) { await p.getByRole("tab", { name: clickText }).click(); await p.waitForTimeout(3000); }
await p.screenshot({ path: out });
console.log(errs.length ? "ERRORS:\n" + errs.slice(0,5).join("\n") : "no console errors");
await b.close();
