import os

def compile_translate():
	for lang in os.listdir('po'):
		if lang.endswith('.po'):
			src = os.path.join('po', lang)
			lang = lang[:-3]
			destdir = os.path.join('src/locale', lang, 'LC_MESSAGES')
			if not os.path.exists(destdir):
				os.makedirs(destdir)
			dest = os.path.join(destdir, 'YouTube.mo')
			print("Language compile %s -> %s" % (src, dest))
			if os.system("msgfmt '%s' -o '%s'" % (src, dest)) != 0:
				raise RuntimeError("Failed to compile", src)


compile_translate()
