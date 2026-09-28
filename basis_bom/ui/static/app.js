"use strict";
/* Basis-Stückliste – Oberfläche für den Fachbereich. Alle Berechnungen macht der Server; hier nur Zustand und Darstellung. */

// ------------------------------------------------------------------------------------------------ Hilfen
const $ = (sel, el = document) => el.querySelector(sel);

function h(tag, attrs = {}, ...kinder) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "html") el.innerHTML = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kind of kinder.flat()) {
    if (kind === null || kind === undefined || kind === false) continue;
    el.append(kind instanceof Node ? kind : document.createTextNode(String(kind)));
  }
  return el;
}

async function api(methode, url, body) {
  const antwort = await fetch(url, {
    method: methode,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const daten = await antwort.json().catch(() => ({}));
  if (!antwort.ok) {
    const fehler = new Error(daten.fehler || `Fehler ${antwort.status}`);
    fehler.status = antwort.status;
    fehler.daten = daten;
    throw fehler;
  }
  return daten;
}

const zahlFormat = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 3 });
const fmtMenge = (m, me) => (m === null || m === undefined ? "–" : `${zahlFormat.format(m)} ${me || ""}`.trim());

function toast(text, fehler = false) {
  const t = $("#toast");
  t.textContent = text;
  t.className = "toast" + (fehler ? " fehler" : "");
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.hidden = true), fehler ? 6000 : 3000);
}

const speicher = {
  lies(k, standard) { try { const v = localStorage.getItem(k); return v === null ? standard : JSON.parse(v); } catch { return standard; } },
  schreib(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* privat */ } },
};

// ------------------------------------------------------------------------------------------------ Texte
const STATUS = {
  basis: { text: "Basis", kurz: "Basis" },
  unbedingt: { text: "Immer enthalten", kurz: "Immer" },
  manuell_prüfen: { text: "Manuell prüfen", kurz: "Prüfen" },
  unterhalb_manuell: { text: "Unter offener Baugruppe", kurz: "Darunter offen" },
  ausgeschlossen: { text: "Nicht in Basis", kurz: "Nicht Basis" },
  ausgeschlossen_vererbt: { text: "Nicht in Basis (Baugruppe)", kurz: "Nicht Basis" },
  ignoriert: { text: "Ignoriert (Text)", kurz: "Ignoriert" },
};
const IM_ERGEBNIS = new Set(["basis", "unbedingt"]);
const OFFEN_STATUS = new Set(["manuell_prüfen", "unterhalb_manuell"]);
const RAUS = new Set(["ausgeschlossen", "ausgeschlossen_vererbt", "ignoriert"]);
const REGEL_STATUS = { BASIS: "Basis", OFFEN: "Offen", NICHT_BASIS: "Nie Basis" };
const ZUSTAND = { offen: "Offen", in_arbeit: "In Arbeit", bestaetigt: "Bestätigt", nicht_aufloesbar: "Nicht auflösbar" };

function statusPill(status, vorher) {
  return h("span", {},
    h("span", { class: `status s-${status}` }, h("span", { class: `punkt p-${status}` }), STATUS[status]?.text || status),
    vorher ? h("span", { class: "vorher" }, `vorher: ${STATUS[vorher]?.text || vorher}`) : null);
}

// ------------------------------------------------------------------------------------------------ Zustand
const S = {
  name: speicher.lies("bb.name", ""),
  meta: null,
  materialien: [],
  zustandFilter: "alle",
  matnr: null,
  daten: null,
  laedt: false,
  auswahl: null,
  ansicht: "stueckliste",
  filter: "alle",
  baumQ: "",
  zu: new Set(),
  entwurf: speicher.lies("bb.entwurf", { regeln: {}, aliasse: {} }),
  basisRegeln: {},
  basisAliasse: {},
  merkmale: {},
  lokal: {},
  lokalErgaenzt: [],
  regelnQ: "",
  regelnNurOffen: true,
  regelnNurMaterial: false,
  regelDaten: null,
  fokusMerkmal: null,
  auswirkung: null,
};

const entwurfPayload = () => ({ regeln: Object.values(S.entwurf.regeln), aliasse: Object.values(S.entwurf.aliasse) });
const entwurfAnzahl = () => Object.keys(S.entwurf.regeln).length + Object.keys(S.entwurf.aliasse).length;
const entwurfLeer = () => entwurfAnzahl() === 0;

function speichereLokal() {
  speicher.schreib("bb.entwurf", S.entwurf);
  if (S.matnr) speicher.schreib(`bb.review.${S.matnr}`, { lokal: S.lokal, ergaenzt: S.lokalErgaenzt });
}

// ------------------------------------------------------------------------------------------------ Laden
async function ladeBasisRegeln() {
  const d = await api("POST", "/api/regeln", { entwurf: null });
  S.basisRegeln = {};
  for (const m of d.merkmale) for (const w of m.werte) S.basisRegeln[`${m.merkmal}|${w.wert}`] = { status: w.status, rang: w.rang };
  S.basisAliasse = {};
  for (const k of d.kuerzel) S.basisAliasse[k.alias] = { merkmal: k.merkmal, status: k.status };
}

async function ladeMeta() {
  S.meta = await api("GET", "/api/meta");
  const m = S.meta;
  $("#meta").textContent = `Datenstand ${new Date(m.stichtag).toLocaleDateString("de-DE")} · ${m.regeln} Regelwerte, davon ${m.offen} offen`;
  $("#offen-zahl").textContent = m.offen || "";
}

async function ladeMaterialien() {
  S.materialien = await api("GET", "/api/materialien");
  zeichneMaterialliste();
}

async function ladeMaterial(matnr, { behalteAuswahl = false } = {}) {
  const neu = matnr !== S.matnr;
  S.matnr = matnr;
  if (neu) {
    S.auswahl = null;
    const r = speicher.lies(`bb.review.${matnr}`, { lokal: {}, ergaenzt: [] });
    S.lokal = r.lokal || {};
    S.lokalErgaenzt = r.ergaenzt || [];
    location.hash = `#/material/${matnr}`;
  }
  S.laedt = true;
  $("#ansicht-stueckliste").classList.add("laedt");
  try {
    const d = await api("POST", `/api/material/${matnr}`, { entwurf: entwurfPayload() });
    S.daten = d;
    for (const m of d.merkmale) S.merkmale[m.merkmal] = m;
    if (neu) {
      S.zu = new Set(d.positionen.filter((p) => p.hat_kinder && RAUS.has(p.status)).map((p) => p.id));
      S.filter = "alle";
    }
    if (!behalteAuswahl && neu) S.auswahl = null;
  } catch (e) {
    S.daten = { fehler: e.message, matnr };
  } finally {
    S.laedt = false;
    $("#ansicht-stueckliste").classList.remove("laedt");
  }
  zeichneMaterialliste();
  zeichne();
}

let neuRechnenTimer = null;
function entwurfGeaendert() {
  speichereLokal();
  zeichneEntwurf();
  S.auswirkung = null;
  clearTimeout(neuRechnenTimer);
  neuRechnenTimer = setTimeout(async () => {
    const aufgaben = [];
    if (S.matnr) aufgaben.push(ladeMaterial(S.matnr, { behalteAuswahl: true }));
    if (S.ansicht === "regeln") aufgaben.push(ladeRegelAnsicht());
    await Promise.all(aufgaben);
    if (S.ansicht === "auswirkung") zeichneAuswirkung();
  }, 120);
}

