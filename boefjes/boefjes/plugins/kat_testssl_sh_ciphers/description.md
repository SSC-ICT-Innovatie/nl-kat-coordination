# SSL Test Ciphers

testssl.sh checks TLS/SSL services for supported cipher suites and server cipher preference. This Boefje scans the exact IP represented by the input while retaining the hostname as the TLS/SNI identity when a `HostnameService` is available. A hostname with multiple IP addresses is therefore represented by separate `TLSCipher` observations. IPService-only inputs remain supported when no hostname is known.
