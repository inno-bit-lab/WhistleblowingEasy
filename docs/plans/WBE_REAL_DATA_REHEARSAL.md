# Copia reale per collaudo PostgreSQL

Aggiornato dopo il cutover del 26 ottobre 2026: rehearsal dismesso e svuotato dopo backup finale. La produzione autorevole è ora lo stack `wbe-production`, importato da una nuova copia congelata, non dalla copia di collaudo. Conservati privatamente backup e snapshot. I risultati seguenti documentano il collaudo storico.

## Diagnosi dello snapshot

L’operatore ha eseguito lo snapshot `real-20261026T173607Z`. App e monitor sono stati riavviati; la verifica offline ha rifiutato il marcatore `version_db=68`. Nessuna necessità di ripetere la copia o di fermare nuovamente la produzione.

L’audit in sola lettura ha confrontato tutte le 34 tabelle con il modello 69: colonne, tipi, nullabilità, default, chiavi primarie, indici e foreign key coincidono; è presente anche `context.slug`. Il codice installato dichiara schema 69 e applicazione 5.0.99. La causa individuata in `perform_data_update` è l’aggiornamento del marcatore solo quando cambia anche la versione applicativa: una migrazione di schema con versione applicativa invariata può lasciare il marcatore precedente.

Il fix nel branch aggiornato modifica il marcatore dopo la migrazione riuscita anche a versione applicativa invariata, mantenendo transazione e rollback. Non è stato distribuito al backend di produzione. Il solo valore 68 non autorizza a rietichettare altri database: occorre un confronto strutturale completo oppure la vera migrazione offline.

Lo snapshot originale rimane invariato e privato. La copia di lavoro `.local/imports/real-20261026T173607Z-work` conserva DB e file; soltanto `config.version_db` è stato normalizzato a 69, dopo confronto strutturale. SHA256 del database sorgente verificato invariato. Integrità SQLite, foreign key e assenza di upload pendenti confermate. Dettagli privati in `preparation.json` e `files-manifest.json`, esclusi da Git.

Per snapshot futuri lo script accetta marker 68 o 69; il 68 viene segnalato come `requires-offline-schema-review`, senza normalizzazione automatica. L’importatore PostgreSQL continua a richiedere schema 69 e target vuoto.

## Risultato dell’importazione

- Progetto separato `wbe-rehearsal`, volume PostgreSQL e segreti propri.
- Dry-run e importazione atomica completati; 34 tabelle verificate per conteggi e digest canonici.
- **9 utenti e 1 segnalazione** importati. Nessun reset di password, 2FA o chiavi; i relativi dati sono compresi nel confronto di tutti i valori delle tabelle.
- **9 file permanenti** verificati per riferimenti, dimensione e SHA256, copiati in appdata separata. Non sono tutti necessariamente allegati: sono inclusi anche i file di personalizzazione.
- Schema applicativo 69, revisione PostgreSQL 2.
- Evidenze private: `.local/rehearsal/import-dry-run.json`, `import-result.json`, `files-verified.json`, `schema-check.json`.

Lo snapshot originale conserva anche materiale di riferimento non utilizzato dal collaudo. Per il runtime sono stati installati soltanto file permanenti verificati e dati importati nel DB; non vengono montati appdata, configurazioni di servizio, log o directory Tor della produzione.

## Isolamento e funzionamento

FE/BE leggono il codice dal checkout; backend e PostgreSQL usano esclusivamente reti Docker interne. Solo FE dispone di una rete ingress aggiuntiva per pubblicare `127.0.0.1:18091`. Il backend non dispone di uscita Internet, verificata con controllo delle reti e prova di connessione; nessuna porta BE/DB pubblicata. Tutti i servizi hanno `traefik.enable=false`.

`WBE_REHEARSAL=1` richiede frontend separato e notifiche disabilitate. Avvia soltanto il job locale Delivery, necessario alla gestione dei file e delle nuove segnalazioni di prova; non avvia Tor, notifiche, pulizie per scadenza, controlli aggiornamenti o altri job periodici. Nessuna identità onion produttiva viene attivata. I redirect canonici da IP e l’header Onion-Location sono soppressi in questa modalità. Configurazioni, credenziali e chiavi nel DB sono preservate; non è stata riscritta la configurazione per ottenere questo isolamento.

Questo ambiente non serve a provare invio email, Tor, scadenze automatiche, HA o cutover. Gli eventuali link esterni mostrati dall’applicazione mantengono il contenuto originale: restare nell’origine localhost del collaudo.

## Accesso dal PC

```sh
ssh -N -L 18091:127.0.0.1:18091 ibladmin@IP_SERVER
```

Aprire **http://localhost:18091/#/login** e usare le proprie credenziali del WBE attuale, compresa la 2FA se configurata. Le credenziali sintetiche della porta 18090 non appartengono a questa copia.

Verificati: tre servizi healthy, readiness FE/API, schema DB, pagina di login in Chromium senza errori JavaScript né richieste fallite. Non sono state inserite password reali nel browser automatico. Login autenticato, autorizzazioni utente, ricevute e decrittazione effettiva richiedono il collaudo dell’operatore con le proprie credenziali: non inviarle in chat. Nessuno screenshot di dati reali viene salvato automaticamente.

