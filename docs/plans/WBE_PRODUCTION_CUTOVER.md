# Cutover WBE SQLite → PostgreSQL: procedura operatore

Data: 26 ottobre 2026. **Cutover eseguito sulla VM attuale.** Sorgente autorevole ora: PostgreSQL e appdata dello stack `wbe-production`. Il legacy è fermo, con monitor fermo e maintenance nel node.conf. Non riavviarlo e non ripristinare lo snapshot SQLite: il nuovo sito è aperto alle scritture.

## Esito operativo

- Freeze operatore: 20:42:50 Europe/Rome. Backup legacy completo verificato dallo script operatore e copia finale privata acquisita.
- Schema completo verificato, marker normalizzato sulla sola copia, dry-run e import PostgreSQL riusciti; controllo schema riuscito. I manifest dei 9 file permanenti coincidono. Nessun reset delle utenze o delle credenziali.
- Apertura web verificata entro le 20:47:13: downtime circa 5 minuti. Homepage, canale, API JSON e asset HTTP 200. Browser reale a 375 e 1440 px senza overflow orizzontale.
- SMTP: connessione diretta, TLS e autenticazione verificati dal container, senza invio di messaggi di prova. Notifiche applicative riabilitate; questo controllo non certifica la consegna finale delle email né il percorso SMTP via Tor.
- Tor riabilitato dopo cambio rotte, con identità importata: richieste end-to-end sulla rete onion alla pagina e alle API HTTP 200. Nessun hostname/chiave onion incluso nel repository.
- Rehearsal dismesso dopo backup finale verificato: rimossi i soli container/reti/volume del progetto `wbe-rehearsal`, svuotata la sua appdata. Backup e snapshot privati conservati. Il laboratorio sintetico separato `wbe-refact` non è stato eliminato.
- Tutti e tre i container production healthy; vecchi app e timer inattivi. Il timer legacy risulta ancora enabled: richiesto all’operatore `sudo systemctl disable --now wbe-monitor@node1.timer` per impedirne la riattivazione al boot. Verifica funzionale confermata dall’operatore dopo il cutover: login con credenziali precedenti e apertura di un allegato esistente riusciti.

Le sole configurazioni dinamiche WBE sono state aggiornate, senza riavviare Traefik. Durante il caricamento il provider ha rifiutato `routers: {}` nel file degli alias: corretto conservando il solo redirect della base canale; la riscrittura del documento è gestita dal FE. Il caricamento successivo e gli accessi pubblici sono riusciti. Configurazioni originali, dump e manifest sono conservati in `.local/production/` con accesso privato.

**Rollback dopo apertura:** conservare tutte le nuove scritture; eventuali guasti vanno gestiti sul nuovo stack o con una migrazione inversa validata. Non riattivare semplicemente SQLite. Il backup originale rimane conservato per recupero e confronto.

Le sezioni seguenti descrivono preparazione e procedura storica della finestra appena eseguita; lo stato corrente è quello riportato sopra.

## Aggiornamento implementazione — stack Docker sulla VM attuale

Decisione esplicita dell'utente: prima messa online sulla VM attuale; HA tra server rinviata. Manifest `deploy/production/compose.yml`, wrapper e strumenti `scripts/production/` ora implementati. Le indicazioni sotto che descrivono questi file come mancanti sono superate da questo aggiornamento; i gate operativi restano obbligatori.

Lo stack `wbe-production` è avviato con **soli dati sintetici**, separato da produzione legacy e rehearsal. PostgreSQL è interno; FE/BE leggono sorgenti tramite bind mount. FE e BE condividono il namespace di rete per il listener onion loopback, ma restano processi/container separati. Non rappresenta ancora una soluzione HA o a repliche indipendenti.

