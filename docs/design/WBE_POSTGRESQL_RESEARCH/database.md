# Analisi database WBE — 26 ottobre 2026

Scope: lettura codice /opt/apps/wbe/node1/backend e confronto mirato con /opt/apps/wbe/repos/WhistleblowingEasy-upgrade/backend. Nessuna lettura di contenuti DB, nessun accesso segreti, nessuna modifica runtime. Non sono stati eseguiti test o import. Nessun AGENTS.md trovato nelle directory leggibili; ricerca estesa ha incontrato directory deployment non accessibile e directory estranee, senza ulteriori tentativi.

## Risultato

Migrazione realizzabile come evoluzione del fork, non cambio configurazione. SQLAlchemy aiuta la portabilità ma il prodotto è SQLite-specifico nel lifecycle DB, hardening, test, backup e concorrenza. Prima release richiesta HA completa: non confondere DB remoto con backend replicabile. PostgreSQL primario/standby sincrono più quorum/fencing non correggono automaticamente race applicative.

Codice locale dichiara GlobaLeaks 5.0.99, schema 69, minimo migrabile 52: `node1/backend/globaleaks/__init__.py:9-13`. Gli equivalenti nel repository upgrade coincidono; confronto byte dei file orm.py, models/__init__.py, db/migration.py restituisce identità. Non inferire identità dell'intera installazione né versione DB live.

## Evidenze e lavoro necessario (percorsi relativi a /opt/apps/wbe)

