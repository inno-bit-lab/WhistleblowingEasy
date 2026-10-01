# WhistleblowingEasy on GlobaLeaks 5.0.99

This branch merges the fork history with the upstream v5.0.99 release and ports WBE customizations onto the new Angular client. Upstream fixes and dependency lockfiles remain the baseline.

Preserved behavior: WBE logo/favicon, translated documentation and support links, activation-email wording, context-specific header/language visibility, receipt search on submission, hidden header receipt form, hidden default Tor notice, hidden homepage submission button, and checkbox presentation of single-choice fields. Checkbox answers retain the option identifier expected by the backend; true multiple selection remains the separate checkbox field type.

Operational scripts use Python 3, hash-verified distribution dependencies and the Angular/Grunt build. Provisioning exports tracked sources, refuses existing nodes and leaves a new node in maintenance. The main HTTP port is read from HTTP_PORT; HTTPS remains 8443. Production uses 8082 to avoid the existing 8080 listener. Temporary token material stays in RAM under /run/wbe-NODE through the new systemd RuntimeDirectory, instead of the old persistent appdata/shm customization.

The WBE Tor exit-list endpoint is retained with validated IPv4/IPv6 parsing. Other obsolete logging/whitespace changes are superseded by upstream. The upstream Docker installer and distribution packaging are retained; the old fork Dockerfile referenced inconsistent installer filenames.

## Deployment

Install the updated scripts and wbe-app@.service together. Run systemctl daemon-reload after updating the unit. Node code and dependencies must belong to iblapps. Set MAINTENANCE_MODE=N only when ready to start. Stop the monitor timer and application before copying live application data. Do not run the old provisioning script against this branch.

A stopped backup must include the database, attachments and files. The onion-service key is held in the database. GlobaLeaks 5 starts Tor using temporary local sockets; its handling of the old Tor state directory has changed upstream.

## Validation and rollback

The production Angular build passed. The selected upstream migration, crypto and filesystem suites plus the WBE Tor parser tests passed (56 tests). A separate HTTP smoke test on a backup copy served the homepage and public API with jobs, email and Tor disabled; this is not an end-to-end authenticated test.

The local deployment script snapshots live appdata after stopping the service, preserves the old node and operational files, switches the node and verifies the public HTTP response. Rollback restores the stopped pre-upgrade data; reports or configuration changes created during the new-version trial remain only in the preserved upgraded directory. Verify receipt and recipient access, attachment decryption, email delivery and onion access before treating the rollout as accepted.