Ingresso web: Traefik HTTPS → `127.0.0.1:18092` → FE → socket Unix privato BE. Il FE accetta solo peer proxy espliciti, protocollo HTTPS e ultimo IP della catena X-Forwarded-For; elimina le asserzioni provenienti dal browser. Ingresso onion separato su loopback 8085 → FE → socket Unix onion. Il backend conserva le chiavi onion importate. Pubblicazione onion disabilitata durante preparazione; notifiche disabilitate nella prova sintetica.

Verificato il 26 ottobre: tre container healthy; login amministratore sintetico verificato in browser su HTTPS; percorso reale tramite istanza Traefik isolata TLS restituisce 200 per pagina e `/api/public`; 4 test frontend, 11 ingressi/Tor e 13 preparazione snapshot superati. Anche lo snapshot reale offline già usato in rehearsal coincide con lo schema canonico completo. Verificato inoltre accesso end-to-end sulla rete Tor con identità esclusivamente sintetica: pagina e API HTTP 200 dopo pubblicazione. Il primo tentativo era scaduto; ripetizione riuscita. Pubblicazione disabilitata al termine. Questi risultati non sostituiscono la prova autenticata, il download/decifratura allegati e SMTP sul candidato finale.

`prepare-snapshot.py` confronta struttura completa (DDL, colonne, vincoli e indici), integrità, FK e upload pendenti prima della normalizzazione 68→69 della sola copia. Produce una nuova directory privata con hash e manifest; non opera sul nodo live. Ripetere sulla copia finale congelata.

Configurazioni Traefik pronte in `deploy/production/traefik/`, **non installate**: endpoint FE 18092, rimozione dai soli router WBE dei middleware che cancellano X-Forwarded-For o sovrascrivono le policy applicative; routing canali delegato al FE. Non modificare i middleware condivisi o altri servizi. La configurazione statica attuale accetta forwarded headers: il FE usa l'ultimo IP aggiunto da Traefik, non il primo fornito dal browser; verificare anche la configurazione effettiva prima del cutover.

Verificato anche backup consistente con FE/BE fermi, checksum, integrità archivi e ripristino del dump in un database sintetico temporaneo separato (poi eliminato). Prima del freeze: completare verifica SMTP, maintenance e prova finestra; ripetere il controllo Tor con identità finale dopo il passaggio. Poi rimuovere esclusivamente i dati sintetici della destinazione (marker privato `SYNTHETIC_ONLY`), preservando backup, e importare lo snapshot finale. Vietato applicare i template al database sintetico. Le configurazioni e i segreti in `.local/` non vanno in Git.

L'arresto del legacy richiede un operatore con sudo; l'agente non dispone di sudo non interattivo. **Non eseguire ancora il comando di freeze** finché i gate sopra non risultano chiusi.

## Autorizzazione, responsabilità e blocchi

L'utente ha autorizzato eliminazione dei soli dati di rehearsal, nuova migrazione dalla produzione, passaggio Traefik e successivamente Tor. L'agente non dispone di sudo non interattivo: non sono stati arrestati servizi di produzione, cancellati dati, acquisiti nuovi snapshot produttivi o cambiati routing. Il collaudo è stato brevemente fermato e riavviato per salvarne un backup coerente prima di qualsiasi pulizia. Le operazioni privilegiate vanno eseguite dall'operatore in terminale; non inviare password o file segreti in chat.

Prima della finestra chiudere questi blocchi:

1. Manifest e wrapper **production** revisionati, con destinazione PostgreSQL, file, credenziali, restart, backup, rete/SMTP/Tor e endpoint FE espliciti. Il compose rehearsal esistente usa `WBE_REHEARSAL=1`, notifiche disabilitate e reti BE/DB interne: non basta collegarlo a Traefik. Se HA resta requisito della prima messa online, il singolo PG/backend/frontend attuale non lo soddisfa: serve gate HA oppure decisione esplicita di scope differente.
2. Collaudo autenticato operatore con password/2FA, ricevuta e decifratura allegati completato. Nessun reset credenziali durante migrazione.
3. Procedura di confronto strutturale 68/69 ripetibile e revisionata. Il precedente snapshot aveva marker 68 ma struttura 69: non implica che ogni futuro DB possa essere rietichettato. È disponibile `scripts/production/prepare-snapshot.py`, che rifiuta qualsiasi differenza strutturale.
4. Rehearsal dell'intera finestra, backup compreso, con massimo 60 minuti e tempo di rollback misurato; prova di ripristino backup su destinazione isolata. Assegnare responsabile GO/NO-GO e operatore rollback.
5. Maintenance HTTPS predisposta e provata; blocco di nuovi ingressi prima del drain, inclusa la vecchia onion. Il servizio `wbe-maintenance-service` presente punta a 8889, ma la sua esistenza nel YAML non prova che risponda.

