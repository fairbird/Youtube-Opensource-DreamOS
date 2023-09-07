import gettext

from os import environ

from Components.Language import language
from Tools.Directories import resolveFilename, SCOPE_PLUGINS


def locale_init():
	try:
		environ["LANGUAGE"]
	except KeyError:  # On old images LANGUAGE environment is not set
		environ["LANGUAGE"] = language.getLanguage()[:2]
	gettext.bindtextdomain(
		"YouTube",
		resolveFilename(SCOPE_PLUGINS, "Extensions/YouTube/locale")
	)


def _(txt):
	t = gettext.dgettext("YouTube", txt)
	if t == txt:
		t = gettext.gettext(txt)
	return t


def ngettext(singular, plural, n):
	t = gettext.dngettext("YouTube", singular, plural, n)
	if t in (singular, plural):
		t = gettext.ngettext(singular, plural, n)
	return t


locale_init()
language.addCallback(locale_init)


from enigma import getDesktop
screenwidth = getDesktop(0).size().width()
if not screenwidth:
	screenwidth = 720
