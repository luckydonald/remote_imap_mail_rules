import { isMap, isNode, isScalar, isSeq, type Document, type Node } from 'yaml'

/** The comment related properties of a YAML node. */
interface Notes {
  commentBefore?: string | null
  comment?: string | null
  spaceBefore?: boolean
}

/** The header line is generated from `$schema`, so the one in the source must not be copied a second time. */
const GENERATED = new Set(['/$schema#key'])

function ruleName(item: Node): string | undefined {
  if (!isMap(item)) return undefined
  const name = item.get('name')
  return typeof name === 'string' ? name : undefined
}

/**
 * Child nodes with a path that survives edits.
 * Map entries use their key (`#key` is the key node itself), items of `rules` use the rule name, other items their index.
 * That way moving, duplicating or deleting a rule keeps the comments of the others.
 */
function* children(node: unknown, path: string): Generator<[string, Node]> {
  if (isMap(node)) {
    for (const pair of node.items) {
      const key = isScalar(pair.key) ? String(pair.key.value) : String(pair.key)
      if (isNode(pair.key)) yield [`${path}/${key}#key`, pair.key]
      if (isNode(pair.value)) yield [`${path}/${key}`, pair.value]
    }
  } else if (isSeq(node)) {
    const seen = new Map<string, number>()
    for (const [index, item] of node.items.entries()) {
      if (!isNode(item)) continue
      const name = path === '/rules' ? ruleName(item) : undefined
      const id = name !== undefined ? `n:${name}` : `i:${index}`
      const count = seen.get(id) ?? 0
      seen.set(id, count + 1)
      yield [`${path}/${count > 0 ? `${id}~${count}` : id}`, item]
    }
  }
}

function walk(node: Node, path: string, visit: (path: string, node: Node) => void): void {
  visit(path, node)
  for (const [childPath, child] of children(node, path)) walk(child, childPath, visit)
}

function notesOf(node: Node): Notes | undefined {
  const notes: Notes = {}
  if (typeof node.commentBefore === 'string') notes.commentBefore = node.commentBefore
  if (typeof node.comment === 'string') notes.comment = node.comment
  if (node.spaceBefore) notes.spaceBefore = true
  return Object.keys(notes).length > 0 ? notes : undefined
}

export type CommentMap = Map<string, Notes>

/** Collects the comments and blank lines of a parsed document by path. */
export function collectComments(source: Document): CommentMap {
  const found: CommentMap = new Map()
  if (!isNode(source.contents)) return found
  walk(source.contents, '', (path, node) => {
    const notes = notesOf(node)
    if (!notes) return
    // A comment above the first item of a sequence is stored on the sequence by the parser, but belongs to that item.
    const first =
      isSeq(node) && notes.commentBefore !== undefined ? children(node, path).next() : undefined
    if (first && !first.done) {
      const [firstPath] = first.value
      delete notes.commentBefore
      found.set(firstPath, { ...found.get(firstPath), commentBefore: node.commentBefore })
      if (Object.keys(notes).length > 0) found.set(path, { ...found.get(path), ...notes })
      return
    }
    found.set(path, { ...found.get(path), ...notes })
  })
  return found
}

/** Writes collected comments onto the nodes of `target` that still exist at the same path. */
export function applyComments(target: Document, comments: CommentMap): void {
  if (!isNode(target.contents)) return
  walk(target.contents, '', (path, node) => {
    const notes = comments.get(path)
    if (!notes || GENERATED.has(path)) return
    Object.assign(node, notes)
  })
}

/** The comment properties of a node, to carry over to a node that replaces it. */
export function moveNotes(from: Node, to: Node): void {
  const notes = notesOf(from)
  if (notes) Object.assign(to, notes)
}