// ------------------------------------------------------------------------------------------------ Regeln bearbeiten
function merkmalAktuell(merkmal) {
  return S.merkmale[merkmal] || S.regelDaten?.merkmale.find((m) => m.merkmal === merkmal) || null;
}

function wendeAn(merkmal, werte) {
  // Ränge der Basis-Werte lückenlos 1..n in der gegebenen Reihenfolge; Entwurf = Abweichung vom übernommenen Stand
  const basis = werte.filter((w) => w.status === "BASIS").sort((a, b) => (a.rang ?? 999) - (b.rang ?? 999));
  basis.forEach((w, i) => (w.rang = i + 1));
  for (const w of werte) {
    if (w.status !== "BASIS") w.rang = null;
    const key = `${merkmal}|${w.wert}`;
    const vorher = S.basisRegeln[key] || { status: "OFFEN", rang: null };
    if (vorher.status === w.status && (vorher.rang ?? null) === (w.rang ?? null)) delete S.entwurf.regeln[key];
    else S.entwurf.regeln[key] = { merkmal, wert: w.wert, status: w.status, rang: w.rang, vorher };
  }
  const m = merkmalAktuell(merkmal);
  if (m) m.werte = werte;
  entwurfGeaendert();
}

function setzeStatus(merkmal, wert, status) {
  const m = merkmalAktuell(merkmal);
  if (!m) return;
  const werte = m.werte.map((w) => ({ ...w }));
  const w = werte.find((x) => x.wert === wert);
  if (!w || w.status === status) return;
  if (status === "BASIS") w.rang = Math.max(0, ...werte.filter((x) => x.status === "BASIS").map((x) => x.rang || 0)) + 1;
  w.status = status;
  wendeAn(merkmal, werte);
}

function verschiebe(merkmal, wert, richtung) {
  const m = merkmalAktuell(merkmal);
  const werte = m.werte.map((w) => ({ ...w }));
  const basis = werte.filter((w) => w.status === "BASIS").sort((a, b) => a.rang - b.rang);
  const i = basis.findIndex((w) => w.wert === wert);
  const j = i + richtung;
  if (i < 0 || j < 0 || j >= basis.length) return;
  [basis[i].rang, basis[j].rang] = [basis[j].rang, basis[i].rang];
  wendeAn(merkmal, werte);
}

function setzeKuerzel(alias, merkmal, status) {
  const vorher = S.basisAliasse[alias] || { merkmal: null, status: "OFFEN" };
  if ((vorher.merkmal || null) === (merkmal || null) && vorher.status === status) delete S.entwurf.aliasse[alias];
  else S.entwurf.aliasse[alias] = { alias, merkmal: merkmal || null, status, vorher };
  entwurfGeaendert();
}

function entwurfEintragText(e) {
  if (e.alias) return `Kürzel ${e.alias} → ${e.merkmal || "–"}`;
  const s = e.status === "BASIS" ? `Basis (Rang ${e.rang})` : REGEL_STATUS[e.status];
  const v = e.vorher.status === "BASIS" ? `Basis (Rang ${e.vorher.rang})` : REGEL_STATUS[e.vorher.status];
  const w = e.wert === "vorhanden" ? "" : ` = ${e.wert}`;
  return `${e.merkmal}${w}: ${v} → ${s}`;
}

function merkmalKarte(m, { hierWerte = null, gewaehlt, hervor = false } = {}) {
  const imEntwurf = (w) => Boolean(S.entwurf.regeln[`${m.merkmal}|${w}`]);
  const basisWerte = m.werte.filter((w) => w.status === "BASIS").sort((a, b) => a.rang - b.rang);
  let art = "Rangfolge: der Basiswert mit dem kleinsten Rang gewinnt";
  if (m.systemregel) art = "Technische Regel – gilt sie in der Basis?";
  if (m.sitzhoehe) art = "Automatisch: der niedrigste vorkommende Wert gewinnt";
  const karte = h("div", { class: "merkmal-karte" + (hervor ? " hervor" : ""), "data-merkmal": m.merkmal },
    h("div", { class: "merkmal-kopf" },
      h("div", {}, h("div", { class: "mname" }, m.merkmal), h("div", { class: "art" }, art)),
      gewaehlt !== undefined ? h("span", { class: "status " + (gewaehlt ? "s-basis" : "s-manuell_prüfen") },
        gewaehlt ? `hier gewählt: ${gewaehlt === "vorhanden" ? "gilt" : gewaehlt}` : "hier: noch kein Basiswert") : null));
  const werte = [...m.werte];
  if (hierWerte) werte.sort((a, b) => (hierWerte.has(b.wert) - hierWerte.has(a.wert)));
  for (const w of werte) {
    const i = basisWerte.findIndex((x) => x.wert === w.wert);
    const knoepfe = m.systemregel
      ? [["BASIS", "Gilt", "b"], ["OFFEN", "Offen", "o"], ["NICHT_BASIS", "Gilt nicht", "n"]]
      : m.sitzhoehe
        ? [["OFFEN", "Erlaubt", "o"], ["NICHT_BASIS", "Nie Basis", "n"]]
        : [["BASIS", "Basis", "b"], ["OFFEN", "Offen", "o"], ["NICHT_BASIS", "Nie Basis", "n"]];
    const hier = hierWerte && hierWerte.has(w.wert);
    karte.append(h("div", { class: "wert-zeile" + (imEntwurf(w.wert) ? " im-entwurf" : "") },
      h("div", { class: "rang" + (w.status === "BASIS" ? "" : " kein"), title: w.status === "BASIS" ? "Rang" : "" },
        w.status === "BASIS" && !m.sitzhoehe ? w.rang : "–"),
      h("div", { class: "wname" }, m.systemregel ? "Regel aktiv" : w.wert,
        hier ? h("small", {}, gewaehlt === w.wert ? "★ hier gewählt" : "kommt hier vor") : (w.vorkommen ? h("small", {}, `${w.vorkommen}× im Material`) : null)),
      h("div", { class: "status-wahl", role: "group", "aria-label": `Status für ${m.merkmal} ${w.wert}` },
        knoepfe.map(([st, text, cls]) => h("button", {
          type: "button", class: (w.status === st ? `an ${cls}` : ""), "aria-pressed": w.status === st ? "true" : "false",
          onclick: (ev) => { ev.stopPropagation(); setzeStatus(m.merkmal, w.wert, st); },
        }, text))),
      h("div", { class: "pfeile" },
        h("button", { type: "button", title: "Rang verbessern (nach oben)", "aria-label": "Rang verbessern", disabled: w.status !== "BASIS" || i <= 0 || m.systemregel || m.sitzhoehe,
          onclick: (ev) => { ev.stopPropagation(); verschiebe(m.merkmal, w.wert, -1); } }, "▲"),
        h("button", { type: "button", title: "Rang verschlechtern (nach unten)", "aria-label": "Rang verschlechtern", disabled: w.status !== "BASIS" || i < 0 || i >= basisWerte.length - 1 || m.systemregel || m.sitzhoehe,
          onclick: (ev) => { ev.stopPropagation(); verschiebe(m.merkmal, w.wert, 1); } }, "▼"))));
  }
  return karte;
}

