# Tor: proposta di cutover e blocchi verificati

Data: 26 ottobre 2026. Analisi statica; nessun servizio, configurazione, chiave, database o permesso modificato. Nessuna lettura dei segreti o accesso sudo. Percorsi sotto `/opt/apps/wbe-refact` salvo indicazione diversa. La proposta NON è una configurazione implementata o collaudata.

## Esito

**Il deployment separato FE/BE attuale non è pronto per il cutover onion.** Il backend pubblica ancora ogni servizio onion verso `localhost:8083`, saltando il frontend. In modalità frontend separato quella destinazione restituisce metadati interni invece della pagina renderizzata. Cambiare soltanto destinazione verso il frontend risolve il rendering ma, con FE→BE sulla porta 8080, perde il riconoscimento Tor del backend. Servono percorso dedicato e controllo della provenienza, preservando identità onion e policy di rete.

Il collaudo reale esistente deve restare isolato e non pubblicare le identità onion di produzione. Non usare la rimozione di `WBE_REHEARSAL=1` come scorciatoia per abilitarlo: ciò avvia anche notifiche, pulizia e controlli esterni. La prima release produttiva richiesta è HA completa: una soluzione transitoria con solo processo Tor/backend non soddisfa questo requisito.

## Evidenze di codice

| Punto | Evidenza | Implicazione |
|---|---|---|
| Lifecycle | `backend/globaleaks/backend.py:56–69` | Fuori rehearsal ogni backend avvia Tor insieme ai job; dentro rehearsal solo Delivery. Nessun ruolo gateway/leader Tor implementato qui. |
| Daemon | `backend/globaleaks/services/tor.py:23–28,117–128` | `txtorcon.launch` avvia daemon locale; controllo e SOCKS sono socket Unix. Non è già disponibile configurazione per un daemon esterno. |
| Pubblicazione | `backend/globaleaks/services/tor.py:45–85` | Target fisso `80 localhost:8083`; servizi ephemeral creati con `private_key=key` letto dalla cache tenant. Non rigenerare chiavi durante trasferimento. |
| Origine identità | `backend/globaleaks/models/config.py:160`; `utils/onion.py:39`; `db/__init__.py:262,292–307` | Config applicativa contiene onionservice e tor_onion_key (formato ED25519-V3). Map hostname include onion tenant e sottodomini ereditati dal root. Non si può assumere che basti copiare una HiddenServiceDir. |
| Percorsi runtime | `backend/globaleaks/settings.py:39–47,89–99` | RuntimeDirectory definisce pid/ramdisk, ma socket Tor/SOCKS derivano da working_path/tmp. Distinguere questi percorsi dal testo operativo generale. |
| Binding | `backend/globaleaks/state.py:193–216`; `settings.py:23–24` | Porta 8083 bind su 127.0.0.1 del namespace backend; FE in container diverso non la raggiunge tramite backend:8083. Rete Tor-only può rendere loopback anche i listener remoti. |
| Riconoscimento Tor | `backend/globaleaks/rest/api.py:402–427,752–755` | Tor riconosciuto da IP exit node oppure porta locale 8083. Host .onion evita redirect HTTPS (:325–328), ma da solo non attiva client_using_tor. |
| Routing tenant | `backend/globaleaks/rest/api.py:433–438`; `db/__init__.py:307` | Host onion originale deve restare invariato fino al BE. Host localhost forzerebbe tenant root. |
| FE | `deploy/dev/frontend-server/server.mjs:12–14,51–74,89–104` | FE conserva Host e DPoP, elimina Forwarded/X-Forwarded/X-Real-IP e renderizza metadati/nonce. BACKEND_URL unico per istanza, nessun listener distinto Tor implementato. |
| Deployment | `deploy/rehearsal/compose.yml`; `deploy/rehearsal/README.md` | BE e PG solo reti internal, Tor disattivo; FE pubblicato solo loopback. Stack non è config produzione HA. |
| Runtime immagine | `deploy/dev/Dockerfile.backend-runtime:2`; `deploy/dev/backend-entrypoint.sh` | Binario Tor installato, processo backend non privilegiato con bind 0.0.0.0 per porte remote; ciò non cambia bind loopback 8083. |

`/opt/apps/wbe/OPERATIONS.md` punta al documento operativo del checkout upgrade. Quel documento identifica servizio legacy `wbe-app@node1`, monitor, Tor host e backup completo appdata; non prova le configurazioni correnti del nuovo stack. Non interrogati socket/control runtime né le chiavi reali.

