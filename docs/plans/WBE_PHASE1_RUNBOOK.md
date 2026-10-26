# WBE Fase 1 — ambiente separato di sviluppo

Il progetto Compose è sempre `wbe-refact`. Questo ambiente usa dati sintetici ed è indipendente da WBE live e Notarius. Non costituisce HA e non autorizza il cutover produttivo. Tutti i comandi seguenti si eseguono da `/opt/apps/wbe-refact`.

## Preparazione e avvio

Prerequisiti: Docker e Compose moderno, Python 3.11+ host per bootstrap e verifica backup, accesso al registry e npm durante build. Il wrapper usa `.local/bin/docker-compose` se presente (binario 5.3.1 verificato sul server), altrimenti `docker compose`; non modifica Docker globale.

```sh
./scripts/dev/bootstrap.sh
./scripts/dev/compose.sh build backend frontend
./scripts/dev/build-client.sh
./scripts/dev/compose.sh up -d postgres
./scripts/dev/migrate.sh init --working-path /var/globaleaks
./scripts/dev/compose.sh up -d backend frontend
./scripts/dev/smoke.sh
```

`init` è esplicito e richiede uno schema vuoto. Per un database già inizializzato usare `check`, non ripetere `init`. Il backend non crea schema e non ripiega su SQLite quando PostgreSQL manca. Importare uno snapshot al posto di `init`, mai dopo.

HTTP di sviluppo è consentito solo con `WBE_DEV_HTTP=1`, frontend separato e host loopback; gli altri hostname mantengono il redirect HTTPS.

Frontend disponibile su `http://127.0.0.1:18090` (tunnel SSH per accesso remoto). PostgreSQL non pubblica porte host. FE è sulla rete web, PostgreSQL sulla rete database interna; solo BE partecipa a entrambe. Un backend singolo conserva sessioni/upload/scheduler locali: non scalarlo ancora.

Le immagini contengono soltanto runtime/dipendenze, non codice WBE. `backend/`, `client/`, server frontend ed entrypoint sono bind mount; FE/BE leggono il sorgente in sola lettura. `client-build` è un tooling esplicito che esegue `npm ci` e Grunt sul checkout, come UID/GID dell'operatore. I dati pubblici necessari al backend sono copiati in `.local/resources`; nessun build frontend è montato nel backend. Dopo modifica Python/server FE riavviare il rispettivo servizio; dopo modifica Angular ricompilare. Ricostruire immagini quando cambiano dipendenze.

`bootstrap` genera segreti senza stamparli, conserva quelli esistenti e crea `.local/dev.env` con UID/GID host. Non aggiungere `.local` a Git o al contesto build. I tre file password PostgreSQL sono leggibili dal suo UID container ma la directory host `.local/secrets` è privata 0700; DSN owner/runtime sono 0600. Docker Compose locale monta file, non offre cifratura/secrets management orchestrato. Non eseguire bootstrap come root.

Il ruolo `wbe_owner` crea schema e oggetti. `wbe_runtime` dispone di DML e sequenze ma non DDL. I privilegi predefiniti del proprietario coprono oggetti creati da `init`/importatore. `wbe_phase1_test` è un database separato per test distruttivi, mai usare `wbe` come target dei test di reset schema.

Python 3.12, lockfile backend Noble (SQLAlchemy 1.4.50), psycopg2-binary 2.9.10, Node 24 e PostgreSQL 18 sono la combinazione verificata; le immagini base sono fissate ai digest verificati. Versioni provate: Python 3.12.15 e PostgreSQL 18.6. Le immagini applicative autonome restano un successivo passo di rilascio. Il runtime Debian bookworm stampa l'avviso upstream di piattaforma consigliata Noble/Trixie: le dipendenze Python usano comunque il lockfile Noble.

## Importazione e test

Mettere solo fixture autorizzate e snapshot SQLite congelati sotto `.local/imports`, con relativi allegati/chiavi in appdata separata. Non usare direttamente il DB live. Lo schema atteso è 69. L'importatore richiede target vuoto e non copia allegati.

```sh
./scripts/dev/import-sqlite.sh .local/imports/fixture.db --dry-run
./scripts/dev/import-sqlite.sh .local/imports/fixture.db
./scripts/dev/migrate.sh check --working-path /var/globaleaks
./scripts/dev/smoke.sh
# Suite serializzate sul solo database sintetico wbe_phase1_test.
./scripts/dev/test-backend.sh postgresql
./scripts/dev/test-backend.sh integration
# Compatibilità preesistente con SQLite:
./scripts/dev/test-backend.sh sqlite
python3 -m unittest discover -s tests/phase1 -p test_files.py -v
./scripts/dev/compose.sh run --rm --no-deps -v "$PWD:/workspace:ro" frontend node --test /workspace/tests/phase1/frontend.test.mjs
```

Per ripetere soltanto un’area backend usare per esempio `./scripts/dev/test-backend.sh postgresql globaleaks.tests.handlers.recipient`. I test PostgreSQL sono serializzati dal lock locale; non arrestare/ricreare il DB durante la loro esecuzione. Il collaudo Chromium opzionale e i flag per setup/invio/download sono documentati in `deploy/dev/frontend-server/README.md`.

Per i test unitari frontend senza Docker usare `node --test tests/phase1/frontend.test.mjs`. `smoke` verifica readiness HTTP e schema, non sostituisce prove login, invio, ricevuta, allegati, crittografia e autorizzazioni.