// ------------------------------------------------------------------------------------------------ Zeichnen: Kopf, Entwurf, Liste
function zeichneEntwurf() {
  const n = entwurfAnzahl();
  $("#entwurf-leiste").hidden = n === 0;
  $("#entwurf-text").textContent = n === 1 ? "1 Änderung" : `${n} Änderungen`;
  const box = $("#entwurf-aenderungen");
  box.replaceChildren(...[...Object.values(S.entwurf.regeln), ...Object.values(S.entwurf.aliasse)].map((e) =>
    h("span", { class: "chip" }, entwurfEintragText(e),
      h("button", { type: "button", title: "Diese Änderung zurücknehmen", "aria-label": "zurücknehmen", onclick: () => {
        if (e.alias) delete S.entwurf.aliasse[e.alias]; else delete S.entwurf.regeln[`${e.merkmal}|${e.wert}`];
        entwurfGeaendert();
      } }, "✕"))));
  $("#nutzer-knopf").textContent = S.name || "Name eingeben";
}

function zeichneMaterialliste() {
  const q = $("#material-suche").value.trim().toUpperCase();
  const zaehler = { alle: S.materialien.length };
  for (const m of S.materialien) zaehler[m.zustand] = (zaehler[m.zustand] || 0) + 1;
  $("#zustand-filter").replaceChildren(...["alle", "offen", "in_arbeit", "bestaetigt", "nicht_aufloesbar"].filter((z) => z === "alle" || zaehler[z]).map((z) =>
    h("button", { type: "button", class: "filter-knopf" + (S.zustandFilter === z ? " aktiv" : ""), onclick: () => { S.zustandFilter = z; zeichneMaterialliste(); } },
      `${z === "alle" ? "Alle" : ZUSTAND[z]} ${zaehler[z] || 0}`)));
  const liste = S.materialien.filter((m) => (S.zustandFilter === "alle" || m.zustand === S.zustandFilter) &&
    (!q || m.matnr.includes(q) || (m.kurztext || "").toUpperCase().includes(q)));
  $("#materialliste").replaceChildren(...(liste.length ? liste.map((m) =>
    h("li", {}, h("button", { type: "button", class: "material" + (m.matnr === S.matnr ? " aktiv" : ""), onclick: () => oeffneMaterial(m.matnr) },
      h("span", { class: `zustand ${m.zustand}` }, ZUSTAND[m.zustand]),
      h("span", { class: "nr" }, m.matnr),
      h("span", { class: "text" }, m.kurztext || m.grund || "")))) : [h("li", { class: "leer-hinweis" }, "Keine Materialien gefunden.")]));
}

function oeffneMaterial(matnr) {
  wechsleAnsicht("stueckliste");
  ladeMaterial(matnr);
}

// ------------------------------------------------------------------------------------------------ Stückliste
function urteilVon(id) {
  if (S.lokal[id] !== undefined) return S.lokal[id];
  return S.daten?.review?.urteile?.[id] || null;
}

function sichtbarePositionen() {
  const d = S.daten;
  const q = S.baumQ.trim().toUpperCase();
  const passt = (p) => {
    if (q && !(p.matnr.includes(q) || (p.kurztext || "").toUpperCase().includes(q))) return false;
    if (S.filter === "offen") return OFFEN_STATUS.has(p.status);
    if (S.filter === "ergebnis") return IM_ERGEBNIS.has(p.status);
    if (S.filter === "geaendert") return Boolean(p.vorher);
    if (S.filter === "unbewertet") return !urteilVon(p.id);
    return true;
  };
  const gefiltert = S.filter !== "alle" || q;
  const nachId = new Map(d.positionen.map((p) => [p.id, p]));
  const treffer = new Set(d.positionen.filter(passt).map((p) => p.id));
  const zeigen = new Set(treffer);
  if (gefiltert) for (const id of treffer) { let p = nachId.get(id); while (p && nachId.has(p.parent)) { zeigen.add(p.parent); p = nachId.get(p.parent); } }
  const kinder = new Map();
  for (const p of d.positionen) { if (!kinder.has(p.parent)) kinder.set(p.parent, []); kinder.get(p.parent).push(p); }
  const reihenfolge = [];
  const lauf = (parent) => {
    for (const p of kinder.get(parent) || []) {
      if (!zeigen.has(p.id)) continue;
      reihenfolge.push({ p, kontext: gefiltert && !treffer.has(p.id) });
      if (!S.zu.has(p.id) || gefiltert) lauf(p.id);
    }
  };
  lauf(d.matnr);
  return { reihenfolge, treffer: treffer.size };
}

function bewertungsKnoepfe(p) {
  const u = urteilVon(p.id);
  const gesperrt = !entwurfLeer();
  const titelSperre = "Erst den Entwurf übernehmen oder verwerfen – bewertet wird der gespeicherte Regelstand.";
  const imErg = IM_ERGEBNIS.has(p.status);
  const zweit = imErg ? ["gehoert_nicht_rein", "Raus", "Gehört nicht in die Basis-Stückliste"] : ["fehlt", "Rein", "Gehört in die Basis-Stückliste, fehlt aber"];
  const knopf = (urteil, text, titel, cls) => h("button", {
    type: "button", class: "bew" + (u?.urteil === urteil ? ` an ${cls}` : ""), disabled: gesperrt, title: gesperrt ? titelSperre : titel,
    "aria-pressed": u?.urteil === urteil ? "true" : "false",
    onclick: (ev) => { ev.stopPropagation(); setzeUrteil(p.id, u?.urteil === urteil ? null : urteil); },
  }, text);
  return h("div", { class: "bewertung" }, knopf("richtig", "✓ Stimmt", "Der Status dieser Zeile ist richtig", "ok"), knopf(zweit[0], zweit[1], zweit[2], "nein"));
}

function setzeUrteil(id, urteil) {
  const alt = S.daten?.review?.urteile?.[id];
  if (urteil === null) {
    if (alt) S.lokal[id] = null; else delete S.lokal[id];
  } else {
    const kommentar = S.lokal[id]?.kommentar ?? alt?.kommentar ?? null;
    S.lokal[id] = { urteil, kommentar };
    if (alt && alt.urteil === urteil && (alt.kommentar || null) === (kommentar || null)) delete S.lokal[id];
  }
  speichereLokal();
  zeichneStueckliste();
  if (S.auswahl === id) zeichneDetails();
}

function reviewStand() {
  const d = S.daten;
  const alle = d.positionen.length;
  let bewertet = 0, richtig = 0;
  for (const p of d.positionen) { const u = urteilVon(p.id); if (u) { bewertet++; if (u.urteil === "richtig") richtig++; } }
  const ungespeichert = Object.keys(S.lokal).length + S.lokalErgaenzt.length;
  const ergaenzt = (d.review?.ergaenzt?.length || 0) + S.lokalErgaenzt.length;
  return { alle, bewertet, richtig, ungespeichert, ergaenzt };
}

