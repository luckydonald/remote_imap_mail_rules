import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import schema from "@schema";
import type { Expression, RuleFile } from "./types";
import { isVar } from "./types";
import { expandRules } from "./yaml-io";

export interface Problem {
  path: string;
  message: string;
  /** Index into `rules`, if the problem is inside one. */
  rule: number | null;
  template: string | null;
}

const ajv = new Ajv2020({ strict: false, allErrors: true });
addFormats(ajv);
const validateSchema = ajv.compile(schema as object);

function locate(path: string): Pick<Problem, "rule" | "template"> {
  const rule = /^\/rules\/(\d+)/.exec(path);
  const template = /^\/templates\/([^/]+)/.exec(path);
  return { rule: rule ? Number(rule[1]) : null, template: template ? decodeURIComponent(template[1] ?? "") : null };
}

function collectVars(value: unknown, into: Set<string>): void {
  if (isVar(value)) into.add(value.var);
  else if (Array.isArray(value)) value.forEach((item) => collectVars(item, into));
  else if (typeof value === "object" && value !== null) Object.values(value).forEach((item) => collectVars(item, into));
}

/** Variables an expression needs from its scope: a nested use needs only what its own `variables` refer to. */
export function neededVariables(expression: Expression): Set<string> {
  const names = new Set<string>();
  if (expression.type === "template") collectVars(expression.variables, names);
  else collectVars(expression, names);
  return names;
}

export function templateVariables(file: RuleFile, name: string): string[] {
  const def = file.templates[name];
  if (!def) return [];
  return [...neededVariables(def.content)].sort();
}

function walkUses(node: unknown, path: string, visitUse: (use: Extract<Expression, { type: "template" }>, path: string) => void): void {
  if (Array.isArray(node)) node.forEach((item, index) => walkUses(item, `${path}/${index}`, visitUse));
  else if (typeof node === "object" && node !== null) {
    const record = node as Record<string, unknown>;
    if (record.type === "template" && typeof record.ref === "string") visitUse(record as never, path);
    for (const [key, value] of Object.entries(record)) walkUses(value, `${path}/${key}`, visitUse);
  }
}

export function validateRules(file: RuleFile): Problem[] {
  const problems: Problem[] = [];
  const expanded = expandRules(file);
  if (!validateSchema(expanded)) {
    const seen = new Set<string>();
    for (const error of validateSchema.errors ?? []) {
      // The unions produce one failure per branch, the discriminator keyword or the `type` const is the useful one.
      if (error.keyword === "anyOf" || error.keyword === "oneOf" || error.keyword === "if") continue;
      const message = `${error.message ?? "invalid"}${error.params && "additionalProperty" in error.params ? `: ${String(error.params.additionalProperty)}` : ""}`;
      const key = `${error.instancePath}|${message}`;
      if (seen.has(key)) continue;
      seen.add(key);
      problems.push({ path: error.instancePath || "/", message, ...locate(error.instancePath) });
    }
  }
  walkUses(file.rules, "/rules", (use, path) => checkUse(file, use, path, problems));
  walkUses(file.templates, "/templates", (use, path) => checkUse(file, use, path, problems));
  return problems;
}

function checkUse(file: RuleFile, use: Extract<Expression, { type: "template" }>, path: string, problems: Problem[]): void {
  const def = file.templates[use.ref];
  if (!def) {
    problems.push({ path, message: `template \`${use.ref}\` does not exist`, ...locate(path) });
    return;
  }
  const needed = new Set(templateVariables(file, use.ref));
  const set = new Set(Object.keys(use.variables ?? {}));
  const defaults = new Set(Object.keys(def.defaults ?? {}));
  const missing = [...needed].filter((name) => !set.has(name) && !defaults.has(name));
  const unknown = [...set].filter((name) => !needed.has(name));
  if (missing.length > 0) problems.push({ path, message: `variables without value or default: ${missing.join(", ")}`, ...locate(path) });
  if (unknown.length > 0) problems.push({ path, message: `template has no such variables: ${unknown.join(", ")}`, ...locate(path) });
}