Non iniziare il fermo finché questi gate non sono chiusi. Non promuovere il rehearsal per aggirare un gate.

## Preparazione prima del fermo

Fissare commit/build backend e frontend; conservare gli artifact testati, evitare build e installazioni durante il fermo. Annotare privatamente timestamp UTC, tempi limite, volumi, percorsi, UID/GID e checksum. `umask 077`; nessun `set -x`, DSN in argv, dump dati o output completo di Docker env/config.

La procedura assume un wrapper production revisionato chiamato `scripts/production/compose.sh` con servizi `postgres`, `backend`, `frontend`, `migrate` e opzioni migrator uguali a rehearsal. **Il wrapper è ora implementato e verificato nello stack sintetico; non implica che il database candidato contenga già i dati finali.** Deve usare progetto e segreti production separati da `wbe-refact` e `wbe-rehearsal`, appdata permanente dedicata e destinazione PG vuota. Non usare `migrate init` prima dell'import.

Verifiche operatore prima di iniziare:

```sh
cd /opt/apps/wbe-refact
systemctl is-active wbe-app@node1.service wbe-monitor@node1.timer traefik
./scripts/rehearsal/compose.sh ps
python3 -m unittest discover -s /opt/apps/wbe/install/traefik/tests -v
```

Conservare privatamente copia dei file dinamici Traefik `20-wbe-kronosfinance.yml` e `25-wbe-channel-aliases.yml`, codice/build attivi e configurazione nodo. Non modificare altri router (in particolare Flow). Non copiare segreti nel repository o nei report. Verificare spazio per backup completo, copia frozen, copia lavoro e PG/WAL; registrare tempo massimo backup verificato. Preparare endpoint production loopback e URL health, senza assumere 18091 (porta rehearsal).

### Pulizia esclusivamente rehearsal

Può precedere il fermo, dopo la conclusione del collaudo. Fermare solo il progetto esplicito:

```sh
./scripts/rehearsal/compose.sh stop frontend backend
./scripts/rehearsal/compose.sh ps -a
```

Inventariare volume PostgreSQL del container rehearsal con `docker inspect` mirato ai soli mount e label; verificare `com.docker.compose.project=wbe-rehearsal`. La rimozione va circoscritta al volume verificato e ai file di `.local/rehearsal/appdata`. Prima spostare appdata in quarantena privata con nome univoco per controllare il perimetro, poi eliminare solo quanto autorizzato. Gli snapshot in `.local/imports`, backup storici, `.local/dev`, dati production e segreti non fanno parte della pulizia. Non usare `docker system prune`, wildcard, `down -v` su progetto implicito o rimozioni ricorsive su `.local`. Il runbook non esegue questa pulizia; il nuovo import production usa una destinazione distinta e vuota.

## Fase 1 — freeze e backup completo

Il timer monitor può riavviare il servizio: fermarlo insieme al monitor prima dell'applicazione. Attivare maintenance sul solo host WBE; aspettare upload/Delivery conclusi. Fermare anche ingresso Tor legacy prima dello snapshot finale. Se upload rimangono pendenti, NO-GO: riaprire il legacy e completare il drain, non cancellare riferimenti.