Per gli allegati usare `verify-files.py` prima e dopo la copia, con fixture congelata e destinazione nuova; non unire file in appdata di un backend attivo:

```sh
python3 scripts/dev/verify-files.py --snapshot .local/imports/fixture.db --source-appdata .local/imports/fixture-appdata --destination .local/imports/verified-files --manifest .local/imports/files-manifest.json
```

Il manifest conserva conteggi, dimensioni e SHA256 senza leggere contenuti in output. Il comando verifica schema, riferimenti ai file e assenza di upload in attesa; rifiuta file mancanti e destinazione esistente. La directory verificata contiene `files/` e `attachments/`: predisporre l'appdata di destinazione a backend fermo e conservare separatamente configurazione/chiavi della copia autorizzata. Il port DB non rigenera chiavi né ricifra allegati.

Notifiche disabilitate nel laboratorio (`WBE_DISABLE_NOTIFICATIONS=1`), Tor usa soltanto appdata nuova. I tmpfs proteggono runtime e file temporanei; il riavvio del container perde sessioni e materiale temporaneo, coerentemente con il limite mono-BE della Fase 1.

## Backup coordinato e restore isolato

```sh
./scripts/dev/compose.sh stop frontend backend
./scripts/dev/backup.sh
./scripts/dev/compose.sh start backend frontend
./scripts/dev/restore.sh .local/backups/TIMESTAMP
```

Il backup rifiuta servizi applicativi attivi e produce dump custom PostgreSQL, archivio appdata (esclude tmpfs), archivio privato di segreti/configurazione e SHA256SUMS. Conservare insieme dump, file e chiavi; i vecchi backup SQLite non includono PostgreSQL. La directory è privata e contiene dati/chiavi sensibili; nella produzione futura occorrono cifratura e destinazione indipendente.

Il restore verifica digest e rifiuta path assoluti, traversal, symlink e file speciali negli archivi; crea un database nuovo `wbe_restore_TIMESTAMP` e una directory nuova `.local/restore-TIMESTAMP`, senza sovrascrivere il laboratorio corrente. Non ripristina automaticamente le credenziali archiviate: sono destinate al recupero controllato del cluster originale. La prova va completata con `check` puntando un file DSN owner al DB ripristinato, confronto conteggi e lettura/decrittazione di una fixture. Il restore non avvia una seconda istanza e non cambia il DSN dell'istanza corrente. Conservare le evidenze; eliminare il target di prova solo dopo verifica.

## Operazioni e diagnosi

```sh
./scripts/dev/compose.sh ps
./scripts/dev/compose.sh logs --tail 100 backend frontend
./scripts/dev/compose.sh restart backend frontend
./scripts/dev/compose.sh down
```

`down` preserva volume PostgreSQL e appdata; **`down -v` elimina i volumi DB di sviluppo**. Non usarlo per risolvere un errore di migrazione. I segreti generati non vengono rigenerati al restart; modificarli richiede rotazione SQL coerente. Readiness negativa con DB spento è attesa; al ritorno verificare API e riconnessione pool, senza accettare un SQLite alternativo.

`backend/bin/gl-admin` è SQLite-only e rifiuta esplicitamente le operazioni quando è configurato PostgreSQL, per evitare backup incompleti o modifiche al DB sbagliato. Usare la UI amministrativa e gli script di questo runbook.

Il futuro DB remoto si configura tramite file DSN e TLS verificato (`sslmode=verify-full`, CA esplicita); la rete locale Compose non è una configurazione TLS per VM remota.

Per verificare l’indisponibilità nel laboratorio, a suite e migrazioni terminate: fermare solo `postgres`, verificare che `/healthz` sul FE restituisca 503 e che non compaiano nuovi `.db` in appdata, quindi riavviare `postgres` e ripetere lo smoke. Questa è una prova di recupero, non di failover HA. Ripristinare sempre il servizio DB anche se un’asserzione fallisce.

## Evidenze di esecuzione del 26 ottobre 2026

- Bootstrap/Compose e build runtime completati; build frontend dal sorgente attuale tramite npm lockfile e Grunt completata.
- Tre container healthy; smoke frontend/API/schema restituisce schema 69, revisione 2.
- PostgreSQL runtime rifiuta CREATE, DROP e UPDATE della revisione con SQLSTATE 42501; owner separato.
- Due test unitari frontend e quattro test Chromium reali superati, inclusa decrittazione allegato. Dopo i riavvii, altri tre test browser sulla fixture persistente superati.
- Suite SQLite: 648 superati; dopo le correzioni, 55 test delle aree coinvolte superati. Suite PostgreSQL finale: 629 superati e 19 esclusioni SQLite previste, zero errori. Integrazione PostgreSQL: 15 superati.
- Stop DB: readiness 503 senza fallback; restart DB: readiness 200 e recupero pool senza restart backend. Ripristino revisione 2 con due allegati verificati: dettagli e differenze di audit successive al backup nel rapporto di implementazione.
- Backup coordinato e restore isolato provati: database `wbe_restore_20261026164552`, schema 69/revisione iniziale 1 e conteggi delle 35 tabelle coincidenti. La fixture iniziale non conteneva allegati: questa prova non dimostra decrittazione file reali.
- Una ricreazione PostgreSQL durante la prima prova ha interrotto una suite parallela; non eseguire operazioni lifecycle sul DB mentre sono attivi test. Esiti consolidati e limiti del collaudo sono riportati in `WBE_PHASE1_IMPLEMENTATION.md`.