function zeichneStueckliste() {
  const box = $("#ansicht-stueckliste");
  const d = S.daten;
  if (!d) {
    box.replaceChildren(h("div", { class: "leer-hinweis" }, "Links ein Material wählen."));
    return;
  }
  if (d.fehler) {
    box.replaceChildren(h("div", { class: "leer-hinweis" }, h("strong", {}, d.matnr), h("p", {}, d.fehler)));
    return;
  }
  const z = d.zaehler;
  const n = (...st) => st.reduce((s, k) => s + (z[k] || 0), 0);
  const rs = reviewStand();
  const kennzahl = (cls, wert, name, filter, titel) => h("button", { type: "button", class: `kennzahl ${cls}`, title: titel, onclick: () => { S.filter = S.filter === filter ? "alle" : filter; zeichneStueckliste(); } },
    h("div", { class: "wert" }, wert), h("div", { class: "name" }, name));
  const kopf = h("div", { class: "mat-kopf" },
    h("div", { class: "mat-titel" }, h("h1", {}, d.matnr, h("small", {}, d.kurztext)),
      d.review?.bestaetigt ? h("span", { class: "status s-basis" }, `✓ Bestätigt von ${d.review.bestaetigt.von} am ${new Date(d.review.bestaetigt.datum).toLocaleDateString("de-DE")}`) : null),
    h("div", { class: "kennzahlen" },
      kennzahl("basis", n("basis", "unbedingt"), "in der Basis-Stückliste", "ergebnis", "Nur Positionen zeigen, die in die Basis-Stückliste kommen"),
      kennzahl("manuell", n("manuell_prüfen", "unterhalb_manuell"), "offen – manuell prüfen", "offen", "Nur offene Positionen zeigen"),
      kennzahl("aus", n("ausgeschlossen", "ausgeschlossen_vererbt", "ignoriert"), "nicht in der Basis", "alle", "Alle zeigen"),
      !entwurfLeer() ? kennzahl("entwurf", d.geaendert, "durch Entwurf geändert", "geaendert", "Nur durch den Entwurf geänderte Positionen zeigen") : null),
    h("div", { class: "werkzeuge" },
      h("div", { class: "segment", role: "group", "aria-label": "Ansicht filtern" },
        [["alle", "Alle"], ["offen", "Offene"], ["ergebnis", "Basis-Ergebnis"], ["unbewertet", "Unbewertet"], ...(entwurfLeer() ? [] : [["geaendert", "Geändert"]])].map(([f, t]) =>
          h("button", { type: "button", class: S.filter === f ? "aktiv" : "", "aria-pressed": S.filter === f ? "true" : "false", onclick: () => { S.filter = f; zeichneStueckliste(); } }, t))),
      h("input", { class: "baum-suche", type: "search", placeholder: "In Stückliste suchen", value: S.baumQ,
        oninput: (ev) => { S.baumQ = ev.target.value; zeichneBaum(); } }),
      h("button", { type: "button", class: "knopf leise klein", onclick: () => { S.zu.clear(); zeichneStueckliste(); } }, "Alles aufklappen"),
      h("button", { type: "button", class: "knopf leise klein", onclick: () => { S.zu = new Set(d.positionen.filter((p) => p.hat_kinder).map((p) => p.id)); zeichneStueckliste(); } }, "Alles zuklappen")),
    h("div", { class: "review-leiste" },
      h("div", { class: "fortschritt" },
        h("div", {}, `Bewertet: ${rs.bewertet} von ${rs.alle}` + (rs.ungespeichert ? ` · ${rs.ungespeichert} nicht gespeichert` : "") + (rs.ergaenzt ? ` · ${rs.ergaenzt} ergänzt` : "")),
        h("div", { class: "balken" }, h("div", { style: `width:${rs.alle ? Math.round((100 * rs.bewertet) / rs.alle) : 0}%` }))),
      h("button", { type: "button", class: "knopf klein", disabled: !entwurfLeer(), title: "Alle aktuell angezeigten Zeilen ohne Urteil als „Stimmt“ markieren",
        onclick: alleSichtbarenRichtig }, "Angezeigte ohne Urteil: ✓ Stimmt"),
      h("button", { type: "button", class: "knopf klein", disabled: !rs.ungespeichert || !entwurfLeer(), onclick: speichereReview }, "Bewertung speichern"),
      h("button", { type: "button", class: "knopf haupt klein", disabled: !bestaetigbar(rs), title: bestaetigbar(rs) ? "Material als geprüft markieren" : "Möglich, wenn alle Zeilen gespeichert mit „Stimmt“ bewertet sind",
        onclick: bestaetige }, "Material bestätigen")),
    !entwurfLeer() ? h("div", { class: "hinweis" }, "Du siehst die Vorschau deines Entwurfs. Bewerten ist erst nach „Übernehmen“ oder „Verwerfen“ möglich.") : null,
    d.review?.veraltet ? h("div", { class: "hinweis" }, `Seit der letzten Bewertung haben sich Regeln geändert: ${d.review.veraltet} Positionen haben jetzt einen anderen Status. Bitte diese Zeilen neu bewerten.`) : null,
    d.warnungen?.length ? h("div", { class: "hinweis info" }, d.warnungen.join(" · ")) : null);
  box.replaceChildren(kopf, h("div", { class: "baum", id: "baum" }));
  zeichneBaum();
}

function zeichneBaum() {
  const baum = $("#baum");
  if (!baum) return;
  const { reihenfolge } = sichtbarePositionen();
  const zeilen = reihenfolge.map(({ p, kontext }) => {
    const raus = RAUS.has(p.status);
    return h("div", {
      class: "zeile" + (S.auswahl === p.id ? " gewaehlt" : "") + (p.vorher ? " geaendert" : "") + (raus ? " raus" : ""),
      role: "treeitem", tabindex: S.auswahl === p.id ? "0" : "-1", "data-id": p.id, "aria-level": p.ebene,
      "aria-expanded": p.hat_kinder ? String(!S.zu.has(p.id)) : null, style: kontext ? "opacity:.55" : null,
      onclick: () => waehle(p.id),
    },
      h("div", { class: "name" },
        h("span", { class: "einzug", style: `width:${(p.ebene - 1) * 18}px` }),
        h("button", { type: "button", class: "pfeil" + (p.hat_kinder ? "" : " leer"), "aria-label": S.zu.has(p.id) ? "aufklappen" : "zuklappen", tabindex: "-1",
          onclick: (ev) => { ev.stopPropagation(); if (S.zu.has(p.id)) S.zu.delete(p.id); else S.zu.add(p.id); zeichneBaum(); } }, S.zu.has(p.id) ? "▶" : "▼"),
        h("span", { class: `punkt p-${p.status}` }),
        h("span", { class: "name-text" }, h("span", { class: "pos" }, p.posnr), h("span", { class: "mat" }, p.matnr || (p.postp === "K" ? "Klassenposition" : "Textposition")),
          h("span", { class: "kt" }, p.kurztext))),
      h("div", { class: "menge" }, fmtMenge(p.menge_kum, p.meins)),
      h("div", {}, statusPill(p.status, p.vorher)),
      bewertungsKnoepfe(p));
  });
  const ergaenzt = [...(S.daten.review?.ergaenzt || []), ...S.lokalErgaenzt.map((e) => ({ ...e, lokal: true }))];
  const zusatz = ergaenzt.length ? [h("div", { class: "gruppen-titel" }, "Als fehlend ergänzt"), ...ergaenzt.map((e, i) =>
    h("div", { class: "zeile" },
      h("div", { class: "name" }, h("span", { class: "punkt p-basis" }), h("span", { class: "name-text" }, h("span", { class: "mat" }, e.matnr),
        h("span", { class: "kt" }, `unter ${e.parent_matnr || (e.parent_pfad || "").split("/").pop().split(":").pop()}` + (e.kommentar ? ` – ${e.kommentar}` : "")))),
      h("div", { class: "menge" }, e.menge ?? "–"),
      h("div", {}, h("span", { class: "status s-basis" }, e.lokal ? "ergänzt (nicht gespeichert)" : "ergänzt")),
      h("div", { class: "bewertung" }, e.lokal ? h("button", { type: "button", class: "bew", onclick: () => { S.lokalErgaenzt.splice(i - (S.daten.review?.ergaenzt?.length || 0), 1); speichereLokal(); zeichneStueckliste(); } }, "Entfernen") : null)))] : [];
  baum.replaceChildren(h("div", { class: "baum-kopf", role: "presentation" }, h("div", {}, "Position · Material"), h("div", { style: "text-align:right" }, "Menge"), h("div", {}, "Status"), h("div", { style: "text-align:right" }, "Bewertung")),
    ...(zeilen.length ? zeilen : [h("div", { class: "leer-hinweis" }, "Keine Positionen für diesen Filter.")]), ...zusatz);
  baum.setAttribute("role", "tree");
}

