# Collaudo isolato con copia reale

Questo stack usa il progetto Docker `wbe-rehearsal`, database e volume propri,
segreti separati in `.local/rehearsal/secrets` e appdata in
`.local/rehearsal/appdata`. Non condivide database o appdata con `wbe-refact` o
con la produzione. I sorgenti FE/BE e le risorse statiche vengono montati in
sola lettura dal checkout. Le immagini runtime devono essere già costruite dal
progetto di sviluppo; nessun codice applicativo viene incorporato qui.

Da `/opt/apps/wbe-refact`:

```sh
./scripts/rehearsal/bootstrap.sh
./scripts/rehearsal/compose.sh config --quiet
```

Questi comandi preparano solo la configurazione: non avviano container, non
importano dati e non toccano la produzione. Il wrapper imposta sempre il nome
del progetto, il file Compose e la directory radice corretti.

Il frontend pubblica esclusivamente `127.0.0.1:18091`. Dal PC:

```sh
ssh -N -L 18091:127.0.0.1:18091 ibladmin@IP_SERVER
```

Aprire `http://localhost:18091`. Le reti Docker `web` e `database` sono
`internal: true`: backend e PostgreSQL sono collegati esclusivamente a queste
reti, senza connettività Internet in uscita. Solo il frontend è collegato anche
a `ingress`, necessaria a Docker per pubblicare la porta loopback. Nessuna
porta è pubblicata su interfacce esterne; Traefik è esplicitamente disabilitato
tramite label su tutti i servizi.
Il backend non pubblica porte; PostgreSQL non pubblica porte. Nessun container
condivide reti della produzione o dello sviluppo.

L'ambiente imposta `WBE_REHEARSAL=1` e `WBE_DISABLE_NOTIFICATIONS=1`. Il backend
esegue soltanto il job locale Delivery per la gestione di segnalazioni/file;
non avvia Tor, notifiche, pulizie per scadenza o controlli esterni. I redirect
canonici da IP e l’header Onion-Location non rimandano alla produzione in
questa modalità. La configurazione richiede frontend separato e notifiche
disabilitate, altrimenti l’avvio è rifiutato. Non copiare configurazioni di servizio o
identità Tor della produzione. Conservare solo il materiale applicativo
necessario alla lettura della copia, secondo la procedura di importazione.
Non eseguire fixture sintetiche o suite che ricreano schemi sul database reale.

Il servizio `migrate` (profilo `tooling`) usa l'utenza proprietaria separata;
il backend usa l'utenza runtime. Il PostgreSQL isolato riusa lo script di
inizializzazione ruoli di sviluppo; l'ulteriore database `wbe_phase1_test`
creato da questo script resta vuoto e non autorizza test sui dati reali.
Non usare `migrate init` quando si deve importare uno snapshot: l'importatore
richiede un database vuoto. L'importazione e l'avvio seguono la procedura di
collaudo e devono essere eseguiti solo dopo la validazione dello snapshot.

Questo ambiente contiene dati reali: accesso riservato agli operatori del
collaudo, niente pubblicazione in LAN o Internet. Non costituisce la migrazione
definitiva o una configurazione HA. La successiva pulizia deve eliminare solo
le risorse del progetto `wbe-rehearsal`, dopo autorizzazione esplicita.
