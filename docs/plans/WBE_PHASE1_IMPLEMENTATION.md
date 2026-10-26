# WBE Fase 1 — implementazione e collaudo

Data: 26 ottobre 2026. Stato: Fase 1 implementata e collaudata sul laboratorio sintetico; nessun cutover produttivo. Worktree `/opt/apps/wbe-refact`, branch `feature/phase1-layers-postgresql`, base `367b8635236bde61a289880d7002574b5ddff6ca`.

## Risultato e perimetro

Ambiente Docker separato `wbe-refact` con frontend Node, backend Python/Twisted e PostgreSQL. Il codice FE/BE è montato dal filesystem Linux in sola lettura; le immagini contengono runtime e dipendenze. La build Angular viene prodotta dal sorgente tramite tooling esplicito. Il listener di sviluppo è `http://127.0.0.1:18090`; per l'accesso remoto utilizzare un tunnel SSH. PostgreSQL non espone porte host.

Il backend usa PostgreSQL, pool limitato per processo e ruolo runtime separato dal migratore. Lo schema applicativo resta 69 con revisione PostgreSQL 2. La selezione del database è esplicita tramite DSN o file segreto: indisponibilità PostgreSQL e configurazioni errate non provocano fallback su SQLite. L'avvio controlla lo schema senza migrazioni automatiche.

Il frontend serve HTML e asset dal proprio mount e inoltra le API conservando l'origine browser. Tenant, lingua e intestazioni di sicurezza vengono decisi dal backend; il documento incorpora il nonce CSP restituito dal backend. Il backend monta soltanto i dati pubblici/font necessari, senza il bundle applicativo frontend.

Nel laboratorio sintetico descritto qui non sono stati importati dati di produzione. La successiva copia reale isolata è documentata in WBE_REAL_DATA_REHEARSAL.md; non è stato effettuato cutover. WBE live e Notarius rimangono indipendenti. Controllo finale in sola lettura: `wbe-app@node1.service` attivo; i tre container `notarius-internal` ancora healthy con uptime di tre settimane. Questo laboratorio usa fixture sintetiche e notifiche disabilitate.

## Persistenza e trasferimento

L'importatore offline richiede uno snapshot SQLite già aggiornato allo schema 69 e un target PostgreSQL vuoto. Verifica integrità, foreign key, tabelle/colonne, dominio dei booleani e formati ricevuta; importa con transazione atomica, confronta conteggi e digest canonici di ogni tabella e riallinea le sequenze. Rifiuta ricevute con formati misti nello stesso tenant: normalizzarle tramite il percorso legacy prima di produrre lo snapshot. Il dry run non crea tabelle.

L'importazione DB non trasferisce gli allegati: `verify-files.py` controlla riferimenti e SHA256 su snapshot congelato, rifiuta upload pendenti/file mancanti/link simbolici e copia verso una directory nuova. Chiavi e configurazioni devono accompagnare i dati autorizzati, senza rigenerazione o ricifratura implicita.

Il contatore progressivo usa il lock della riga; l'archivio questionari gestisce inserimenti concorrenti tramite `ON CONFLICT`. La manutenzione PostgreSQL è affidata ad autovacuum, evitando il VACUUM SQLite nel job periodico.

Backup e restore sono coordinati: FE/BE fermi durante l'istantanea di database e appdata; restore in nuovo DB e nuova directory, verificando digest e percorsi negli archivi. Comandi e prerequisiti nel [runbook](WBE_PHASE1_RUNBOOK.md).

## Collaudo

Evidenze locali in `.local/`, escluse da Git; contengono soltanto il laboratorio e devono comunque restare private.

