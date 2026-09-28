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

test('Zeilen bewerten und speichern; offene Positionen sperren das Bestätigen', async ({ page }) => {
  await page.locator('.material', { hasText: '90000006' }).click()
  await expect(page.locator('h1.mat-titel')).toContainText('90000006')
  const speichern = page.locator('[data-test="speichern-knopf"]')
  const erste = page.locator('.zeile[data-id]', { hasText: '10000020' })
  await erste.locator('[data-test="bew-falsch"]').click()
  await page.getByRole('button', { name: 'Angezeigte als Richtig' }).click()
  await expect(page.getByText(/„Manuell prüfen“ bleib(t|en) offen/)).toBeVisible()
  await expect(speichern).toContainText('Speichern (')
  await speichern.click()
  await expect(page.getByText(/Gespeichert: \d+ Zeilen? bewertet/)).toBeVisible()
  await erste.locator('[data-test="bew-richtig"]').click()
  await speichern.click()
  await expect(speichern).toContainText('Gespeichert')
  // 10000102 ist „Manuell prüfen“ → Bestätigen gesperrt, mit Begründung
  await expect(page.locator('[data-test="bestaetigen-knopf"]')).toBeDisabled()
  await expect(page.getByText(/noch „Manuell prüfen“ – erst die offenen Regelfragen klären/)).toBeVisible()
})

test('Entwurf und Bewertungen bleiben beim Personenwechsel getrennt', async ({ page }) => {
  await page.locator('.zeile[data-id]', { hasText: '10000102' }).click()
  const karte = page.locator('.details [data-merkmal="SITZQUALI"]')
  await karte.locator('.wert-zeile', { hasText: 'XX' }).getByRole('button', { name: 'Nie Basis', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Regel-Entwurf' })).toBeVisible()
  await page.waitForTimeout(600)  // Entwurf ist beim Server angekommen
  await page.locator('[data-test="nutzer-knopf"]').click()
  await page.getByText('Abmelden').click()
  await page.getByLabel('Ihr Name').fill(`Andere Person ${Date.now() % 100000}`)
  await page.getByLabel('Team-Passwort').fill(PASSWORT)
  await page.getByRole('button', { name: 'Anmelden' }).click()
  await expect(page.locator('.zeile[data-id]').first()).toBeVisible()
  await expect(page.getByRole('region', { name: 'Regel-Entwurf' })).toHaveCount(0)
})

test('Kommentar erst nach einem Urteil; offene Positionen sind nicht „richtig“', async ({ page }) => {
  await page.locator('.zeile[data-id]', { hasText: '10000002' }).click()
  const kommentar = page.getByLabel('Kommentar')
  await expect(kommentar).toBeDisabled()
  await page.locator('.details [data-test="bew-richtig"]').click()
  await expect(kommentar).toBeEnabled()
  // offene Position: nur „Sollte rein/raus“
  const offen = page.locator('.zeile[data-id]', { hasText: '10000102' })
  await expect(offen.locator('[data-test="bew-richtig"]')).toHaveCount(0)
  await expect(offen.locator('[data-test="bew-rein"]')).toBeVisible()
})

test('Zuklappen wirkt auch bei aktivem Filter', async ({ page }) => {
  await page.getByRole('button', { name: 'Offene', exact: true }).click()
  const zeilen = page.locator('.zeile[data-id]')
  const vorher = await zeilen.count()
  await page.getByRole('button', { name: 'Alle zuklappen' }).click()
  await expect(zeilen).not.toHaveCount(vorher)
})
