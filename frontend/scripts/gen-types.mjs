// Generate src/lib/generated/events.ts from the backend's JSON Schema (make types).
import { compile } from "json-schema-to-typescript";
import { readFileSync, writeFileSync } from "node:fs";

const schema = JSON.parse(readFileSync("src/lib/generated/events.schema.json", "utf8"));
const ts = await compile(schema, "NexusEvent", {
  bannerComment: "/* Generated from backend/nexus/core/event_types.py by `make types`. Do not edit. */",
  additionalProperties: false,
  unreachableDefinitions: false,
  style: { printWidth: 120 },
});
writeFileSync("src/lib/generated/events.ts", ts);
console.log("wrote src/lib/generated/events.ts");