## Operazioni

Da `/opt/apps/wbe-refact`:

```sh
./scripts/rehearsal/compose.sh ps
./scripts/rehearsal/compose.sh stop frontend backend
./scripts/rehearsal/compose.sh start backend frontend
```

Il laboratorio sintetico `wbe-refact` su 18090 resta separato. Non usare le fixture sintetiche, i test che ricreano lo schema o `migrate init` contro la copia reale. Non eseguire `down -v` per correggere errori: elimina i volumi di questa destinazione. Non usare `scripts/dev/backup.sh` per questo stack: è fissato al progetto sintetico; un backup del collaudo deve usare il wrapper rehearsal e coordinare DB e appdata.

## Verifiche e passaggio definitivo

Test aggiunti: recupero dello snapshot dopo timeout e rifiuto senza privilegi; aggiornamento del marker a versione applicativa invariata e rollback; avvio del solo Delivery senza Tor/job ordinari. Verificata anche la migrazione storica sintetica 68→69. Le regressioni dei contratti web preesistenti restano verdi.

App `wbe-app@node1.service` e timer monitor confermati attivi dopo lo snapshot e dopo l’importazione. Il database live non è stato modificato da questa procedura; la copia non riceve nuove scritture dalla produzione.

Prima del passaggio definitivo: registrare gli esiti del collaudo autenticato, predisporre backup e rollback, svuotare soltanto la destinazione di prova nel momento concordato, acquisire un nuovo snapshot coerente e ripetere preparazione/import/verifica. Le modifiche fatte durante il collaudo non saranno riportate in produzione. Il limite di fermo di un’ora va verificato su tutta la procedura finale; non si deduce dalla sola velocità dell’importazione del laboratorio.

## Correzione allegati dal modulo del canale — 26 ottobre 2026

Il collaudo ha rilevato un upload HTTP 501 seguito da invio della segnalazione HTTP 201: Flow.js usava un target API relativo e, dalla pagina del canale, aggiungeva erroneamente il prefisso del canale. Flow usa XHR direttamente e non passa dall'interceptor Angular. Per la segnalazione esaminata non risultavano metadati di allegati; il file deve essere ricaricato dall'utente.

In `UtilsService.getFlowOptions` i target che iniziano con `api/` vengono ora resi assoluti rispetto all'origine (`/api/…`), prima della generazione della prova DPoP. Il frontend è stato ricompilato ed è disponibile nei due laboratori mediante il mount del build; produzione invariata.

Verifica: quattro test URL/DPoP superati; prova Chromium sul solo laboratorio sintetico 18090 con ingresso `/phase1-upload-channel/report`, allegato inserito prima dell'invio, risposta upload 2xx sull'endpoint corretto, ricevuta utilizzabile in una nuova sessione e download decifrato dal destinatario confrontato byte per byte con il contenuto sintetico. Due test browser superati. Il test si attiva con `WBE_E2E_CHANNEL=phase1-upload-channel` insieme a `WBE_E2E_REPORT=1`; richiede il canale configurato nella fixture sintetica. Nessun contenuto di allegati reali è stato letto per la diagnosi.

Per riprovare nel collaudo reale: ricaricare completamente il browser (Ctrl+Shift+R), accedere alla segnalazione con la propria ricevuta e aggiungere nuovamente il file. La correzione non recupera il precedente upload respinto.

## Audit dei percorsi browser dopo il difetto upload

Controllati i punti che non passano dall'interceptor HTTP Angular: Flow/XHR, fetch, Worker, window.open, iframe e risorse inserite nel DOM. Corretti anche sei punti di download/export API (uno contiene due rami nel downloader condiviso), tre URL iframe del viewer per allegati/audio e due fogli di stile dinamici. Questi URL sono ora assoluti rispetto all'origine; token, endpoint e controlli di autorizzazione restano invariati. Worker, fetch del canale e script personalizzato erano già radicati. Le API relative ancora presenti nei servizi Angular passano dall'interceptor, che aggiunge lo slash iniziale.

Spiegazione storica: il commit `ba8f9c9dc7` del 1 ottobre 2026 introduceva i canali e già conteneva Flow con target relativo e normalizzazione nel solo interceptor Angular. Senza un base href, `api/…` aperto da `/#/submission` risolve a `/api/…`, mentre da `/canale/report` risolve a `/canale/api/…`. Il difetto è quindi presente nel sorgente precedente alla separazione FE/BE e non deriva dal motore PostgreSQL. Non è stata accertata la combinazione di URL e configurazione proxy usata nel precedente caricamento riuscito dell'operatore.

Il test browser del canale ora controlla anche che i due fogli di stile dinamici siano caricati dai percorsi radicati e non risultino errori HTTP delle risorse monitorate. Il controllo statico degli altri percorsi non equivale a un collaudo funzionale di tutti i formati audio, anteprime o modalità di export.

Esito audit: build completato; 4 test URL/DPoP e 2 test proxy superati; Chromium 3 test superati (avvio IT/EN e CSP, invio dal canale con allegato e stili, download decifrato), wizard escluso perché già configurato. Build disponibile nei laboratori tramite mount del filesystem.
