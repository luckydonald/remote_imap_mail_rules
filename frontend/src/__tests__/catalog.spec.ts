import { describe, expect, it } from 'vitest'
import {
  addressFields,
  boolFields,
  compareOperators,
  dateFields,
  newExpression,
  numberFields,
  textFields,
  textOperators,
  expressionTypes,
} from '@/model/catalog'
import { validateRules } from '@/model/validate'

describe('catalog', () => {
  it('reads the enums from the schema', () => {
    expect(textFields).toContain('subject')
    expect(addressFields).toContain('from')
    expect(numberFields).toContain('spam_score')
    expect(dateFields).toContain('date_received')
    expect(boolFields).toContain('seen')
    expect(textOperators).toContain('in')
    expect(compareOperators).toContain('between')
  })

  it.each(expressionTypes.filter((type) => type !== 'template'))(
    'a new %s condition is valid',
    (type) => {
      const when = newExpression(type)
      // Empty text values and an empty account id are fine for the schema except the UUID.
      const problems = validateRules({
        templates: {},
        rules: [
          { name: 'x', locations: [{ account_id: '6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11' }], when },
        ],
      })
      expect(problems).toEqual([])
    },
  )
})