Registrare inizio downtime, deadline totale e deadline abort = 60 minuti − tempo massimo rollback verificato − margine. Usare un osservatore indipendente del tempo; non avvolgere il backup in un timeout che possa uccidere la shell lasciando stato sconosciuto.

Comando esistente, da operatore privilegiato:

```sh
sudo /opt/apps/wbe/install/scripts/stop-and-backup-node1.sh
```

Lo script salva `node.conf.before-stop`, ferma monitor/timer, imposta `MAINTENANCE_MODE=Y`, ferma app, verifica assenza processo, archivia l'intero node1 con ACL/xattr, verifica gzip e SHA256. **Lascia tutto fermo**. In caso di errore non presumere servizi ripristinati: verificare stato e applicare rollback. Annotare il percorso esatto restituito, non usare `latest` o glob.

```sh
systemctl is-active wbe-app@node1.service wbe-monitor@node1.timer wbe-monitor@node1.service
# Atteso: tutti inattivi; il codice di uscita nonzero è normale.
```

Verificare anche processi legacy effettivi e assenza del servizio onion precedente. Vietato avviare app o timer fino al rollback o alla definitiva dismissione.

**Non usare `scripts/dev/snapshot-production.py` per questo cutover:** il suo `finally` riavvia app e timer, consentendo nuove scritture dopo la copia. È corretto per rehearsal, non per freeze finale.

## Fase 2 — snapshot finale e revisione schema

Dopo backup valido e freeze confermato, copiare appdata in percorso nuovo privato. Esempio eseguito dall'operatore; `cutover_stamp` deve essere univoco e registrato:

```sh
umask 077
cutover_stamp=$(date -u +%Y%m%dT%H%M%SZ)
cutover_root=/opt/apps/wbe-refact/.local/imports/cutover-$cutover_stamp
sudo install -d -m 0700 "$cutover_root"
sudo cp -a -- /opt/apps/wbe/node1/appdata "$cutover_root/source-appdata"
sudo cp -a -- "$cutover_root/source-appdata" "$cutover_root/work-appdata"
```

La copia source resta immutata. Preservare permessi; se necessario concedere all'operatore accesso **solo alle nuove copie**, senza modificare node1 e senza seguire symlink. Registrare SHA256 DB sorgente prima/dopo preparazione. DB, file e identità onion possono contenere segreti: non stamparli né caricarli in artifact pubblici.

Su source e work eseguire verifiche offline read-only: `PRAGMA integrity_check`, `PRAGMA foreign_key_check`, marker version_db e count internalfile.new=1. Output solo esito/contatori tecnici, mai righe applicative. Il DB di lavoro deve avere schema 69 valido:

- Marker 69: confrontare struttura completa al modello della build fissata; procedere solo su corrispondenza.
- Marker 68 con **tutte** le tabelle/colonne/tipi/nullabilità/default/PK/FK/indici equivalenti al modello 69: normalizzazione del solo marker sulla copia work, transazione esplicita e report prima/dopo; verificare che nessun altro valore sia cambiato. Il dry-run importer verifica tabelle/colonne e valori ma **non sostituisce** il confronto strutturale completo.
- Schema realmente 68: applicare migrator storico 68→69 esclusivamente alla copia isolata, senza daemon, Tor, rete o job, usando procedura provata in rehearsal. Non chiamare startup generale sul clone. Verificare nuovo schema, dati e marker dopo commit.
- Qualsiasi altra situazione: NO-GO. Non correggere il live e non ignorare incongruenze.

Non eseguire UPDATE manuali del marker: utilizzare `scripts/production/prepare-snapshot.py` sulla copia staged per il confronto completo e la normalizzazione controllata. Se la revisione supera deadline abort, rollback.

## Fase 3 — file e import PostgreSQL

Il tool esistente copia esclusivamente `files` e `attachments` verso directory nuova, rifiuta symlink/file mancanti/upload pendenti e confronta SHA256. Impostare `production_appdata` sul percorso **esatto revisionato nel manifest production**, inesistente e distinto da rehearsal e node1. Aggiungere `--destination "$production_appdata"` solo dopo verifica del percorso e UID/GID del runtime. Esempio controllo senza copia:

