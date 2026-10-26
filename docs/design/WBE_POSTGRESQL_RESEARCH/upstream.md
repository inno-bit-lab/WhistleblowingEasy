# Stato upstream GlobaLeaks e implicazioni WBE

Data verifica: 26 ottobre 2026 (Europe/Rome). Fonti ufficiali interrogate con connettore GitHub e ricerca web; sola lettura codice e documentazione, nessun database/segreto/deploy. Nessun AGENTS.md presente nei percorsi antenati controllati.

## Risultato
GlobaLeaks è mantenuto attivamente, ma PostgreSQL esterno e backend active-active non sono funzionalità supportate/documentate nell'implementazione stable osservata. Il progetto WBE deve trattarle come evoluzione architetturale del fork, assumendo manutenzione, migrazioni, test e rivalutazione del modello di sicurezza. SQLAlchemy riduce parte del lavoro di portabilità ORM, non rende il prodotto compatibile con PostgreSQL cambiando solo una URL.

## Evidenze verificabili

1. API releases/latest indica v5.0.99, pubblicata 2026-07-26T10:30:00Z, non prerelease; commit tag 134d4426cc16e341794b9d2dab84a6492cb4d42b. La release include correzioni su isolamento/identità tenant, redazioni, token e cancellazione file. Fonte: https://github.com/globaleaks/globaleaks-whistleblowing-software/releases/tag/v5.0.99 e https://api.github.com/repos/globaleaks/globaleaks-whistleblowing-software/releases/latest
2. API commits/stable restituisce ac2c55372e3ef3bb74a1ad9befce021f45849b9f, 2026-10-23T15:31:40Z, “Adapt the client to ngx-translate 18 and Cypress 16”. Dunque release pubblicata e testa stable differiscono: non chiamare automaticamente stable una release certificata. Fonte: https://github.com/globaleaks/globaleaks-whistleblowing-software/commit/ac2c55372e3ef3bb74a1ad9befce021f45849b9f
3. Documentazione attuale: backend Python REST e client TypeScript; DB SQLite locale hardened via SQLAlchemy. Misure comprendono secure_delete, trusted_schema, defensive mode, restrizione SQL authorizer, disabilitazione trigger/view. Fonte: https://github.com/globaleaks/globaleaks-whistleblowing-software/blob/stable/documentation/technical/security/application-security.rst
4. Codice stable orm.py conferma URI sqlite costruita da file, connect_args timeout SQLite, PRAGMA incondizionati, sqlite3.set_authorizer, retry di “database is locked”. Fonte: https://github.com/globaleaks/globaleaks-whistleblowing-software/blob/ac2c55372e3ef3bb74a1ad9befce021f45849b9f/backend/globaleaks/orm.py
5. Feature ufficiali dichiarano SQLite integrato, software self-contained, multi-site, Angular/Python Twisted. Multi-site non equivale a cluster active-active. Fonte: https://github.com/globaleaks/globaleaks-whistleblowing-software/blob/stable/documentation/technical/features.rst
6. Issue #1324 “Extend support to multiple database technologies” risulta APERTA. Commento maintainer 2018 parla di modelli SQLAlchemy creati anche su PostgreSQL; commento successivo 2021 chiarisce supporto solo teorico e necessità di grande lavoro/test; DB esterno oltre il threat model self-contained/sandboxed. Questa distinzione evita di citare solo il commento ottimistico del 2018. Fonte più precisa: https://github.com/globaleaks/globaleaks-whistleblowing-software/issues/1324#issuecomment-760931387 . Issue #1679 è chiusa come duplicato di #1324, NON prova di implementazione: https://github.com/globaleaks/globaleaks-whistleblowing-software/issues/1679#issuecomment-985035761
7. SECURITY.md fornisce disclosure privata, obiettivo risposta 8h e fix critici 2 giorni ove possibile; non è SLA commerciale né garanzia su fork. Fonte: https://github.com/globaleaks/globaleaks-whistleblowing-software/blob/stable/SECURITY.md
8. SQLite ufficiale sconsiglia rete filesystem per scenari concorrenti multi-macchina e indica architettura client/server per dati remoti. Quindi non adottare NFS come scorciatoia per condividere DB SQLite: https://www.sqlite.org/useovernet.html e https://www.sqlite.org/faq.html

