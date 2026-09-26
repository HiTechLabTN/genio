# Upgrade guide — to 4.1.0

From git checkout: `genio update --prefix <P> --to v4.1.0`
(auto backup + verify + rollback on failure).
From archive: `genio update --prefix <P> --archive genio-4.1.0.tar.gz
--checksum genio-4.1.0.tar.gz.sha256`.
Downgrades need `--allow-downgrade`. `data/` untouched in all paths.
After upgrade: `genio doctor --prefix <P> --deep` must show 0 FAIL.