```sh
python3 scripts/dev/verify-files.py \
  --snapshot "$cutover_root/work-appdata/globaleaks.db" \
  --source-appdata "$cutover_root/work-appdata" \
  --manifest "$cutover_root/files-source.json"
```

Con la destinazione nuova e approvata:

```sh
python3 scripts/dev/verify-files.py \
  --snapshot "$cutover_root/work-appdata/globaleaks.db" \
  --source-appdata "$cutover_root/work-appdata" \
  --destination "$production_appdata" \
  --manifest "$cutover_root/files-copied.json"
```

Controllare ownership senza chmod permissivi. Non montare il clone completo nel runtime: log, SQLite, Tor e configurazioni reference-only non vanno promossi implicitamente. Config/chiavi conservati nel DB sono importati senza reset/ricifratura. Materiale Tor segue la fase dedicata successiva.

Comandi contrattuali del wrapper production **da implementare e validare prima del fermo**:

```sh
./scripts/production/compose.sh up -d postgres
./scripts/production/compose.sh --profile tooling run --rm \
  -v "$cutover_root/work-appdata/globaleaks.db:/imports/source.db:ro" \
  migrate import-sqlite --working-path /var/globaleaks \
  --source /imports/source.db --runtime-role wbe_runtime --dry-run \
  > "$cutover_root/import-dry-run.json"
./scripts/production/compose.sh --profile tooling run --rm \
  -v "$cutover_root/work-appdata/globaleaks.db:/imports/source.db:ro" \
  migrate import-sqlite --working-path /var/globaleaks \
  --source /imports/source.db --runtime-role wbe_runtime \
  > "$cutover_root/import-result.json"
./scripts/production/compose.sh --profile tooling run --rm \
  migrate check --working-path /var/globaleaks > "$cutover_root/schema-check.json"
```

Verificare exit status di ogni comando prima del successivo. Il tool richiede PG vuoto, esegue import atomico, verifica vincoli/conteggi/digest di tutte le tabelle e riallinea sequence. Il dry-run non scrive tabelle ma verifica anche vuoto target. Non usare wrapper `scripts/dev/import-sqlite.sh`: punta al laboratorio sintetico. Dopo import, ripetere verify-files contro destination con nuovo manifest e confrontare inventario al precedente. In caso di errore non cancellare automaticamente il target: determinare se il commit è avvenuto e conservarne evidenza.

## Fase 4 — validazione privata e GO Traefik

Avviare target dietro accesso privato con job/email/Tor ancora governati dalla modalità di pre-cutover progettata; non assumere che togliere WBE_REHEARSAL sia sufficiente. Verificare FE `/healthz`, API `/api/health`, header/CSP e asset; HTTPS Host corretto senza redirect al vecchio backend, route home/slug/login/admin/API, 404 JSON corretti e nessun HTML al posto di API. L'operatore verifica autenticazione/2FA e allegati esistenti, senza creazione di segnalazioni tecniche in produzione.

**Ogni login o job può già scrivere nel target** (audit/last-access/Delivery), anche prima della pubblicazione. Tracciare da questo momento tutte le scritture target. Se rimangono esclusivamente effetti tecnici controllati sul clone e nessuna azione reale, un abort può scartarli esplicitamente. Dal primo accesso pubblico o nuova azione reale non è consentito tornare al vecchio snapshot perdendo modifiche.

Il routing letto è in `/opt/apps/wbe/install/traefik/dynamic/20-wbe-kronosfinance.yml`: servizio condiviso `wbe-kronosfinance-https`, URL `https://127.0.0.1:8443`, `serversTransport: insecure-transport`. Anche i router prioritari del file `25-wbe-channel-aliases.yml` usano questo servizio.