function waehle(id) {
  S.auswahl = id;
  S.fokusMerkmal = null;
  zeichneBaum();
  zeichneDetails();
  const el = document.querySelector(`.zeile[data-id="${CSS.escape(id)}"]`);
  if (el) el.focus({ preventScroll: false });
}

function alleSichtbarenRichtig() {
  const { reihenfolge } = sichtbarePositionen();
  let n = 0;
  for (const { p, kontext } of reihenfolge) if (!kontext && !urteilVon(p.id)) { S.lokal[p.id] = { urteil: "richtig", kommentar: null }; n++; }
  speichereLokal();
  zeichneStueckliste();
  toast(n ? `${n} Zeilen als „Stimmt“ markiert – noch nicht gespeichert.` : "Alle angezeigten Zeilen haben schon ein Urteil.");
}

function bestaetigbar(rs) {
  const d = S.daten;
  if (!d || rs.ungespeichert || !entwurfLeer() || d.review?.veraltet || rs.ergaenzt) return false;
  return d.positionen.every((p) => d.review?.urteile?.[p.id]?.urteil === "richtig");
}

async function speichereReview() {
  if (!(await brauchtName())) return;
  const d = S.daten;
  const urteile = {};
  for (const p of d.positionen) { const u = urteilVon(p.id); if (u) urteile[p.id] = u; }
  const ergaenzt = [...(d.review?.ergaenzt || []).map((e) => ({ parent_pfad: e.pfad.split("/+:")[0], matnr: e.matnr, menge: e.menge, kommentar: e.kommentar })), ...S.lokalErgaenzt];
  try {
    const r = await api("POST", `/api/review/${d.matnr}`, { von: S.name, urteile, ergaenzt });
    S.lokal = {};
    S.lokalErgaenzt = [];
    speichereLokal();
    toast(`Bewertung gespeichert (${r.urteile} Zeilen${r.ergaenzt ? `, ${r.ergaenzt} ergänzt` : ""}).`);
    await Promise.all([ladeMaterial(d.matnr, { behalteAuswahl: true }), ladeMaterialien()]);
  } catch (e) { toast(e.message, true); }
}

async function bestaetige() {
  if (!(await brauchtName())) return;
  try {
    await api("POST", `/api/bestaetigen/${S.daten.matnr}`, { von: S.name });
    toast("Material bestätigt – es dient ab jetzt als Referenz für spätere Läufe.");
    await Promise.all([ladeMaterial(S.daten.matnr, { behalteAuswahl: true }), ladeMaterialien()]);
  } catch (e) { toast(e.message, true); }
}

// ------------------------------------------------------------------------------------------------ Details
function zeichneDetails() {
  const box = $("#details");
  const d = S.daten;
  if (!d || d.fehler) { box.replaceChildren(h("div", { class: "details" }, h("p", { class: "unter" }, "Hier erscheinen Details zur gewählten Position."))); return; }
  const p = d.positionen.find((x) => x.id === S.auswahl);
  if (!p) { box.replaceChildren(materialUebersicht()); return; }
  const u = urteilVon(p.id);
  const ebene = d.ebenen[p.stlnr];
  const merkmaleHier = [...new Set(p.bedingungen.flatMap((b) => b.pruefungen.map((x) => x.merkmal)))];
  const inhalt = h("div", { class: "details" },
    h("h2", {}, p.matnr || (p.postp === "K" ? "Klassenposition" : "Position"), p.kurztext ? h("span", { style: "font-weight:400;color:var(--text-2)" }, ` ${p.kurztext}`) : null),
    h("div", { class: "unter" }, `Position ${p.posnr} · Ebene ${p.ebene}`),
    h("div", {}, statusPill(p.status, p.vorher)),
    h("div", { class: "abschnitt" }, h("div", { class: "erklaerung" }, p.erklaerung)),
    p.fragen.length ? h("div", { class: "abschnitt" }, h("h3", {}, "Offene Fragen"), ...p.fragen.map((f) => frageZeile(f))) : null,
    merkmaleHier.length ? h("div", { class: "abschnitt" }, h("h3", {}, "Regeln für diese Position"),
      h("p", { class: "unter", style: "margin:0 0 6px" }, "Änderungen wirken sofort als Entwurf – der Baum zeigt die Folgen."),
      ...merkmaleHier.map((mn) => {
        const m = S.merkmale[mn];
        if (!m) return null;
        const hier = new Set((ebene?.kandidaten?.[mn] || []).map((k) => k.wert));
        return merkmalKarte(m, { hierWerte: hier, gewaehlt: ebene ? ebene.gewaehlt[mn] ?? (mn in (ebene.gewaehlt || {}) ? null : null) : undefined, hervor: S.fokusMerkmal === mn });
      })) : null,
    h("div", { class: "abschnitt" }, h("h3", {}, "Bewertung"),
      !entwurfLeer() ? h("p", { class: "unter" }, "Erst den Entwurf übernehmen oder verwerfen.") : null,
      h("div", { style: "display:flex;gap:6px;margin-bottom:6px" }, bewertungsKnoepfe(p)),
      h("textarea", { placeholder: "Kommentar (optional)", disabled: !entwurfLeer(), "aria-label": "Kommentar",
        oninput: (ev) => { const cur = urteilVon(p.id); S.lokal[p.id] = { urteil: cur?.urteil || "richtig", kommentar: ev.target.value }; speichereLokal(); } }, u?.kommentar || ""),
      p.hat_kinder || true ? ergaenzenFormular(p) : null),
    h("div", { class: "abschnitt" }, h("h3", {}, "Bedingungen (SAP)"),
      p.bedingungen.length ? p.bedingungen.map((b) => h("div", { class: "bedingung" },
        h("div", { class: "roh" }, b.name, b.rolle === "prozedur_ignoriert" ? " · Prozedur, wird ignoriert" : ""),
        ...b.pruefungen.map((x) => h("div", { class: "pruefung" },
          h("span", { class: `ergebnis e-${x.ergebnis}` }, x.ergebnis === "passt" ? "passt" : x.ergebnis === "passt_nicht" ? "passt nicht" : "offen"),
          h("span", {}, x.wert === "vorhanden" ? `${x.merkmal}` : `${x.merkmal} = ${x.wert.replace("≠", "≠ ")}`))),
        b.fehler ? h("div", { class: "pruefung" }, h("span", { class: "ergebnis e-manuell" }, "unlesbar"), b.fehler) : null))
        : h("p", { class: "unter" }, "Keine Bedingung – die Position ist immer enthalten."),
      p.prozeduren.length ? h("p", { class: "unter" }, `Ignorierte Prozeduren: ${p.prozeduren.join(", ")}`) : null),
    h("div", { class: "abschnitt" }, h("h3", {}, "Daten"),
      h("dl", { class: "kv" },
        h("dt", {}, "Menge"), h("dd", {}, fmtMenge(p.menge, p.meins)),
        h("dt", {}, "Menge gesamt"), h("dd", {}, fmtMenge(p.menge_kum, p.meins)),
        h("dt", {}, "Stückliste"), h("dd", {}, p.stlnr),
        h("dt", {}, "Positionstyp"), h("dd", {}, p.postp || "–"))));
  box.replaceChildren(inhalt);
  if (S.fokusMerkmal) { const k = box.querySelector(`[data-merkmal="${CSS.escape(S.fokusMerkmal)}"]`); if (k) k.scrollIntoView({ block: "center" }); }
}

