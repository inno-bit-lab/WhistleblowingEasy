# WBE: riferimento operativo della macchina

Aggiornato il 1 ottobre 2026. Questa guida descrive lo stato verificato dopo l'aggiornamento e il restyling. Non eseguire i vecchi script di installazione/migrazione come procedure di aggiornamento corrente.

## Stato e percorsi

- Produzione: `/opt/apps/wbe/node1`. Codice backend in `backend/globaleaks`, virtualenv in `backend/env`, client distribuito in `client/build`.
- Dati reali: `node1/appdata` (database, allegati, chiavi e log). Non copiare questi dati nel repository e non eliminarli durante build/deploy.
- Repository di lavoro: `/opt/apps/wbe/repos/WhistleblowingEasy-upgrade`; remoto `inno-bit-lab/WhistleblowingEasy`; branch `upgrade/globaleaks-5.0.99`. Il checkout `repos/WhistleblowingEasy` è il riferimento storico precedente.
- Base applicativa GlobaLeaks 5.0.99, Python 3.12, client Angular 21; schema database della fork **69** (upstream iniziale 68).
- Configurazione: `node1/node.conf`, `conf/.common_wbe`, `scripts/.common_node_wbe`. Trattare configurazioni mail, certificati e chiavi come riservati.
- Il codice sotto node1 può essere una copia di installazione: il sorgente per nuovi interventi è il checkout upgrade. Il restyling è compilato nel client distribuito, non necessariamente nei sorgenti client copiati originariamente nel nodo.
- Utente servizio `iblapps`; operatore `ibladmin` nei gruppi `iblapps`, `traefik`, `docker`. Diverse operazioni su log, dati e systemd richiedono sudo; non allargare i permessi dei dati per comodità.

## Servizi e automatismi

`wbe-app@node1.service` avvia `scripts/startup_node.sh --node-name node1` in foreground, con restart su errore. Runtime Tor e socket in `/run/wbe-node1` tramite RuntimeDirectory. Tor è disponibile in `/usr/sbin/tor`: serve al canale anonimo onion e alle funzioni di rete previste da GlobaLeaks, non è il reverse proxy HTTPS.

`wbe-monitor@node1.timer` esegue il monitor ogni 3 minuti. Il monitor controlla il processo, rispetta `MAINTENANCE_MODE=Y`, invia le notifiche previste e gestisce lo stato WARN/throttling. La dipendenza systemd avvia l'applicazione: fermare solo il processo non costituisce manutenzione stabile.

Controlli:

```sh
systemctl status wbe-app@node1.service wbe-monitor@node1.timer traefik --no-pager
sudo journalctl -u wbe-app@node1.service -n 100 --no-pager
sudo tail -n 100 /opt/apps/wbe/node1/appdata/log/globaleaks.log
sudo tail -n 100 /opt/apps/wbe/node1/appdata/log/access.log
```

Backend HTTP 8082 e HTTPS 8443; Traefik usa HTTPS `127.0.0.1:8443`. La porta 8080 era già occupata: verificare `node1/node.conf` prima di cambiare porte.

## Traefik e URL

Traefik 3.1.0 è un binario host `/usr/local/bin/traefik`, gestito da `traefik.service`. `/etc/traefik` punta a `/opt/apps/wbe/install/traefik`. Provider file con watch; le modifiche dinamiche non richiedono restart. Provider Docker tramite socket locale.

- `20-wbe-kronosfinance.yml`: host WBE, servizio HTTPS backend, trasporto verso certificato locale.
- `25-wbe-channel-aliases.yml`: documenti dei canali, riscrittura interna su `/` e redirect degli slug base.
- `40-flowgest-docker-fallback.yml`: ripristino temporaneo Flow descritto sotto; è configurazione operativa della macchina, non un componente WBE.

Percorsi `/{slug}/report`, `/{slug}/login`, `/{slug}/admin/...`, `/{slug}/login/passwordreset`. `/{slug}` e `/{slug}/` reindirizzano con 302 a `/{slug}/report`, preservando query. Il browser mantiene lo slug sulle route supportate. I link legacy `/#/...` restano validi. Slug errato: pagina di cortesia bilingue.

**Escludere sempre `/api/...` e gli altri prefissi tecnici dalla regola slug.** L'intercettazione di `/api/admin/node` causava HTML 200 al posto di JSON e cancellazione della sessione admin. Non estendere le regex senza eseguire:

```sh
python3 -m unittest discover -s install/traefik/tests -v
```

Gli asset e le API sono assoluti; mantenere CSP `base-uri none`. Il campo slug è facoltativo e univoco per tenant, minuscolo alfanumerico con trattini, massimo 64 caratteri. Non usare i nomi riservati delle route tecniche/principali (api, login, admin, ecc.). La proprietà è esposta nell'editor amministrativo dei canali e risolta da `/api/public/channels/{slug}`. Un canale è presentato come organizzazione destinataria: lo slug **non crea un tenant né modifica permessi o isolamento dei dati**. Dettagli in `install/traefik/CHANNEL_ALIASES.md`.

## Personalizzazioni da preservare