## Topologia proposta

```text
Tor Browser
   -> servizio onion v3 (identità esistente)
   -> gateway Tor attivo, standby pronto con fencing
   -> ingresso onion PRIVATO
   -> FE-onion (rendering shell/assets + proxy API)
   -> BE listener onion autenticato/isolato
   -> PostgreSQL / storage / stato HA

HTTPS pubblico -> ingress HTTPS -> FE-web -> BE listener web
BE/worker egress anonimo -> SOCKS Unix locale -> Tor egress
```

Separare ownership della pubblicazione onion dall'egress Tor. Il gateway attivo possiede pubblicazione/control; le repliche API non pubblicano autonomamente la medesima identità. Standby deve essere pronto su altro dominio guasto e assumere ownership solo dopo fencing dell'attivo. Lease da sola non spegne un daemon isolato: serve fencing operativo. Questa strategia active/passive conserva identità; disponibilità e tempi effettivi di ripubblicazione descriptor vanno provati sullo stack Tor scelto, senza promettere failover istantaneo. Soluzioni active/active richiedono un progetto specifico ulteriore; non avviare semplicemente due publisher con la stessa chiave.

## Modifiche minime richieste prima del deployment

1. **Configurazione target e ruolo Tor espliciti.** Separare `launch daemon`, `publish onion services`, `egress SOCKS`; aggiungere configurazione del target frontend onion e controllo esterno con timeout/readiness. I nomi di variabili definitivi sono da implementare: non esistono già nel codice ispezionato. Il controller usa i valori configurati per tutti i tenant; bootstrap e aggiornamenti config non devono duplicare publisher.
2. **FE-onion dedicato.** Stesso codice/bundle del FE-web, diversa istanza/listener di rete con upstream Tor. Non scegliere canale privilegiato dalla sola stringa Host o da header del browser. Backend deve distinguere il canale tramite endpoint riservato con firewall/identità del peer o trasporto autenticato e trust esplicito. Conservare Host onion originale, method/path/query/body, DPoP, Date, CSP e nonce.
3. **Rendere raggiungibile il listener Tor senza renderlo pubblico.** Variante locale per PoC: FE-onion nello stesso namespace di rete del BE, upstream `http://127.0.0.1:8083`, target Tor verso una porta distinta del FE-onion. Mantiene semantica attuale ma accoppia FE/BE e NON è il target HA indipendente. Target HA: listener backend onion su interfaccia privata dedicata e accessibile soltanto da FE-onion autenticati; mantenere 8083 o introdurre classificazione esplicita del listener. Non bindare semplicemente 8083 su tutte le reti e non esporlo su host.
4. **Trust proxy web separato.** Attualmente i limiti IP vedono il FE, non il visitatore; il codice scarta header forwarded. La propagazione IP web richiede lista proxy fidati/configurazione autenticata e stripping al primo hop. Il canale onion non ha un IP reale visitatore da recuperare: non inventarlo né fidarsi di X-Forwarded-For. Verificare policy Tor/rate limiting differenziate e protezione da classificazione Tor spoofata.
5. **Controllo e SOCKS.** Socket Unix e directory private, UID/GID dedicati e coerenti fra controller e daemon; directory 0700 come default, accesso minimo tramite gruppo/ACL solo se richiesto. Non montare control socket in FE o container non fidati, non aprire ControlPort/SocksPort pubblici, non usare chmod 777. Pin e verificare compatibilità Tor/txtorcon e autenticazione control scelta. Egress attuale usa `UNIXClientEndpoint` (`utils/agent.py:8–20`): gateway remoto TCP non è sostituto diretto; mantenere daemon egress locale per ogni host/namespace o implementare adapter protetto separatamente.
6. **Lifecycle robusto.** Validare restart daemon/control e ripubblicazione: `load_all_onion_services` salta tenant con attributo ephs già presente; al reconnect gli attributi vanno riconciliati con servizi effettivamente registrati. Gestire cleanup, hostname corrispondente alla chiave, errori callback e shutdown senza assunzioni su permanenza dei servizi ephemeral.

## Conservazione identità senza esposizione segreti