## Stato checkout locale confrontato
Repository /opt/apps/wbe/repos/WhistleblowingEasy-upgrade:
- HEAD 367b8635236bde61a289880d7002574b5ddff6ca, data commit 2026-10-01.
- backend/globaleaks/__init__.py:9 dichiara 5.0.99.
- git rev-list --left-right --count v5.0.99...HEAD = 0 72: il tag è antenato e ci sono 72 commit successivi nella storia locale. Non equivalgono necessariamente tutti a patch specifiche WBE; serve classificare il delta.
- git diff --stat v5.0.99...HEAD: 255 file, 15.860 inserzioni, 6.229 rimozioni.
- CHANGELOG locale parte da 5.0.99, non è inventario completo delle customizzazioni.
- README rimane prevalentemente upstream; versione nominale uguale non prova equivalenza comportamento, aggiornamento di tutti i fix, né quale build sia in esecuzione. Il parent deve integrare inventario runtime/deploy.

## Strategia manutenzione proposta (inferenza progettuale)
- Baseline esplicita di commit upstream, commit WBE e schema SQLite di partenza; manifest build per componente. Delta review prima del port, classificato in personalizzazioni UI, sicurezza/autenticazione, dati, packaging.
- Adapter DB e migrazioni versionate che isolino codice PostgreSQL. Evitare riscrittura generale del backend insieme alla migrazione.
- CI obbligatoria con matrice SQLite (compatibilità/ingresso importatore) e PostgreSQL (target) più regressioni upstream, test di concorrenza e tenant isolation.
- Riconciliazione periodica changelog/security fixes upstream, ramo di integrazione, test migrazioni e ripristino prima del rilascio. Aggiornamenti automatici del pacchetto upstream non devono sovrascrivere il fork.
- Se possibile proporre upstream i cambiamenti generici, senza assumere accettazione o scadenze.
- Non attendere una futura release PostgreSQL: non è emersa una roadmap ufficiale con impegno di consegna.
- Piano in fasi: port DB single-backend; poi stato condiviso, job singleton/idempotenti e storage; infine multi-replica. Stabilire misure di successo e possibilità di rollback per fase.
- Nuovo threat model richiesto come deliverable futuro: flussi DB su rete, permessi TLS/DB, sessioni/token/cache distribuiti, backup/WAL/repliche, log edge e anonimato, cancellazione/retention. PostgreSQL MVCC e WAL non offrono equivalenza automatica al secure_delete SQLite: occorre progettare retention e cifratura sulle copie.

## Licenza (riscontro documentale, non parere legale)
README e LICENSE dichiarano AGPLv3 con termini aggiuntivi: preservazione attribuzione GlobaLeaks e identificazione delle versioni modificate. Il disegno deve includere distribuzione del sorgente corrispondente e notices coerenti con il fork, da verificare con responsabile licenze. Fonte: https://github.com/globaleaks/globaleaks-whistleblowing-software/blob/stable/LICENSE ; locale LICENSE (termini aggiuntivi da circa riga 704). Non dedurre obbligo contrattuale di SLA da aspirazioni in preambolo.

## Limiti
Ricerca mirata, non audit di sicurezza né certificazione che nessuna PR futura implementerà PostgreSQL. Il sostegno alla conclusione è positivo (codice stable incompatibile e docs SQLite), non soltanto assenza di risultati. Nessun load test eseguito; nessuna stima affidabile di capacità deducibile dalle sole fonti upstream. Le pagine stable sono mutabili; per decisioni implementative congelare commit verificato sopra.
