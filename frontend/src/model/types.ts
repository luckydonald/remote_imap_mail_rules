/** Mirrors the pydantic rule file. A `Templatable<T>` is a value or a `Var`. */

export interface Var {
  var: string
}

export type Templatable<T> = T | Var

export type TimeValue = { relative: false; value: string } | { relative: true; value: string }

export interface GroupAll {
  type: 'all'
  conditions: Expression[]
}

export interface GroupAny {
  type: 'any'
  conditions: Expression[]
}

export interface GroupNot {
  type: 'not'
  condition: Expression
}

export interface TextCondition {
  type: 'text'
  field: Templatable<string>
  operator: Templatable<string>
  value: Templatable<string | string[]>
  case_sensitive?: Templatable<boolean>
  quantifier?: Templatable<string>
}

export interface HeaderCondition {
  type: 'header'
  name: Templatable<string>
  operator: Templatable<string>
  value: Templatable<string | string[]>
  case_sensitive?: Templatable<boolean>
  quantifier?: Templatable<string>
}

export interface AddressCondition {
  type: 'address'
  field: Templatable<string>
  part?: Templatable<string>
  operator: Templatable<string>
  value: Templatable<string | string[]>
  case_sensitive?: Templatable<boolean>
  quantifier?: Templatable<string>
}

export interface NumberCondition {
  type: 'number'
  field: Templatable<string>
  operator: Templatable<string>
  value: Templatable<number | [number, number]>
  quantifier?: Templatable<string>
}

export interface DateCondition {
  type: 'date'
  field: Templatable<string>
  operator: Templatable<string>
  value: Templatable<TimeValue | [TimeValue, TimeValue]>
}

export interface BoolCondition {
  type: 'bool'
  field: Templatable<string>
  value?: Templatable<boolean>
  quantifier?: Templatable<string>
}

export interface PresenceCondition {
  type: 'presence'
  field?: Templatable<string>
  header?: Templatable<string>
  operator?: Templatable<string>
  value?: Templatable<boolean>
}

/** Use of a template: in the file `<<: *anchor` plus `variables`. `ref` is the key in `templates`. */
export interface TemplateUse {
  type: 'template'
  ref: string
  variables: Record<string, unknown>
}

export type Expression =
  | GroupAll
  | GroupAny
  | GroupNot
  | TextCondition
  | HeaderCondition
  | AddressCondition
  | NumberCondition
  | DateCondition
  | BoolCondition
  | PresenceCondition
  | TemplateUse

export interface Location {
  account_id: Templatable<string>
  folder?: Templatable<string>
  recursive?: Templatable<boolean>
}

export type Action =
  | { type: 'move'; folder: Templatable<string>; account_id?: Templatable<string> }
  | { type: 'mark_read' }
  | { type: 'mark_unread' }
  | { type: 'flag'; value?: Templatable<boolean> }
  | { type: 'keyword'; keyword: Templatable<string>; value?: Templatable<boolean> }

export interface Rule {
  name: string
  description?: string
  enabled?: Templatable<boolean>
  locations: Location[]
  when: Expression
  actions?: Action[]
}

export interface TemplateDef {
  type: 'template'
  defaults: Record<string, unknown>
  content: Expression
}

export interface RuleFile {
  $schema?: string
  templates: Record<string, TemplateDef>
  rules: Rule[]
}

export function isVar(value: unknown): value is Var {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value) &&
    Object.keys(value).length === 1 &&
    typeof (value as Var).var === 'string'
  )
}