function frageZeile(f) {
  if (f.typ === "rang") return h("div", { class: "frage" }, h("span", {}, f.text), h("button", { type: "button", class: "knopf klein", onclick: () => { S.fokusMerkmal = f.merkmal; zeichneDetails(); } }, "Festlegen"));
  if (f.typ === "kuerzel") return h("div", { class: "frage" }, h("span", {}, f.text), h("button", { type: "button", class: "knopf klein", onclick: () => kuerzelDialog(f.alias) }, "Zuordnen"));
  return h("div", { class: "frage" }, h("span", {}, f.text));
}

function ergaenzenFormular(p) {
  const f = h("details", { style: "margin-top:10px" }, h("summary", {}, "Fehlendes Material unter dieser Position ergänzen"),
    h("div", { style: "display:grid;grid-template-columns:1fr 90px;gap:6px;margin-top:6px" },
      h("input", { type: "text", placeholder: "Materialnummer", "aria-label": "Materialnummer", disabled: !entwurfLeer() }),
      h("input", { type: "number", placeholder: "Menge", min: "0", step: "any", "aria-label": "Menge", disabled: !entwurfLeer() })),
    h("input", { type: "text", placeholder: "Kommentar", "aria-label": "Kommentar zum ergänzten Material", style: "width:100%;margin-top:6px", disabled: !entwurfLeer() }),
    h("button", { type: "button", class: "knopf klein", style: "margin-top:6px", disabled: !entwurfLeer(), onclick: () => {
      const [nr, menge, kommentar] = f.querySelectorAll("input");
      if (!nr.value.trim()) { toast("Bitte eine Materialnummer eintragen.", true); return; }
      S.lokalErgaenzt.push({ parent_pfad: p.id, parent_matnr: p.matnr, matnr: nr.value.trim(), menge: menge.value ? Number(menge.value) : null, kommentar: kommentar.value.trim() || null });
      speichereLokal();
      zeichneStueckliste();
      toast("Ergänzt – noch nicht gespeichert.");
    } }, "Ergänzen"));
  return f;
}

function materialUebersicht() {
  const d = S.daten;
  const fragen = new Map();
  for (const p of d.positionen) for (const f of p.fragen) {
    const key = `${f.typ}|${f.merkmal || f.alias || f.text}`;
    if (!fragen.has(key)) fragen.set(key, { ...f, anzahl: 0, beispiel: p.id });
    fragen.get(key).anzahl++;
  }
  const liste = [...fragen.values()].sort((a, b) => b.anzahl - a.anzahl);
  return h("div", { class: "details" },
    h("h2", {}, "Was ist zu tun?"),
    h("p", { class: "unter" }, "Wähle im Baum eine Position, um zu sehen, warum sie diesen Status hat."),
    liste.length ? h("div", { class: "abschnitt" }, h("h3", {}, `Offene Fragen in diesem Material (${liste.length})`),
      ...liste.map((f) => h("div", { class: "frage" }, h("span", {}, f.text, h("br"), h("small", { style: "color:var(--text-2)" }, `betrifft ${f.anzahl} Position${f.anzahl === 1 ? "" : "en"}`)),
        f.typ === "unlesbar" ? h("button", { type: "button", class: "knopf klein", onclick: () => waehle(f.beispiel) }, "Zeigen")
          : h("button", { type: "button", class: "knopf klein", onclick: () => { if (f.typ === "kuerzel") kuerzelDialog(f.alias); else { S.auswahl = f.beispiel; S.fokusMerkmal = f.merkmal; zeichneBaum(); zeichneDetails(); } } }, f.typ === "kuerzel" ? "Zuordnen" : "Festlegen"))))
      : h("div", { class: "hinweis gut" }, "Keine offenen Regelfragen in diesem Material."),
    h("div", { class: "abschnitt" }, h("h3", {}, "So geht's"),
      h("ol", { class: "einfach" },
        h("li", {}, "Offene Fragen klären: Basiswerte festlegen – der Baum rechnet sofort neu."),
        h("li", {}, "Mit „Auswirkung auf alle Materialien“ prüfen, was der Entwurf sonst ändert."),
        h("li", {}, "„Übernehmen“ speichert die Regeln für alle."),
        h("li", {}, "Zeilen bewerten, speichern und das Material bestätigen."))));
}

// ------------------------------------------------------------------------------------------------ Regel-Ansicht
async function ladeRegelAnsicht() {
  const d = await api("POST", `/api/regeln?q=${encodeURIComponent(S.regelnQ)}&nur_offen=${S.regelnNurOffen}`, { entwurf: entwurfPayload() });
  S.regelDaten = d;
  for (const m of d.merkmale) if (!S.merkmale[m.merkmal] || !S.daten?.merkmale?.some((x) => x.merkmal === m.merkmal)) S.merkmale[m.merkmal] = m;
  zeichneRegeln();
}

function zeichneRegeln() {
  const box = $("#ansicht-regeln");
  const d = S.regelDaten;
  let merkmale = d ? d.merkmale : [];
  if (S.regelnNurMaterial && S.daten?.merkmale) { const hier = new Set(S.daten.merkmale.map((m) => m.merkmal)); merkmale = merkmale.filter((m) => hier.has(m.merkmal)); }
  box.replaceChildren(
    h("div", { class: "regel-werkzeuge" },
      h("input", { class: "baum-suche", type: "search", placeholder: "Merkmal suchen", value: S.regelnQ, style: "width:240px",
        oninput: (ev) => { S.regelnQ = ev.target.value; clearTimeout(zeichneRegeln._t); zeichneRegeln._t = setTimeout(ladeRegelAnsicht, 200); } }),
      h("label", {}, h("input", { type: "checkbox", checked: S.regelnNurOffen, onchange: (ev) => { S.regelnNurOffen = ev.target.checked; ladeRegelAnsicht(); } }), " nur Merkmale mit offenen Werten"),
      S.daten?.merkmale ? h("label", {}, h("input", { type: "checkbox", checked: S.regelnNurMaterial, onchange: (ev) => { S.regelnNurMaterial = ev.target.checked; zeichneRegeln(); } }), ` nur Merkmale aus ${S.daten.matnr}`) : null,
      h("span", { class: "unter", style: "margin-left:auto;color:var(--text-2)" }, `${merkmale.length} Merkmale`)),
    d?.kuerzel?.length ? h("div", { style: "padding:10px 18px 0" }, h("div", { class: "gruppen-titel", style: "padding:0 0 6px" }, "Kürzel ohne Zuordnung"),
      h("div", { style: "display:flex;gap:6px;flex-wrap:wrap" }, ...d.kuerzel.map((k) => h("span", { class: "chip" }, h("strong", {}, k.alias), k.merkmal ? `→ ${k.merkmal}` : " ohne Merkmal",
        h("button", { type: "button", class: "knopf klein", style: "border:none", onclick: () => kuerzelDialog(k.alias) }, "Zuordnen"))))) : null,
    merkmale.length ? h("div", { class: "regel-liste" }, ...merkmale.map((m) => merkmalKarte(S.merkmale[m.merkmal] && entwurfLeer() ? m : m)))
      : h("div", { class: "leer-hinweis" }, S.regelnNurOffen ? "Keine Merkmale mit offenen Werten – Häkchen oben entfernen, um alle zu sehen." : "Keine Merkmale gefunden."));
}