- Avviso Tor e pulsante generico di nuova segnalazione della home nascosti come nella fork. La scelta singola resa checkbox conserva un solo valore.
- Italiano predefinito e inglese; stringhe aggiunte in `services/helper/kronos-translations.ts` e cataloghi i18n/l10n. L'integrazione runtime serve anche quando i cataloghi backend sono in cache.
- Home, login e recupero password navy/teal; footer distingue gestione Kronos Finance, manutenzione InnoBitLab e Powered by GlobaLeaks con relativi link.
- Pagina del canale: intestazione aziendale con logo in contenitore proporzionato, introduzione/guida/accesso tramite codice, informazioni e pulsante di apertura del modulo. Su mobile l'accesso tramite codice segue l'introduzione.
- Apertura e cambio passo spostano focus/vista al modulo, non alla cima della pagina. Campi a colonna, calendari leggibili, scelte e allegati uniformati; barra passi mobile compatta.
- Il logo usa object-fit contain, senza crop/deformazione. Il nome dell'azienda è testo indipendente dal logo.

File principali: `submission.component.{html,ts}`, `form*.component.html`, `whistleblower-submission.service.ts`, `homepage.component.css`, `client/app/css/main.css`, header/user, `channel-location.strategy.ts`, interceptor HTTP, traduzioni Kronos. Backend: modello Context, handler admin/public, richieste REST e migrazione 69.

## Build e deploy client

```sh
cd /opt/apps/wbe/repos/WhistleblowingEasy-upgrade
./client/node_modules/.bin/grunt --gruntfile client/Gruntfile.js --base client shell:build package
python3 /opt/apps/wbe/install/scripts/deploy-client.py
```

Se mancano dipendenze, usare il lockfile (`npm ci` in client) e i requisiti Python adatti alla distribuzione; non installare dipendenze durante l'avvio del servizio. La build scarica anche i font. Non basta copy:build dopo una modifica Angular/CSS: ricompilare.

Il deploy copia il build in staging, conserva i chunk per sessioni già aperte e sostituisce la directory con rename; nessun restart backend. Produce una copia precedente. Dopo verifica mantenere solo quella necessaria al rollback, non accumulare tutte le anteprime. Non distribuire mentre un'altra build/deploy sta scrivendo gli stessi percorsi.

Verificare home e canali a 320/375 px e desktop, italiano/inglese, accesso tramite codice, avanti/indietro/validazione, calendari e admin login. Non inviare segnalazioni vere per una prova tecnica. I test proxy sono inclusi nel workflow Tests; i test Cypress aprono esplicitamente il nuovo modulo con `cy.open_channel()`.

## Backend, backup e ripristino

Un deploy backend/migrazione richiede backup coerente dell'intero appdata (non solo SQLite), codice e configurazione, stop del monitor e servizio, verifiche e piano di ripristino. Non sostituire il DB live con una copia di test. La migrazione 68→69 è già avvenuta: non rieseguire lo staging storico.

Per un backup completo con nodo fermo:

```sh
sudo /opt/apps/wbe/install/scripts/stop-and-backup-node1.sh
```

**Lo script lascia app e monitor fermi e MAINTENANCE_MODE=Y.** Dopo conferma del backup, ripristinare la modalità precedente da `node.conf.before-stop` (o impostare N se era N), poi riavviare app e timer. Non modificare altre proprietà del nodo.

Conservati: backup originale `backups/node1-20261001-065217`, snapshot pre-migrazione slug `backups/channel-slugs-20261001-090447`, `node1old`, nodo 4.15.3 precedente e stato root di `analysis/deployments`/`last-upgrade-state`. Le build client precedenti sono in `node1/client/build-preview-previous-*`; il deploy della correzione CI ha conservato anche `build-preview-previous-20261001-113928`.

Rollback client: sostituire build con la copia precedente solo dopo aver salvato quella attiva; nessuna modifica a appdata. Rollback completo storico: `analysis/rollback-node1-5.0.99.sh` dipende dallo stato salvato e ripristina il nodo/dati di allora. **Non conserva automaticamente le segnalazioni nuove nel nodo ripristinato**; i dati attuali restano nel nodo rinominato. La regola slug è successiva al vecchio nodo: riesaminarla/disattivarla nel rollback. Uno schema 69 non è direttamente utilizzabile dal backend precedente.

## Improvement futuro: compatibilità Docker/Traefik (non eseguito)

Docker 29.1.3 richiede API almeno 1.44; il provider di Traefik 3.1.0 tentava API 1.24. Errore presente nei log dal 1 ottobre 2026 06:17:17 CEST. Container Flow sani, router Docker non caricati, risposta proxy 404.

Ripristino temporaneo file `40-flowgest-docker-fallback.yml`: replica Host `flow.innobitlab.it`, frontend porta 80, `/api` e `/health` backend porta 8001. IP al momento: 172.18.0.2 e 172.18.0.3. **Ricreare i container può cambiare gli IP**: verificare con docker inspect e aggiornare il file se necessario. Non rimuovere il fallback finché il provider automatico non è verificato.

