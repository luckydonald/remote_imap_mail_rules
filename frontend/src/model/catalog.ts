import schema from "@schema";
import type { Expression } from "./types";

interface Defs {
  [name: string]: { enum?: string[] };
}
const defs = (schema as unknown as { $defs: Defs }).$defs;

function enumOf(name: string): string[] {
  const values = defs[name]?.enum;
  if (!values) throw new Error(`schema has no enum ${name}`);
  return values;
}

export const textFields = enumOf("TextField");
export const addressFields = enumOf("AddressField");
export const numberFields = enumOf("NumberField");
export const dateFields = enumOf("DateField");
export const boolFields = enumOf("BoolField");
export const addressParts = enumOf("AddressPart");
export const textOperators = enumOf("TextOperator");
export const compareOperators = enumOf("CompareOperator");
export const presenceOperators = enumOf("PresenceOperator");
export const quantifiers = enumOf("Quantifier");
export const presenceFields = [...textFields, ...addressFields, ...numberFields, ...dateFields, ...boolFields];

export const actionTypes = ["move", "mark_read", "mark_unread", "flag", "keyword"] as const;

export const expressionTypes = ["all", "any", "not", "text", "address", "header", "number", "date", "bool", "presence", "template"] as const;
export type ExpressionType = (typeof expressionTypes)[number];

export const typeLabels: Record<ExpressionType, string> = {
  all: "All of (AND)",
  any: "Any of (OR)",
  not: "Not",
  text: "Text field",
  address: "Address field",
  header: "Header",
  number: "Number",
  date: "Date",
  bool: "Flag / yes-no",
  presence: "Presence",
  template: "Template",
};

export const operatorLabels: Record<string, string> = {
  equals: "equals",
  contains: "contains",
  startswith: "starts with",
  endswith: "ends with",
  regex: "matches regex",
  glob: "matches glob",
  in: "is one of",
  eq: "=",
  ne: "≠",
  lt: "<",
  gt: ">",
  gte: "≥",
  lte: "≤",
  between: "between",
  exists: "exists",
  empty: "is empty",
};

export function newExpression(type: ExpressionType, templateNames: string[] = []): Expression {
  switch (type) {
    case "all":
    case "any":
      return { type, conditions: [newExpression("text")] };
    case "not":
      return { type, condition: newExpression("text") };
    case "text":
      return { type, field: "subject", operator: "contains", value: "" };
    case "address":
      return { type, field: "from", part: "address", operator: "equals", value: "" };
    case "header":
      return { type, name: "X-Header", operator: "contains", value: "" };
    case "number":
      return { type, field: "size", operator: "gt", value: 0 };
    case "date":
      return { type, field: "date_received", operator: "lt", value: { relative: true, value: "7d" } };
    case "bool":
      return { type, field: "seen", value: true };
    case "presence":
      return { type, field: "subject", operator: "exists", value: true };
    case "template":
      return { type, ref: templateNames[0] ?? "", variables: {} };
  }
}