// ------------------------------------------------------------------------------------------------ Auswirkung
async function berechneAuswirkung() {
  const box = $("#ansicht-auswirkung");
  box.replaceChildren(h("div", { class: "leer-hinweis" }, "Rechne alle betroffenen Materialien neu …"));
  try {
    S.auswirkung = await api("POST", "/api/auswirkung", { entwurf: entwurfPayload() });
  } catch (e) { S.auswirkung = { fehler: e.message }; }
  zeichneAuswirkung();
}

function zeichneAuswirkung() {
  const box = $("#ansicht-auswirkung");
  if (entwurfLeer()) {
    box.replaceChildren(h("div", { class: "leer-hinweis" }, h("p", {}, "Kein Entwurf offen."), h("p", {}, "Ändere eine Regel (Status oder Rang) – hier siehst du dann, welche Materialien sich dadurch ändern.")));
    return;
  }
  if (!S.auswirkung) { berechneAuswirkung(); return; }
  const a = S.auswirkung;
  if (a.fehler) { box.replaceChildren(h("div", { class: "leer-hinweis" }, a.fehler)); return; }
  box.replaceChildren(
    h("div", { style: "padding:16px 18px" },
      h("h2", { style: "margin:0 0 4px;font-size:16px" }, a.betroffen ? `Dein Entwurf ändert ${a.betroffen} Material${a.betroffen === 1 ? "" : "ien"}` : "Dein Entwurf ändert keine Stückliste"),
      h("p", { class: "unter", style: "color:var(--text-2);margin:0" }, `${a.geprueft} Materialien enthalten die geänderten Merkmale und wurden neu gerechnet.`),
      h("button", { type: "button", class: "knopf klein", style: "margin-top:8px", onclick: berechneAuswirkung }, "Neu berechnen")),
    a.materialien.length ? h("table", { class: "tabelle" },
      h("thead", {}, h("tr", {}, h("th", {}, "Material"), h("th", {}, "Geänderte Positionen"), h("th", {}, "In der Basis-Stückliste"), h("th", {}, "Beispiele"))),
      h("tbody", {}, ...a.materialien.map((m) => h("tr", { class: "klickbar", onclick: () => oeffneMaterial(m.matnr), title: "Material öffnen" },
        h("td", {}, h("strong", {}, m.matnr), h("br"), h("span", { style: "color:var(--text-2)" }, m.kurztext)),
        h("td", {}, ...m.wechsel.map((w) => h("div", {}, `${w.anzahl}× `, h("span", { class: `status s-${w.von}` }, STATUS[w.von]?.kurz || "neu"), h("span", { class: "pfeil-text" }, "→"), h("span", { class: `status s-${w.nach}` }, STATUS[w.nach]?.kurz || "entfällt")))),
        h("td", {}, `${m.vorher_im_ergebnis}`, h("span", { class: "pfeil-text" }, "→"), h("strong", {}, `${m.nachher_im_ergebnis}`), " Positionen"),
        h("td", {}, ...m.beispiele.map((b) => h("div", { style: "font-size:12px;color:var(--text-2)" }, `${b.matnr} ${b.kurztext}`))))))) : null);
}

// ------------------------------------------------------------------------------------------------ Dialoge
function dialog(titel, inhalt, knoepfe) {
  $("#dialog-titel").textContent = titel;
  $("#dialog-inhalt").replaceChildren(...[inhalt].flat());
  $("#dialog-knoepfe").replaceChildren(...knoepfe);
  $("#dialog").hidden = false;
  const erstes = $("#dialog").querySelector("input, textarea, button.haupt");
  if (erstes) erstes.focus();
}
const schliesseDialog = () => ($("#dialog").hidden = true);

function brauchtName() {
  if (S.name) return Promise.resolve(true);
  return new Promise((ok) => nameDialog(() => ok(Boolean(S.name))));
}

function nameDialog(danach) {
  const eingabe = h("input", { type: "text", value: S.name, placeholder: "Vorname Nachname", "aria-label": "Name" });
  const speichern = () => { const n = eingabe.value.trim(); if (!n) { toast("Bitte einen Namen eingeben.", true); return; } S.name = n; speicher.schreib("bb.name", n); zeichneEntwurf(); schliesseDialog(); if (danach) danach(); };
  eingabe.addEventListener("keydown", (ev) => { if (ev.key === "Enter") speichern(); });
  dialog("Wie heißt du?", [h("p", {}, "Dein Name wird bei Regeländerungen und Bewertungen gespeichert, damit nachvollziehbar ist, wer was entschieden hat."), eingabe],
    [h("button", { type: "button", class: "knopf haupt", onclick: speichern }, "Weiter")]);
}

function kuerzelDialog(alias) {
  const bekannte = [...new Set([...Object.keys(S.merkmale), ...Object.keys(S.basisRegeln).map((k) => k.split("|")[0])])].sort();
  const liste = h("datalist", { id: "merkmal-liste" }, ...bekannte.map((m) => h("option", { value: m })));
  const eingabe = h("input", { type: "text", list: "merkmal-liste", placeholder: "Merkmalname laut SAP, z. B. SITZQUALI", "aria-label": "Merkmal" });
  dialog(`Kürzel „${alias}“ zuordnen`, [h("p", {}, "Zu welchem Merkmal gehört dieses Kürzel in den Bedingungsnamen?"), eingabe, liste,
    h("p", { class: "unter", style: "color:var(--text-2)" }, "Die Zuordnung landet im Entwurf – der Baum zeigt sofort, was sich ändert.")],
  [h("button", { type: "button", class: "knopf leise", onclick: () => { setzeKuerzel(alias, null, "NICHT_BASIS"); schliesseDialog(); } }, "Kein Merkmal (ignorieren nicht möglich)"),
    h("button", { type: "button", class: "knopf", onclick: schliesseDialog }, "Abbrechen"),
    h("button", { type: "button", class: "knopf haupt", onclick: () => { const m = eingabe.value.trim().toUpperCase(); if (!m) { toast("Bitte ein Merkmal eintragen.", true); return; } setzeKuerzel(alias, m, "BASIS"); schliesseDialog(); } }, "Zuordnen")]);
}

async function uebernehmenDialog() {
  if (!(await brauchtName())) return;
  const begr = h("textarea", { placeholder: "z. B. „Laut Produktmanagement ist FK die Standardausführung“", "aria-label": "Begründung" });
  const aenderungen = [...Object.values(S.entwurf.regeln), ...Object.values(S.entwurf.aliasse)];
  dialog("Regeländerungen übernehmen", [
    h("p", {}, `${aenderungen.length} Änderung${aenderungen.length === 1 ? "" : "en"} gelten danach für alle Materialien und alle Kolleg:innen:`),
    h("ul", { class: "einfach" }, ...aenderungen.map((e) => h("li", {}, entwurfEintragText(e)))),
    h("label", {}, "Begründung (für die Historie)"), begr,
    h("p", { class: "unter", style: "color:var(--text-2)" }, `Gespeichert als: ${S.name}`)],
  [h("button", { type: "button", class: "knopf", onclick: schliesseDialog }, "Abbrechen"),
    h("button", { type: "button", class: "knopf haupt", onclick: async (ev) => {
      ev.target.disabled = true;
      try {
        await api("POST", "/api/uebernehmen", { entwurf: entwurfPayload(), von: S.name, begruendung: begr.value.trim() || null });
        S.entwurf = { regeln: {}, aliasse: {} };
        schliesseDialog();
        toast("Übernommen – die Regeln gelten jetzt für alle.");
        await ladeBasisRegeln();
        entwurfGeaendert();
        ladeMeta();
        ladeMaterialien();
      } catch (e) {
        ev.target.disabled = false;
        if (e.status === 409) konfliktDialog(e.daten.konflikte); else toast(e.message, true);
      }
    } }, "Übernehmen")]);
}