Preparare prima del fermo una copia candidata che modifica **solo il servizio condiviso** verso l'endpoint frontend production loopback verificato. Se il nuovo hop è HTTP loopback, rimuovere dal servizio il `serversTransport` TLS precedente; se HTTPS, predisporre trasporto appropriato. Preservare router, TLS pubblico, middleware, priorità e esclusioni API. Non introdurre un router concorrente che lasci gli slug sul vecchio backend.

Validare YAML e diff, test routing, backup originale e permessi; installare candidato mediante file temporaneo sulla stessa filesystem e rename atomico al percorso del provider. Il watch dinamico evita restart Traefik. Confermare caricamento senza errori e verificare da origine pubblica home, slug/report/login, API JSON, asset e allegati. Non stampare log con token o contenuti. Solo dopo esito positivo togliere maintenance sul nuovo servizio e annotare punto di apertura scritture. Legacy app/timer restano spenti.

## Fase 5 — Tor dopo Traefik

Non avviare il target con identità onion diversa per errore né due Tor con la stessa identità. Prima identificare in configurazione/codice il responsabile Tor del nuovo deployment, modalità di egress e directory persistenti. La presenza di reti Docker internal impedisce il Tor di produzione: l'egress controllato e i permessi devono essere già progettati/testati.

Preservare l'identità onion tramite copia protetta del materiale necessario dal frozen snapshot, non rigenerarla. Verificare assenza del processo legacy; installare solo le chiavi/config richieste nel percorso runtime production previsto, proprietario e mode corretti. Puntare HiddenServicePort al **frontend completo** che serve client e proxy API, non al backend separato. Non esporre control port/SOCKS pubblicamente. Avviare un solo servizio Tor, verificare bootstrap e raggiungibilità dell'onion esistente dal browser Tor: home, canali, login, API e allegati. Verificare Onion-Location e URL canonici dopo abilitazione.

Il manifest production e i comandi di gestione Tor non esistono ancora nella configurazione ispezionata: questa fase è un gate bloccante, non un `systemctl start tor` generico. Se HTTPS è già aperto e Tor fallisce, correggere Tor mantenendo PostgreSQL autorevole; non riavviare node1 con DB vecchio.

## Rollback e completamento

Prima di scritture reali target: ripristinare maintenance, fermare target web/backend/job/Tor; ripristinare atomicamente file Traefik originali; conservare PG/file target per diagnosi; verificare node1 originale intatto e ripristinare solo MAINTENANCE_MODE al valore salvato in `node.conf.before-stop` (non sovrascrivere indiscriminatamente altre impostazioni). Avviare legacy app, verificare HTTPS/onion, poi timer monitor; rimuovere maintenance e verificare accesso. Non estrarre tar sopra node1 senza necessità: il live non è stato modificato nei dati. Se necessario restore completo, usare procedura già collaudata in finestra; il backup appena creato, non rollback storico.

Dopo nuove scritture reali target: **rollback snapshot vietato**. Fermare ingressi se serve, backup consistente PG+file, correggere avanti. Una migrazione inversa che conserva nuove scritture richiede strumento e prove specifici e non è disponibile. Anche rollback di solo codice deve essere compatibile con schema PG e formato file correnti.

Fine: monitorare errori, code notifiche/Delivery, storage e backup; eseguire backup coordinato production PG+file con restore provato. Conservare backup frozen e legacy spento per periodo concordato, senza pulizie automatiche. Annotare report privato con esiti, tempi, hash, revisione schema e GO, senza dati personali/chiavi. La rimozione del nodo legacy richiede un'attività separata.

## Stato eseguito prima del commit

Backup del collaudo salvato privatamente in `.local/rehearsal/backups/20261026T190613Z`: dump PostgreSQL, appdata permanente, configurazione/segreti e SHA256SUMS. Verificati gzip e catalogo pg_restore; questo non sostituisce una prova di ripristino completa. FE/BE rehearsal riavviati. Pulizia, nuova migrazione, switch Traefik e Tor non eseguiti.
