#!/usr/bin/make -f
prefix=/usr

all:

install:
	cd data && find . -type f -exec install -D "{}" "$(DESTDIR)/{}" \;

clean:

distclean: clean

uninstall:
	-rm -rf $(DESTDIR)/usr/share/kat-mula

.PHONY: all install clean distclean uninstall
