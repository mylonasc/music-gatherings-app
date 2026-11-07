#!/usr/bin/env node
/**
 * Generate TypeScript interfaces from the backend OpenAPI schemas.
 *
 * Usage (backend running locally):
 *   npm run gen:api
 *
 * The output is committed so the UI builds without a live backend, but it
 * must be regenerated whenever backend schemas change.
 */
import { writeFileSync } from "node:fs";

const OPENAPI_URL = process.env.OPENAPI_URL ?? "http://localhost:8000/openapi.json";
const OUT_PATH = new URL("../src/lib/api-types.ts", import.meta.url);

function tsType(schema, refName) {
  if (!schema || typeof schema !== "object") return "unknown";
  if (schema.$ref) return schema.$ref.split("/").pop();
  if (schema.enum) return schema.enum.map((v) => JSON.stringify(v)).join(" | ");
  if (schema.anyOf) return schema.anyOf.map((s) => tsType(s, refName)).join(" | ");
  if (schema.allOf) {
    const parts = schema.allOf.map((s) => tsType(s, refName)).filter((t) => t !== "object");
    return parts.length > 0 ? parts.join(" & ") : "Record<string, unknown>";
  }
  switch (schema.type) {
    case "string":
      return "string";
    case "null":
      return "null";
    case "integer":
      return "number";
    case "number":
      return "number";
    case "boolean":
      return "boolean";
    case "array":
      return `${tsType(schema.items, refName)}[]`;
    case "object":
      if (!schema.properties) return "Record<string, unknown>";
      return refName;
    default:
      return "unknown";
  }
}

function renderInterface(name, schema) {
  if (schema.type !== "object" || !schema.properties) {
    return `export type ${name} = ${tsType(schema)};`;
  }
  const required = new Set(schema.required ?? []);
  const lines = Object.entries(schema.properties).map(([key, prop]) => {
    const optional = required.has(key) ? "" : "?";
    const safe = /^[A-Za-z_$][A-Za-z0-9_$]*$/.test(key) ? key : JSON.stringify(key);
    return `  ${safe}${optional}: ${tsType(prop)};`;
  });
  return `export interface ${name} {\n${lines.join("\n")}\n}`;
}

const response = await fetch(OPENAPI_URL);
if (!response.ok) {
  console.error(`Cannot fetch OpenAPI from ${OPENAPI_URL}: ${response.status}`);
  console.error("Start the backend first (see README.md).");
  process.exit(1);
}
const spec = await response.json();
const schemas = spec.components?.schemas ?? {};
const header = `/* GENERATED from backend OpenAPI — do not edit by hand. Run: npm run gen:api */\n`;
const bodies = Object.entries(schemas).map(([name, schema]) => renderInterface(name, schema));
writeFileSync(OUT_PATH, `${header}\n${bodies.join("\n\n")}\n`);
console.log(`Wrote ${OUT_PATH} (${bodies.length} types)`);