Intervento futuro:

1. Scegliere una release stabile supportata di Traefik e rivedere le note di migrazione dalla 3.1.0. La correzione della negoziazione API è presente dalla 3.6.1: https://github.com/traefik/traefik/releases/tag/v3.6.1 . Verificare nuovamente le release al momento dell'intervento.
2. Backup binario, unità systemd, configurazioni e archivio ACME; questi ultimi contengono chiavi private. Scaricare release ufficiale linux/amd64 e verificare checksum.
3. Provare configurazione/provider su porte isolate e storage ACME separato, senza competere con produzione. Preparare il ripristino del binario vecchio.
4. Con finestra di breve indisponibilità, aggiornare binario e riavviare Traefik; non è necessario ricreare Docker o i container.
5. Verificare discovery Docker, Flow homepage/health/API e WBE home/slug/login/admin. Solo allora rimuovere il fallback file e ripetere le verifiche.

Log Traefik: `/var/log/traefik/traefik.log` e `access.log`. Non indebolire il requisito minimo API Docker come soluzione permanente. L'aggiornamento non è stato eseguito in questa sessione.

## Pulizia del 1 ottobre 2026

Eliminati i 119 percorsi approvati nel piano locale `analysis/CLEANUP-PLAN-20261001.json`, con risultato in `analysis/CLEANUP-RESULT-20261001.json`: circa 1,85 GiB liberati, nessun errore. Arrestati soltanto backend e proxy di test. Rimossi anteprime client superate, staging installato, copie dei dati di test, screenshot/log temporanei e tooling temporaneo sotto /tmp. Conservata build precedente `node1/client/build-preview-previous-20261001-102651`. I backup, i nodi storici, i repository e lo stato di rollback sono conservati. I vecchi strumenti di test sotto /tmp non sono più disponibili: prepararli nuovamente in un ambiente isolato se servono.

## Diagnosi CI

Il workflow `.github/workflows/tests.yml` controlla prima routing proxy e gestione degli errori Lighthouse, poi esegue `.github/workflows/scripts/run_tests.sh`: dipendenze vincolate, regressione navigazione dei questionari, build strumentata, 648 test Twisted backend e 73 test Cypress frontend, quindi report LCOV. Esaminare `gh run view RUN_ID --repo inno-bit-lab/WhistleblowingEasy --log-failed` e identificare lo step fallito. Screenshot/video dei test falliti e report di copertura sono conservati negli artifact per sette giorni.

Le correzioni preservano questi contratti:

- L’avviso `#submissions_disabled` deve comparire quando l’amministratore disabilita gli invii. Il pulsante generico nascosto della fork resta una personalizzazione distinta.
- Il selettore lingua usa pulsanti `data-cy="it"/"en"` e `aria-pressed`; il test aspetta PUT `/api/admin/node` **202** e ritorno del modulo prima di cambiare lingua. Il salvataggio ricarica la route attraverso `/blank`.
- Cercare i campi di identità dentro `src-whistleblower-identity-field` e il questionario aggiuntivo dentro il suo dialogo. Gli indici globali degli input cambiano quando si modifica la landing.
- Le operazioni report che ricaricano la pagina (scadenza, promemoria, stato, concessione/revoca accesso) richiedono attesa del PUT **202**, del GET dettaglio **200** e del nuovo DOM prima del passo successivo. Chiudere il dialogo non significa che il salvataggio e la navigazione siano completati. La race della concessione accesso è documentata localmente in `analysis/ci-36852041578-grant-race.md`.
- Il servizio dei passi è condiviso con i questionari aggiuntivi: usa `scrollToReportForm()` nella landing e il comportamento precedente negli altri componenti. Il test Node copre entrambe le modalità.

Il workflow Build verifica pacchetto, systemd, container, Cypress e Lighthouse. Gli audit sono effettuati sul nodo CI appena avviato. Il wrapper `.github/workflows/scripts/lighthouse_audit.py` ripete soltanto l’errore tecnico di registrazione traccia `NO_NAVSTART`, per massimo tre tentativi, conservando i report falliti. Punteggi bassi e altri errori restano fallimenti; le soglie sono invariate. Riferimento Lighthouse: https://github.com/GoogleChrome/lighthouse/issues/15382 .

La fork non ha secret Codacy configurato: l’invio esterno avviene solo quando è presente `CODACY_PROJECT_TOKEN`. I report LCOV backend/client sono comunque conservati negli artifact GitHub `coverage-reports`. Configurare il secret del progetto per abilitare l’integrazione; non inserire token nel repository.

Evidenze della diagnosi: run iniziale 36839266958 backend 648/648 e browser 61/73; run Tests 36849930737 verde con 648/648 backend, 73/73 browser e artifact copertura; Build 36848115930 e 36849930679 verdi. Ulteriori attese esplicite stabilizzano lo spec18. I test dipendono dalla preparazione di canali, questionari e utenti negli spec precedenti: usare un database isolato nuovo e riprodurre la sequenza necessaria. Non puntare Cypress alla produzione, forzare click per aggirare errori o disabilitare test.
