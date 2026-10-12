# Fragebogen: Merkmalswerte aus dem Beziehungswissen

**Zweck:** Ihre Rückmeldung war, dass in der Übersicht falsche Merkmalswerte stehen und der Wert aus dem *Text* des Beziehungswissens kommen muss. Bevor wir das umbauen, müssen wir genau verstehen, welcher Text gemeint ist, welche Werte falsch sind und was Sie je Wert sehen möchten. Von Ihren Antworten hängt ab, ob wir einen zusätzlichen SAP-Export brauchen und wie wir die Übersicht ändern.

**Von:** Entwicklung Basis-Stückliste – **An:** Fachbereich (Absender der Rückmeldung) – **Verwendung der Antworten:** Grundlage für die Änderung der Anwendung und, falls nötig, für die Anfrage beim SAP-/Export-Team.

## Kontext

Die Anwendung leitet aus den SAP-Stücklisten die Basis-Version konfigurierbarer Stücklisten ab. Dafür muss sie wissen, unter welcher Bedingung eine Position gilt. In SAP hängt dazu an der Position ein Beziehungswissen. Heute liest die Anwendung den Merkmalswert aus dem **Namen** des Beziehungswissens (z. B. `FUNKTION=VZM0_SH48` → Merkmal FUNKTION, Wert VZM0, Sitzhöhe 48). Diese Werte stehen in der **Übersicht der Regeln**: je Merkmal eine Karte mit allen Werten, ihrer Entscheidung (Basis / Offen / Nie Basis) und der Zahl der Stücklisten, in denen der Wert vorkommt.

Zwei Dinge haben wir schon gefunden:
- `VZMO` (mit dem Buchstaben O) kommt nicht aus SAP. Wir haben ihn aus einem älteren Skript als Startwert übernommen. `VZM0` (mit einer Null) steht dagegen wirklich in den SAP-Daten (6 Stücklisten).
- Zu einem Beziehungswissen gibt es in SAP mehrere Texte: den **Namen** (das nutzen wir heute), eine **Bezeichnung** (Kurztext, laden wir, nutzen ihn aber nicht) und den **Quelltext** (die eigentliche Bedingung, z. B. `FUNKTION = 'VZM0'`; den haben wir bisher nicht).

## So antworten Sie

Bitte bis **[Datum eintragen]** zurück; Aufwand etwa 20–30 Minuten. Halbe Antworten und „weiß ich nicht“ helfen uns ebenfalls. Schreiben Sie Ihre Antwort jeweils hinter das `>` unter der Frage. Wenn Sie unsicher sind, vermerken Sie das, statt die Frage auszulassen.

## Welcher Text gemeint ist

### Welcher Text des Beziehungswissens enthält den richtigen Merkmalswert?

_Warum das wichtig ist: Ist es der Quelltext, müssen wir einen neuen SAP-Export anfordern. Ist es die Bezeichnung, haben wir die Daten schon._

Bitte ankreuzen:
- [ ] Der **Quelltext** (die Bedingung, z. B. `FUNKTION = 'VZM0'`)
- [ ] Die **Bezeichnung** (Kurztext, den man in SAP neben dem Namen sieht)
- [ ] Etwas anderes, nämlich:

>

### Können Sie für ein Beziehungswissen den Namen und den gemeinten Text nebeneinander angeben?

_Warum das wichtig ist: An einem echten Beispiel sehen wir sofort, wo der Unterschied liegt._

Ein Beispiel genügt, gern eines mit VZM0. Format: Name | gemeinter Text.

>

### In welcher SAP-Transaktion oder an welcher Stelle sehen Sie diesen Text?

_Warum das wichtig ist: Damit kann das SAP-Team die richtige Tabelle für den Export finden._

>

### Steht in diesem Text immer genau ein Merkmalswert, oder können es mehrere sein?

_Warum das wichtig ist: Zum Beispiel FUNKTION und Sitzhöhe zusammen. Davon hängt ab, wie wir den Text auswerten._

>

## Welche Werte falsch sind

### Welche Werte in der Übersicht sind falsch?

Bitte je Zeile: Merkmal | falscher Wert | richtiger Wert (falls bekannt). Beispiel: `FUNKTION | VZMO | VZM0`.

>

### Ist VZMO (mit O) ein Tippfehler für VZM0 (mit Null)?

_Warum das wichtig ist: Ist es ein Tippfehler, löschen wir VZMO aus den Startwerten. Wenn nicht, brauchen wir die Bedeutung beider Werte._

- [ ] Ja, gemeint ist VZM0
- [ ] Nein, das sind zwei verschiedene Werte
- [ ] Weiß ich nicht

>

### Woran erkennen Sie in der Übersicht, dass ein Wert falsch ist?

_Warum das wichtig ist: Wenn es eine Regel gibt (z. B. „nur Werte aus der SAP-Werteliste“), kann die Anwendung falsche Werte selbst markieren._

>

### Kommen falsche Werte auch daher, dass ein Name mehrere Merkmale enthält und falsch zerlegt wird?

_Warum das wichtig ist: Ein Beispiel ist `ELEKTRO=FAL_SH48_SQ=HR`. Dann liegt der Fehler beim Zerlegen und nicht nur beim Wert._

>

## Fundstellen je Wert

### Was möchten Sie zu einem Wert sehen, wenn Sie auf die Zahl der Stücklisten klicken?

Bitte ankreuzen, was Sie brauchen:
- [ ] Name des Beziehungswissens
- [ ] Gemeinter Text des Beziehungswissens (siehe oben)
- [ ] Stückliste (Nummer)
- [ ] Kopfmaterial der Stückliste mit Kurztext
- [ ] Position und Komponente, an der die Bedingung hängt
- [ ] Oberstes Material (Modell), in dem die Stückliste verbaut ist
- [ ] Sonstiges:

>

### Wofür nutzen Sie diese Fundstellen?

_Warum das wichtig ist: Zum Prüfen am Bildschirm reicht eine Liste in der Anwendung. Zum Korrigieren in SAP oder zum Weitergeben ist ein Excel-Download sinnvoller._

>

### Sollen Werte, die in keiner Stückliste vorkommen (wie VZMO), in der Übersicht ausgeblendet oder nur markiert werden?

- [ ] Ausblenden
- [ ] Sichtbar lassen, aber als „kommt in den Daten nicht vor“ markieren
- [ ] Unverändert lassen

>

### Sollen Sie in der Übersicht nach einem Wert suchen können, der über mehrere Merkmale hinweg vorkommt?

_Warum das wichtig ist: Heute sucht man nach dem Merkmal. Mit einer Wertsuche fände man „VZM0“ direkt._

>

## Sonst noch etwas?

Gibt es etwas, nach dem wir nicht gefragt haben, das wir wissen sollten? Zum Beispiel weitere Merkmale, bei denen Ihnen Fehler aufgefallen sind, oder Ansprechpartner im SAP-Team.

>