Preparare backup cifrato e accesso limitato del recovery set applicativo, inclusi record config onion e configurazioni necessarie. L'operatore autorizzato verifica in procedura protetta che le coppie hostname/chiave, gli identificativi tenant e le associazioni root/subdomain siano identiche dopo migrazione. Il report di verifica deve contenere esito/count e mai chiavi o dump di righe config. Non stampare private_key nei log, shell argv, file compose, ticket o repository. Usare import dei dati esistenti, non inizializzazione nuova config che genera un'identità diversa. Nessuna conversione artigianale verso file Tor hidden-service: il controller attuale accetta direttamente il formato ED25519-V3.

Il vecchio publisher deve risultare spento e fenced prima di pubblicare le stesse identità sul target. Non usare in parallelo le identità reali per testare raggiungibilità del nuovo stack. PoC funzionale con identità e tenant sintetici separati.

## Sequenza concreta proposta di cutover

**Preparazione fuori finestra:** completare modifiche e test sintetici, predisporre gateway standby/controllo/fencing, rete privata e FE-onion, verificare dipendenze senza pubblicare identità reali. Provare rollback e tempo ripubblicazione con identità sintetica. Collaudare browser Tor e request dirette; health HTTP da solo non verifica Tor. Ottenere operatore con privilegi per legacy systemd/firewall: sudo non disponibile in questa sessione.

**Dentro finestra <=60 minuti:** bloccare nuove scritture e accessi operativi, disabilitare monitor legacy/avvio automatico, fermare publisher vecchio e verificarne fencing; completare migrazione/delta con preservazione identità; avviare target HA privato; validare associazioni tenant e readiness; consentire un solo controller attivo e pubblicare identità preesistenti verso FE-onion. Testare con Tor Browser lo stesso indirizzo onion, pagina/lingua/slug, login autorizzato, CSP, assenza metadati interni e API senza redirect web indesiderati. Niente segnalazioni reali di prova. Riaprire scritture soltanto dopo accettazione.

**Go/no-go:** soglia temporale concordata con runbook generale (es. minuto 35–40 solo se rollback misurato <=15 min), includendo bootstrap/ripubblicazione Tor. Se fallisce prima riapertura scritture: spegnere/fence target publisher, ripristinare vecchio publisher e servizio/monitor secondo stato salvato, verificare onion. Dopo riapertura scritture il rollback dati è un altro problema: nessun ripristino SQLite che perda scritture nuove. Il tempo Tor va incluso nel fermo misurato, non escluso perché il backend HTTP è sano.

## Criteri di accettazione e blocchi residui

- Identità onion invariata per ogni tenant, mappa hostname corretta, nessun publisher duplicato.
- Pagina onion passa FE; index e asset ricevono header corretti, niente JSON interno `wbe_frontend` esposto; `X-Check-Tor: True` sul percorso onion e nessuno spoof su web.
- API/DPoP, login e allegati sintetici funzionano; endpoint web non può raggiungere listener onion; Tor-only non diventa accessibile pubblicamente per effetto dei binding container.
- Tor daemon/control kill e perdita gateway attivo: failover fenced senza duplicazione pubblicazione, ripristino onion misurato; perdita quorum privilegia sicurezza ownership.
- Rete outbound realmente disponibile ai soli componenti Tor autorizzati; rehearsal resta internal e disattivo. Nessun requisito di pubblicazione viene soddisfatto dal compose attuale.
- Backup/restore preserva identità; permission test e restart socket controllati; nessuna esposizione control o private key.

**Blocchi attuali:** target hardcoded BE; listener 8083 loopback; assenza controller HA/fencing e ruoli separati; trust proxy non implementato; mancata verifica riconciliazione ephs su restart; nessuna prova bootstrap/failover egress/ingress; nessun operatore sudo disponibile per il cutover legacy. Il documento prepara una soluzione reviewable, non autorizza né certifica deployment. Per HA richiesta dalla prima release questi blocchi sono gate, non attività rinviabili dopo pubblicazione.

### Evidenza operativa comunicata dal coordinatore

Il coordinatore segnala certificato HTTPS del backend legacy scaduto a dicembre 2025 e trasporto Traefik attuale con verifica TLS disabilitata; questa informazione non è stata verificata indipendentemente in questa analisi. È un ulteriore gate del percorso pubblico: predisporre certificato valido e verifica upstream appropriata prima del cutover; non perpetuare un bypass TLS come configurazione del target. Sudo richiede password, quindi questa sessione non può eseguire la sequenza operativa legacy. **Nessun cutover eseguito; architettura Tor HA ancora da implementare e collaudare.**
