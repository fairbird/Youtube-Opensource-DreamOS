from sys import version_info
from threading import Thread


# Disable certificate verification on python 2.7.9
if version_info >= (2, 7, 9):
	import ssl
	ssl._create_default_https_context = ssl._create_unverified_context


if version_info[0] == 2:
	# Python 2
	compat_basestring, compat_chr, compat_str = (
		basestring, unichr, unicode
	)

	from itertools import izip_longest as compat_zip_longest
	from urllib import urlencode as compat_urlencode
	from urllib import quote as compat_quote
	from urllib import urlretrieve as compat_urlretrieve
	from urllib2 import urlopen
	from urllib2 import Request as compat_Request
	from urllib2 import HTTPError as compat_HTTPError
	from urllib2 import URLError as compat_URLError
else:
	# Python 3
	compat_basestring, compat_chr, compat_str = (
		str, chr, str
	)

	from itertools import zip_longest as compat_zip_longest
	from urllib.parse import urlencode as compat_urlencode
	from urllib.parse import quote as compat_quote
	from urllib.request import urlretrieve as compat_urlretrieve
	from urllib.request import urlopen
	from urllib.request import Request as compat_Request
	from urllib.error import HTTPError as compat_HTTPError
	from urllib.error import URLError as compat_URLError


if version_info >= (3, 4):
	from collections import ChainMap as compat_map
else:
	from collections import MutableMapping

	class compat_map(MutableMapping):
		maps = [{}]

		def __init__(self, *maps):
			self.maps = list(maps) or [{}]

		def __getitem__(self, k):
			for m in self.maps:
				if k in m:
					return m[k]
			raise KeyError(k)

		def __setitem__(self, k, v):
			self.maps[0].__setitem__(k, v)
			return

		def __contains__(self, k):
			return any((k in m) for m in self.maps)

		def __delitem(self, k):
			if k in self.maps[0]:
				del self.maps[0][k]
				return
			raise KeyError(k)

		def __delitem__(self, k):
			self.__delitem(k)

		def __iter__(self):
			return itertools.chain(*reversed(self.maps))

		def __len__(self):
			return len(iter(self))


SUBURI = '&suburi='


def compat_urlopen(url, timeout=5):
	"""
	Urlopen in thread to enforce a timeout on the function call.
	Timeout in urlopen only affects how long Python waits before
	an exception is raised if the server has not issued a response.
	It does not enforce a time limit on the entire function call.
	"""
	compat_urlopen.response = None
	compat_urlopen.error = None

	def open_url(url, timeout):
		try:
			compat_urlopen.response = urlopen(url, timeout=timeout)
		except Exception as e:
			compat_urlopen.error = e

	t = Thread(target=open_url, args=(url, timeout))
	t.setDaemon(True)
	t.start()
	t.join(timeout + 1)
	if compat_urlopen.error:
		raise compat_urlopen.error
	return compat_urlopen.response
