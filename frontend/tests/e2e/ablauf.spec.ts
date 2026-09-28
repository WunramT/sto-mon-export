import { expect, test } from '@playwright/test'

// Ablauf mit den Beispieldaten (tests/fixtures): Anmelden → Material → Regel-Entwurf → Auswirkung → Bewerten
const PASSWORT = process.env.E2E_PASSWORT || 'test'
const basis = (process.env.E2E_BASE_URL || '').replace(/\/$/, '')

test.beforeEach(async ({ page }) => {
  await page.goto(basis + '/')
  await page.evaluate(() => localStorage.clear())
  await page.goto(basis + '/')
  await page.getByLabel('Ihr Name').fill(`E2E ${test.info().title.slice(0, 12)} ${Date.now() % 100000}`)
  await page.getByLabel('Team-Passwort').fill(PASSWORT)
  await page.getByRole('button', { name: 'Anmelden' }).click()
  await expect(page.locator('.zeile[data-id]').first()).toBeVisible()
})

test('falsches Passwort wird abgewiesen', async ({ page }) => {
  await page.locator('[data-test="nutzer-knopf"]').click()
  await page.getByText('Abmelden').click()
  await page.getByLabel('Team-Passwort').fill('falsch')
  await page.getByRole('button', { name: 'Anmelden' }).click()
  await expect(page.getByText('Das Passwort stimmt nicht.')).toBeVisible()
})

test('Material öffnen, Position erklären, Regel als Entwurf setzen', async ({ page }) => {
  await expect(page.locator('h1.mat-titel')).toContainText('90000001')
  await page.locator('.zeile[data-id]', { hasText: '10000102' }).click()
  await expect(page.locator('.details .erklaerung')).toContainText('offene Frage')
  const karte = page.locator('.details [data-merkmal="SITZQUALI"]')
  await karte.locator('.wert-zeile', { hasText: 'FK' }).getByRole('button', { name: 'Basis', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Regel-Entwurf' })).toContainText('1 Änderung')
  await expect(page.locator('.zeile[data-id]', { hasText: '10000102' })).toContainText('Basis')
  await page.getByRole('button', { name: 'Auswirkung auf alle Materialien' }).click()
  await expect(page.getByText(/Ihr Entwurf ändert \d+ Materialien?/)).toBeVisible()
  await page.getByRole('button', { name: 'Verwerfen', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Entwurf verwerfen' }).click()
  await expect(page.getByRole('region', { name: 'Regel-Entwurf' })).toHaveCount(0)
})

test('Zeilen bewerten, speichern und bestätigen', async ({ page }) => {
  await page.locator('.material', { hasText: '90000006' }).click()
  await expect(page.locator('h1.mat-titel')).toContainText('90000006')
  const speichern = page.locator('[data-test="speichern-knopf"]')
  // erste Zeile als falsch markieren und speichern (funktioniert auch, wenn schon bewertet wurde)
  const erste = page.locator('.zeile[data-id]').first()
  await erste.locator('[data-test="bew-falsch"]').click()
  await page.getByRole('button', { name: 'Angezeigte als Richtig' }).click()
  await expect(speichern).toContainText('Speichern (')
  await speichern.click()
  await expect(page.getByText(/Gespeichert: \d+ Zeilen? bewertet/)).toBeVisible()
  await expect(page.locator('[data-test="bestaetigen-knopf"]')).toBeDisabled()
  // korrigieren → alles richtig → bestätigen
  await erste.locator('[data-test="bew-richtig"]').click()
  await speichern.click()
  await expect(speichern).toContainText('Gespeichert')
  await page.locator('[data-test="bestaetigen-knopf"]').click()
  await page.getByRole('dialog').getByRole('button', { name: 'Bestätigen', exact: true }).click()
  await expect(page.getByText(/Bestätigt von E2E/)).toBeVisible()
  await page.getByRole('button', { name: 'aufheben' }).click()
  await expect(page.getByText(/Bestätigt von E2E/)).toHaveCount(0)
})