function konfliktDialog(konflikte) {
  dialog("Jemand hat diese Regeln inzwischen geändert", [
    h("p", {}, "Seit du angefangen hast, wurden folgende Werte von jemand anderem geändert:"),
    h("ul", { class: "einfach" }, ...konflikte.map((k) => h("li", {}, k.art === "regel" ? `${k.merkmal} = ${k.wert}: jetzt ${REGEL_STATUS[k.jetzt.status]}${k.jetzt.rang ? ` (Rang ${k.jetzt.rang})` : ""}` : `Kürzel ${k.alias}: jetzt ${k.jetzt.merkmal || "–"}`))),
    h("p", {}, "Lade den aktuellen Stand: Deine übrigen Änderungen bleiben im Entwurf, die betroffenen Werte kannst du danach neu setzen.")],
  [h("button", { type: "button", class: "knopf haupt", onclick: async () => {
    for (const k of konflikte) { if (k.art === "regel") delete S.entwurf.regeln[`${k.merkmal}|${k.wert}`]; else delete S.entwurf.aliasse[k.alias]; }
    await ladeBasisRegeln();
    for (const e of Object.values(S.entwurf.regeln)) e.vorher = S.basisRegeln[`${e.merkmal}|${e.wert}`] || { status: "OFFEN", rang: null };
    for (const e of Object.values(S.entwurf.aliasse)) e.vorher = S.basisAliasse[e.alias] || { merkmal: null, status: "OFFEN" };
    schliesseDialog();
    entwurfGeaendert();
  } }, "Aktuellen Stand laden")]);
}

function hilfeDialog() {
  const zeile = (st) => [h("span", {}, statusPill(st)), h("span", {}, {
    basis: "Erfüllt die Basis-Regeln – kommt in die Basis-Stückliste.",
    unbedingt: "Hat keine Variantenbedingung – immer dabei.",
    manuell_prüfen: "Noch nicht entscheidbar, meist fehlt ein Basiswert. Unter „Offene Fragen“ steht, was fehlt.",
    unterhalb_manuell: "Die übergeordnete Baugruppe ist noch offen.",
    ausgeschlossen: "Passt nicht zu den Basiswerten – kommt nicht in die Basis-Stückliste.",
    ausgeschlossen_vererbt: "Die übergeordnete Baugruppe ist nicht in der Basis.",
  }[st])];
  dialog("So funktioniert die Basis-Stückliste", [
    h("p", {}, "Für jedes Merkmal (z. B. Sitzqualität) legt der Fachbereich fest, welche Werte zur Basis gehören und in welcher Rangfolge. Kommen auf einer Stückliste mehrere Basiswerte vor, gewinnt der mit dem kleinsten Rang."),
    h("div", { class: "legende" }, ...["basis", "unbedingt", "manuell_prüfen", "unterhalb_manuell", "ausgeschlossen", "ausgeschlossen_vererbt"].flatMap(zeile)),
    h("h3", { style: "font-size:14px;margin-top:16px" }, "Ablauf"),
    h("ol", { class: "einfach" },
      h("li", {}, "Material wählen, offene Fragen rechts klären – jede Regeländerung ist zunächst ein Entwurf nur für dich."),
      h("li", {}, "„Auswirkung auf alle Materialien“ zeigt, welche anderen Stücklisten sich mitändern."),
      h("li", {}, "„Übernehmen“ speichert die Regeln für alle (mit Name und Begründung)."),
      h("li", {}, "Zeilen mit „✓ Stimmt“ bzw. „Raus“/„Rein“ bewerten, speichern, Material bestätigen."))],
  [h("button", { type: "button", class: "knopf haupt", onclick: schliesseDialog }, "Verstanden")]);
}

// ------------------------------------------------------------------------------------------------ Navigation
function wechsleAnsicht(ansicht) {
  S.ansicht = ansicht;
  for (const b of document.querySelectorAll(".reiter-knopf")) { const an = b.dataset.ansicht === ansicht; b.classList.toggle("aktiv", an); b.setAttribute("aria-selected", String(an)); }
  for (const a of ["stueckliste", "regeln", "auswirkung"]) $(`#ansicht-${a}`).hidden = a !== ansicht;
  if (ansicht === "regeln") ladeRegelAnsicht();
  if (ansicht === "auswirkung") zeichneAuswirkung();
}

function zeichne() {
  zeichneEntwurf();
  zeichneStueckliste();
  zeichneDetails();
}

document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape" && !$("#dialog").hidden) { schliesseDialog(); return; }
  if (S.ansicht !== "stueckliste" || !S.daten?.positionen || ["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
  const ids = sichtbarePositionen().reihenfolge.map((x) => x.p.id);
  const i = ids.indexOf(S.auswahl);
  if (ev.key === "ArrowDown" && i < ids.length - 1) { ev.preventDefault(); waehle(ids[i + 1] ?? ids[0]); }
  else if (ev.key === "ArrowUp" && i > 0) { ev.preventDefault(); waehle(ids[i - 1]); }
  else if ((ev.key === "ArrowLeft" || ev.key === "ArrowRight") && S.auswahl) {
    ev.preventDefault();
    if (ev.key === "ArrowLeft") S.zu.add(S.auswahl); else S.zu.delete(S.auswahl);
    zeichneBaum();
  }
});

async function start() {
  $("#material-suche").addEventListener("input", zeichneMaterialliste);
  for (const b of document.querySelectorAll(".reiter-knopf")) b.addEventListener("click", () => wechsleAnsicht(b.dataset.ansicht));
  $("#nutzer-knopf").addEventListener("click", () => nameDialog());
  $("#hilfe-knopf").addEventListener("click", hilfeDialog);
  $("#verwerfen-knopf").addEventListener("click", () => {
    dialog("Entwurf verwerfen?", h("p", {}, "Alle Änderungen im Entwurf gehen verloren."), [
      h("button", { type: "button", class: "knopf", onclick: schliesseDialog }, "Abbrechen"),
      h("button", { type: "button", class: "knopf haupt", onclick: () => { S.entwurf = { regeln: {}, aliasse: {} }; schliesseDialog(); entwurfGeaendert(); } }, "Verwerfen")]);
  });
  $("#uebernehmen-knopf").addEventListener("click", uebernehmenDialog);
  $("#auswirkung-knopf").addEventListener("click", () => { wechsleAnsicht("auswirkung"); });
  $("#dialog").addEventListener("click", (ev) => { if (ev.target.id === "dialog") schliesseDialog(); });
  try {
    await Promise.all([ladeMeta(), ladeBasisRegeln(), ladeMaterialien()]);
  } catch (e) { toast(`Server nicht erreichbar: ${e.message}`, true); return; }
  zeichneEntwurf();
  const ausHash = (location.hash.match(/#\/material\/(\w+)/) || [])[1];
  const erstes = ausHash || (S.materialien.find((m) => m.zustand === "offen" || m.zustand === "in_arbeit") || S.materialien[0])?.matnr;
  if (erstes) await ladeMaterial(erstes);
  else zeichne();
  if (!S.name) nameDialog();
}

start();
