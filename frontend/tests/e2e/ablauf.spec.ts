import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'

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
  // immer mit demselben Material beginnen (unabhängig vom Bearbeitungsstand der Daten)
  await page.locator('.material', { hasText: '90000001' }).click()
  await expect(page.locator('h1.mat-titel')).toContainText('90000001')
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

test('Bewerten, offene Positionen manuell entscheiden, bestätigen, exportieren', async ({ page }) => {
  await page.locator('.material', { hasText: '90000006' }).click()
  await expect(page.locator('h1.mat-titel')).toContainText('90000006')
  const speichern = page.locator('[data-test="speichern-knopf"]')
  const bestaetigen = page.locator('[data-test="bestaetigen-knopf"]')
  const zeile = (nr: string) => page.locator('.zeile[data-id]', { hasText: nr })
  // Knöpfe sind Umschalter: nur drücken, wenn nicht schon gesetzt (Test läuft auch auf bewerteten Daten)
  const setze = async (nr: string, knopf: string) => {
    const k = zeile(nr).locator(`[data-test="${knopf}"]`)
    if ((await k.getAttribute('aria-pressed')) !== 'true') await k.click()
  }
  // von einem abgebrochenen Lauf noch bestätigt? → erst aufheben
  if (await page.locator('[data-test="aufheben-knopf"]').count()) {
    await page.locator('[data-test="aufheben-knopf"]').click()
    await page.getByRole('dialog').getByRole('button', { name: 'Aufheben' }).click()
    await expect(page.locator('[data-test="aufheben-knopf"]')).toHaveCount(0)
  }
  // regelentschiedene Zeile erst falsch, dann richtig
  await setze('10000020', 'bew-falsch')
  await page.getByRole('button', { name: 'Angezeigte als Richtig' }).click()
  await setze('10000020', 'bew-richtig')
  // offene Positionen: manuell entscheiden
  await setze('10000102', 'bew-rein')
  await setze('10000016', 'bew-falsch')
  if (await speichern.isEnabled()) await speichern.click()
  await expect(speichern).toContainText('Gespeichert')
  await expect(bestaetigen).toBeEnabled()
  await bestaetigen.click()
  await page.getByRole('dialog').getByRole('button', { name: 'Bestätigen', exact: true }).click()
  await expect(page.getByText(/Bestätigt von E2E/)).toBeVisible()
  await expect(zeile('10000020').locator('[data-test="bew-richtig"]')).toBeDisabled()  // gesperrt
  // SAP-Format enthält die manuell hinzugenommene Position
  const [download] = await Promise.all([page.waitForEvent('download'), page.locator('[data-test="export-knopf"]').click()])
  const inhalt = readFileSync(await download.path(), 'utf-8')
  expect(inhalt).toContain(';10000102;')
  expect(inhalt).not.toContain(';10000016;')
  await page.locator('[data-test="aufheben-knopf"]').click()
  await page.getByRole('dialog').getByRole('button', { name: 'Aufheben' }).click()
  await expect(page.getByText(/Bestätigt von E2E/)).toHaveCount(0)
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

test('Kürzel zuordnen und übernehmen (ohne falschen Konflikt)', async ({ page }) => {
  await page.getByRole('tab', { name: /Regeln/ }).click()
  const chip = page.locator('.kuerzel-chip', { hasText: 'ZZ' })
  test.skip((await chip.count()) === 0, 'ZZ ist in diesen Daten schon zugeordnet (Test braucht frische Beispieldaten)')
  await chip.getByRole('button', { name: 'Zuordnen' }).click()
  await page.getByRole('dialog').getByRole('combobox').first().click()
  await page.getByRole('option', { name: /Sitztiefe|SITZTIEFE/ }).first().click()
  await page.getByRole('dialog').getByRole('button', { name: 'Zuordnen' }).click()
  await page.locator('[data-test="uebernehmen-knopf"]').click()
  await page.getByRole('dialog').getByLabel(/Begründung/).fill('ZZ steht für die Sitztiefe (E2E)')
  await page.locator('[data-test="uebernehmen-ok"]').click()
  await expect(page.getByText('Übernommen – die Regeln gelten jetzt für alle.')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Regel-Entwurf' })).toHaveCount(0)
})