- `node1/backend/globaleaks/orm.py:30-31`: URI costruita SQLite; `:47` engine nuovo a ogni get_session; `:66-85` hook connessione PRAGMA, setconfig, authorizer; `:91-92` sessione lega nuovo engine. Implementare factory per dialect, engine singleton per processo, pool dimensionato per somma repliche/thread e max_connections; pre-ping/reconnect, timeout e TLS verificato, nessun DSN nei log.
- `orm.py:185-219`: commit/rollback e retry esclusivo di stringa "database is locked". Gestire SQLSTATE deadlock/serialization con budget finito e replay solo di transazioni idempotenti, mai retry cieco dopo commit dall'esito ambiguo durante failover. Session.close non basta a progettare ciclo vita del pool.
- `settings.py:95,119`: globaleaks.db imposto; `state.py:172-189` startup legge file SQLite per reachable_via_web. Tutti gli accessi precoci devono usare configurazione database, fallire chiuso se indisponibile, non trattare DB remoto non disponibile come installazione nuova.
- `db/__init__.py:19-39`: versione rilevata da file; `:42-57` create schema con PRAGMA; `:60-69` VACUUM; `:82-104` aggiornamento DB e cleanup a startup. Separare comando migrator esclusivo dal processo web, aggiungere schema version/status checks, readiness che non avvii istanza con schema errato. PostgreSQL vacuum è operazione DBA/autovacuum, non sostituire ciecamente.
- `db/migration.py:174-196,264-269`: copia old.db, DB intermedi in-memory, nuovo file e rename; `:126` data update apre ancora URI file. Tenere migrazioni legacy SQLite come preparazione schema 69; creare baseline PostgreSQL equivalente e migrazioni successive versionate (es. Alembic), mai far migrare tutte le repliche all'avvio.
- `models/properties.py:17-30`: JSON serializzato TEXT; `:33-50`: enum serializzato INTEGER. Prima migrazione preservare questa semantica, rinviare JSONB/enum nativi. Mappare bool reali, timestamp UTC con semantica corrente, stringhe e NULL; verificare Unicode/NUL, range interi, sentinel date. Testare DDL generato davvero su PG; compilazione ORM non è prova funzionale.
- `models/__init__.py:222-224,926-929`: autoincrement AuditLog/Tenant SQLite. Import conservando ID, riallineare sequence PostgreSQL; verificare generazione nuovo tenant e audit successiva.
- `models/__init__.py:249,306,383-384,442-447,883`: FK differibili e talvolta composite/self reference; importer rispetta dependency graph e vincoli differiti, niente disabilitazione globale dei vincoli in runtime. Preservare unicità tenant/slug e tenant/receipt (`:383,:653`).
- `handlers/whistleblower/submission.py:138-141`: contatore progressive read-modify-write su Config JSON-text senza lock. In READ COMMITTED due transazioni possono perdere incremento: usare row lock SELECT FOR UPDATE su riga per tenant o contatore atomico dedicato con RETURNING; test parallelo e vincolo di unicità coerente con semantica. `:144-152` check-then-insert ArchivedSchema richiede gestione conflitto univoco/idempotenza. Inventario completo di pattern analoghi è necessario.
- `jobs/notification.py:83-90` query aggregata; `handlers/admin/auditlog.py:38-59` aggregazioni. Non è emersa SQL raw applicativa massiva oltre PRAGMA/VACUUM; nessuna incompatibilità GROUP BY affermata senza esecuzione. Suite deve coprire query, ordinamento/collation e constraints PG.
- `models/__init__.py:643-648,958-964`: receipt hash, chiavi cifrate e escrow nel DB. Copiare esattamente valori, non rigenerare/ricifrare durante import. Backup richiede anche file allegati e tutte le componenti crittografiche, test decifratura con account/receipt di fixture.
- `settings.py:85-86`: attachments/tmp locali; `db/__init__.py:127-152`: DB traccia nomi file e cleanup elimina file non tracciati. In cluster un upload in corso su replica diversa rischia cleanup improprio: introdurre stato staging/committed, grace period e garbage collection unica coordinata. DB+object storage non hanno transazione atomica: protocollo esplicito di publish, compensazione, retry e riconciliazione.
- `bin/gl-admin:92-104,108-135`: backup ferma systemd globaleaks e crea tar workdir, restore estrae tar. Non contiene backup del futuro PostgreSQL remoto. Nuovo backup coordinato include PG (base backup/WAL PITR) + versioni storage + manifest/config/chiavi con accessi separati e prova restore completa.
- `tests/helpers.py:650-657`: test fixture copia archived SQLite. Rendere harness parametrico SQLite/PG e aggiungere PG reale in CI. `tests/test_orm.py:58-85` prova hardening SQLite: per PG verificare ruoli runtime senza DDL/owner e privilegi minimi, search_path fissato, schema no public CREATE; admin migrator separato.
- Dipendenze distribuzione variano da SQLAlchemy 1.3.22 (bullseye) a 2.0.45 (resolute); `requirements/requirements.in.*:12-13`. Nessun driver psycopg trovato nel requirements set. Fissare immagine/versione Python, SQLAlchemy e driver supportati, poi testare; non promettere tutte le distro nella prima release.

## Architettura DB proposta (da validare con infrastruttura)

Primario PostgreSQL + standby sincrono su VM/host failure domain distinti, endpoint writer HA, orchestrazione promozione con quorum dispari e fencing del vecchio primary. Tre nodi PG se richiesto mantenere write availability dopo perdita di uno standby senza degradare durabilità; a due nodi sync il guasto dello standby può fermare commit. Definire esplicitamente contratto di disponibilità/RPO e testarlo. Nessun accesso pubblico; TLS verify-full, ruoli migrator/runtime/backup distinti, storage cifrato, WAL/backup protetti e retention coerente con cancellazione dati. secure_delete SQLite non ha equivalente diretto in MVCC/WAL/backups: nuova proprietà di cancellazione da definire e approvare, non dichiarare equivalenza.

Applicazioni scrivono solo writer; read replica opzionale per analisi tollerante lag in futuro, non necessaria a MVP HA. Pool totale = repliche × pool_size + overflow + workers + manutenzione; dimensionare con benchmark. In prima release preferire connessioni dirette con endpoint HA; PgBouncer solo se necessario e dopo test advisory lock/session state/pooling mode.

HA non è backup. PITR deve ripristinare DB e allegati allo stesso punto logico, evitando record senza file e file non referenziati; conservare manifest e versioni oggetti. Per requisiti di cancellazione ricordare che versioning e WAL prolungano conservazione anche di cifrato.