- Suite legacy SQLite: **648/648 superati**, 610,342 secondi (`.local/sqlite-tests.log`). Dopo tutte le correzioni finali, ripetute le aree destinatari e ORM: **55/55 superati**, 106,557 secondi (`.local/sqlite-final-affected.log`).
- Suite completa PostgreSQL sulla revisione 2 finale: **629 superati, 19 esclusi, zero errori**, su 648 test raccolti; 538,492 secondi (`.local/pg-regression-revision2.log`). Le esclusioni sono 18 migrazioni storiche di file SQLite e un test dell’authorizer SQLite; queste verifiche sono coperte dalla matrice SQLite.
- Integrazione PostgreSQL reale: **15/15 superati**, 5,235 secondi. Import atomico/dry-run, rifiuto dati non validi, sequenze, privilegi della revisione e concorrenza con otto sessioni.
- Trasferimento file: **3/3**; configurazione/TLS di sviluppo e manutenzione DB: **5/5**; query destinatari con più questionari e accesso limitato: **2/2**.
- Proxy/frontend nel runtime Node: **2/2 superati**.
- Chromium reale: **4/4 superati**, circa 29 secondi. Wizard, login in nuova sessione, lingue EN/IT, assenza errori CSP, worker/viewer, invio segnalazione, ricevuta in nuova sessione, upload allegato sintetico e download decifrato del destinatario con uguaglianza esatta dei byte. I flag e i prerequisiti sono nell’[ADR frontend](../../deploy/dev/frontend-server/README.md).
- Dopo riavvio FE/BE e PostgreSQL, ripetuti **3 test browser superati**, senza creare altre segnalazioni: login persistente, shell EN/IT e download/decifratura dell’allegato esistente.
- Indisponibilità DB: readiness FE **503** a PostgreSQL fermo, nessun nuovo `.db`; dopo riavvio PostgreSQL readiness **200** e recupero del pool senza restart BE (`.local/recovery-final.log`).
- Backup con allegati e restore separato: `wbe_restore_20261026170903`, `.local/restore-20261026170903`, schema 69/revisione 2. **33/35 tabelle** coincidono integralmente per digest canonico; `user` conserva gli stessi due record e tutti i campi salvo `last_login`; `auditlog` conserva invariati tutti i 33 record del backup, con cinque eventi aggiunti sul laboratorio dopo il backup. Differenze dovute ai successivi login del collaudo browser. **Due allegati** coincidono per percorso, dimensione e SHA256; chiavi e altri campi utente coincidono. Evidenza aggregata: `.local/restore-verification.json`. Non è stata avviata una seconda applicazione contro il DB ripristinato: la decrittazione browser è stata verificata sull’istanza originale riavviata, con gli stessi dati crittografici.
- `gl-admin backup` con PostgreSQL rifiutato con exit 2 prima dell’operazione; ruolo runtime privo di CREATE/DROP e scrittura della revisione.

Il test browser ha individuato una query della lista destinatari che SQLite accettava e PostgreSQL rifiutava: è stata sostituita la selezione arbitraria con il primo questionario per data e hash, preservando la visibilità dei destinatari. La revisione ha inoltre individuato e corretto VACUUM periodico e backup legacy incompleto. La matrice completa ha evidenziato un campo `ReceiverFile.size` che su SQLite conteneva sia numeri sia testo cifrato: su PostgreSQL usa ora la rappresentazione JSON testuale, conservando il tipo originale dei valori. La baseline PostgreSQL non pubblicata è stata aggiornata a revisione 2; schema SQLite 69 invariato. I test ORM ora chiudono le sessioni prima del reset del database successivo. Una prima esecuzione PostgreSQL è stata invalidata da una ricreazione del container DB durante il lavoro parallelo; i risultati di quella prova non sono conteggiati come successi.

## Limiti e passaggio successivo

Un solo BE mantiene sessioni, cache, upload e scheduler locali. Non aumentare le repliche BE prima delle modifiche descritte nel [disegno HA](../design/WBE_POSTGRESQL_HA_PLAN.md). Anche PostgreSQL è singolo: questo ambiente non dimostra failover, alta disponibilità o SLA. Il requisito HA completo del primo rilascio produttivo resta valido.

Il proxy di sviluppo non propaga l'IP del visitatore: le policy IP del backend vedono il frontend. Prima della produzione servono gestione esplicita dei proxy fidati, TLS, identità del client e verifica delle relative policy. HTTP è ammesso soltanto sul listener loopback con entrambi i flag di sviluppo; i nomi esterni mantengono il redirect HTTPS.

Per un DB su altra VM configurare TLS verificato e CA (`sslmode=verify-full`), rete/firewall e segreti coerenti: il bridge Docker locale non dimostra questa topologia remota. Non sono state cronometrate migrazioni di un dataset reale, quindi il limite di un'ora per il futuro fermo non è ancora attestato. Servono prova su copia autorizzata, ripristino/decrittazione, dimensionamento e prova generale del cutover.

Le immagini runtime usano Python 3.12/lockfile Noble e Node 24 su Debian bookworm; la raccomandazione piattaforma upstream viene ancora segnalata. Le immagini sono fissate a digest, ma l'installazione delle dipendenze OS deve essere rivalidata per un rilascio produttivo. Gli obblighi di attribuzione e sorgente del fork restano documentati nel disegno.
