# E2E report: 196 passed, 1 flaky, 0 failed of 197

## Flaky (passed on retry)
### create, publish, see it in the shop, edit, unpublish and delete
```
Error: expect(locator).toBeVisible() failed

Locator: getByText('Saved', { exact: true })
Expected: visible
Timeout: 10000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 10000ms
  - waiting for getByText('Saved', { exact: true })


at admin-products.spec.ts:45
```