## Percorso implementativo e cutover entro 60 minuti

1. Inventario versioni/tenants/schema e volumi da metadata autorizzati; nessuno è stato acquisito qui. Congelare commit sorgente e formato schema. Separare change PostgreSQL da eventuale upgrade funzionale.
2. Spike isolato con fixture synthetic: DDL PG, porting lifecycle, engine, hardening, suite CRUD e crypto, concorrenza, import deterministico schema 69. Costruire importer versionato che legge snapshot SQLite solo read-only e scrive PG vuoto; conversioni esplicite, contatori righe, checksum canonici per tabella, vincoli e sequences. Mai logging dati/chiavi.
3. Prove ripetibili su clone autorizzato in staging: almeno due dress rehearsal completi e una abort/restore; timing import + check + switching + restore misurato. Allegati precopiati mentre il servizio gira, final delta solamente dopo fermo scritture. Snapshot DB finale coerente solo dopo stop di tutti i writer/jobs/upload; non usare shutil.copy live.
4. Prima del fermo: destinazione HA pronta, schema vuoto, build testata, endpoint preconfigurati, replica healthy, backup/restore verificati, capacità sufficiente. Se benchmark eccede budget, NO-GO; non improvvisare CDC SQLite o dual-write. Ridurre tempi con precopia storage e importer parallelo solo se provato.
5. Durante fermo: maintenance sul LB, drain upload, stop jobs e writer, freeze, snapshot completo consistente, import e delta files, validazione FK/count/hash/keys/files, sequence reset, startup cluster in accesso controllato e smoke non distruttivi. Riservare margine per rollback misurato.
6. Deadline abort = 60 minuti meno tempo massimo di riavvio/restore legacy misurato meno margine. Non assegnare minuti arbitrari: runbook compilato dai rehearsal. Fino all'apertura scritture PG si può rientrare sullo snapshot SQLite intatto e storage coerente. Verificare vecchio scheduler spento e impedire split-brain tra sistemi.
7. Dopo primo commit applicativo PG, rollback a snapshot SQLite causa perdita dati ed è proibito: roll-forward/hotfix oppure reverse migration completa e validata che includa nuove scritture/allegati. Definire questo punto di non ritorno nel runbook prima del GO. La finestra <60 minuti è criterio di accettazione verificato, non garanzia già ottenuta.

## Gate test per prima release HA

- Suite backend PG e SQLite dove mantenuto; contratti API, tenant isolation, ruoli, receipt, MFA, escrow e login/decifratura; roundtrip allegati/voce.
- Import: conteggi, FK, uniqueness, checksum canonici, JSON/enum/NULL/date, sequences, ID e valori crypto byte-identici, associazione file e campioni decifrati.
- Concorrenza multi-replica: progressive, schema archiviato, invio/commenti/upload, notifiche (duplicazioni), aggiornamenti config e cancellazioni.
- Failover durante transazione/commit, rete divisa, primary fenced, standby indisponibile, perdita quorum, pool reconnect e carico; nessun doppio primario e nessuna perdita dei commit riconosciuti nel modello di guasto dichiarato.
- Restore PITR completo con allegati e chiavi, corruzione/mancanza oggetti, retention, esercitazione abort entro un'ora.
- Benchmark dataset/tenant/concorrenza rappresentativi: P95/P99, latenza writer remote, memoria pool/thread, IOPS, WAL, crescita e tempi backup/import. Non disponibili numeri di sizing attuali.

## Effort orientativo, non preventivo

Solo workstream DB: discovery/spike 1–2 settimane-persona; porting lifecycle/driver/migrations/concurrency 3–5; importer/validation/backup 2–4; HA integration/failover/performance 2–4. Totale indicativo 8–15 settimane-persona con sovrapposizioni e incertezza elevata; non sommare ciecamente ad altri workstream condivisi. Nessuna stima calendario affidabile senza dimensioni dati, RTO/RPO, infrastruttura, staffing e risultati spike. HA frontend/backend/sessioni/storage è ulteriore lavoro da coordinare con gli altri agenti.
