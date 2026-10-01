# URL dei canali WBE

Il campo `context.slug` è persistito nello schema WBE 69, facoltativo, univoco nel tenant, massimo 64 caratteri minuscoli alfanumerici separati da trattini. È modificabile dall’editor dei canali. La migrazione inizializza i canali presenti; nuovi canali possono ricevere uno slug dall’amministrazione. Cambiare o cancellare uno slug rende indisponibile il precedente URL breve; i link UUID rimangono validi.

Il client risolve lo slug via `GET /api/public/channels/{slug}` prima dell’avvio Angular. La risposta contiene soltanto ID e slug del canale nel tenant richiesto. Gli slug sono indirizzi pubblici condivisibili, non credenziali. I canali nascosti rimangono esclusi dall’elenco pubblico, ma uno slug noto consente l’accesso diretto come il loro UUID.

Traefik riscrive internamente il documento su `/`, senza redirect. Lo slug resta visibile. La regola è generale: non serve riconfigurare Traefik quando si aggiunge un canale. Gli asset e le API usano percorsi assoluti; la CSP mantiene `base-uri none`.

Percorsi supportati: `/{slug}/report`, `/{slug}/login`, `/{slug}/admin`, `/{slug}/admin/...`, `/{slug}/login/passwordreset` e sue sottopagine. Login/admin restano della piattaforma e non modificano i permessi per azienda. I vecchi URL `/#/submission?context=UUID` restano compatibili.

| Canale | Slug |
|---|---|
| Kronos Finance | `kronos-finance` |
| Manifatture Sartoriali Zeverino s.r.l. | `zeverino` |
| Longo Euroservice s.r.l. | `longo-euroservice` |
| Lama Distribuzione s.r.l. | `lama-distribuzione` |
| Donato Trasporti s.r.l. | `donato-trasporti` |
| Canale di Test | `test` |
| LAGOLOSADIPUGLIA | `lagolosadipuglia` |
| Impresa Resta S.r.l. | `impresa-resta` |
| Innobitlab | `innobitlab` |

Attivazione: `sudo /opt/apps/wbe/analysis/activate-channel-slugs.sh`. Il servizio viene fermato, la versione corrente e tutti i dati sono copiati nel backup, il backend esegue la migrazione, poi viene pubblicata la regola Traefik. In caso di errore lo script ripristina codice, database e routing precedenti.
