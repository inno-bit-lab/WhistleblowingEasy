# Audit SEO WBE — 26 ottobre 2026

Dominio richiesto: https://wbe.kronosfinance.it/
Riferimento: https://whistleblowing.it/
Stato: analisi preliminare verificata; implementazione SEO non ancora eseguita. Lavoro momentaneamente concentrato sulla pagina di consultazione richiesta dall'operatore. Nessuna impostazione di indicizzazione o modifica di produzione applicata.

## Evidenze osservate

Whistleblowing.it risponde con HTML contenente testi e collegamenti pubblici. Ha pagine specifiche per PA, società in controllo pubblico ed enti privati, documentazione e notizie. Nella home rilevati title descrittivo, canonical alla radice, alternate hreflang it/en/x-default; robots.txt rinvia a wp-sitemap.xml con indice di pagine, post e tassonomie. Nel sorgente scaricato non risultano meta description o H1; og:title è generico ("Homepage"). Non riprodurre questi limiti. Non sono stati misurati ranking, traffico, backlink o Core Web Vitals: nessuna conclusione sulle performance organiche effettive.

WBE pubblico: GET / restituisce 200, X-Robots-Tag noarchive, descrizione generica inglese e shell Angular senza title iniziale. robots.txt consente solo / e blocca il resto; sitemap contiene https://wbe.kronosfinance.it/#/ e variante inglese con frammento. L'app usa lo stesso documento per home, ricevuta e segnalazione autenticata; il frammento non distingue risorse HTTP. Nel codice allow_indexing governa l'header a livello tenant, non per tipo di pagina.

## Disegno proposto

Separare sullo stesso dominio le pagine informative indicizzabili e l'app di segnalazione. Conservare i link esistenti e le sessioni; progettare prima il passaggio della home per non interrompere accesso con ricevuta. Una nuova pagina pubblica statica /piattaforma-whistleblowing/ può essere il primo incremento indipendente.

Pagine pubbliche con contenuti originali:
- /piattaforma-whistleblowing/: servizio e funzionalità effettivamente disponibili.
- /come-funziona/: invio, allegati, ricevuta e dialogo.
- /sicurezza/: caratteristiche verificate dell'installazione, senza promesse assolute.
- /domande-frequenti/: risposte utili per aziende e segnalanti.
- /contatti/: solo recapiti aziendali approvati.
- Pagine per settori solo se corrispondono a offerte reali confermate.

Per ogni pagina: HTML completo già nella risposta, title/description propri, H1 descrittivo, canonical HTTPS, link reali senza #, sitemap con sole pagine pubbliche; hreflang solo per traduzioni reali. Structured data coerenti col contenuto e identità verificata, senza recensioni o certificazioni inventate. Nessuna imitazione di nomi, testi, qualificazioni ACN o offerta gratuita del concorrente.

L'app, API, login, allegati e collaudo restano esclusi dalla strategia di acquisizione organica; noindex non è un controllo di accesso e non sostituisce autenticazione/autorizzazione. Non abilitare indiscriminatamente allow_indexing. Definire una policy per route, compatibile con i fragment URL esistenti.

## Verifiche prima della pubblicazione

Testare HTTP status, HTML senza JavaScript, canonical, robots/header per classe di percorso, sitemap senza frammenti/dati riservati, link, accessibilità e comportamento mobile. Testare accesso tramite canali, ricevute e destinatari dopo il routing. Pubblicare solo dopo revisione del risultato nel collaudo. Configurare/verificare Search Console sul dominio autorizzato e misurare impression, click, CTR e richieste pertinenti; nessuna garanzia di ranking.

## Fonti

- https://whistleblowing.it/
- https://whistleblowing.it/proposte/per-enti-di-diritto-privato/
- https://whistleblowing.it/documentazione-tecnica/
- https://whistleblowing.it/robots.txt
- https://whistleblowing.it/wp-sitemap.xml
- https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics

File esaminati: client/app/index.html, backend/globaleaks/handlers/robots.py, backend/globaleaks/handlers/sitemap.py, backend/globaleaks/rest/api.py, deploy/dev/frontend-server/server.mjs.
