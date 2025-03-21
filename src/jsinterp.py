# coding: utf-8
from __future__ import unicode_literals

import operator
import re

from calendar import timegm
from datetime import timedelta
from datetime import datetime
from email import utils
from itertools import chain
from json import dumps
from json import loads

from .compat import compat_basestring
from .compat import compat_chain_map
from .compat import compat_chr
from .compat import compat_int
from .compat import compat_integer_types
from .compat import compat_map
from .compat import compat_numeric_types
from .compat import compat_str
from .compat import compat_zip_longest


def js_to_json(code):
	COMMENT_RE = r'/\*(?:(?!\*/).)*?\*/|//[^\n]*\n'
	SKIP_RE = r'\s*(?:{comment})?\s*'.format(comment=COMMENT_RE)

	def fix_kv(m):
		v = m.group(0)
		if v in ('true', 'false', 'null'):
			return v
		elif v in ('undefined', 'void 0'):
			return 'null'
		elif v.startswith('/*') or v.startswith('//') or v.startswith('!') or v == ',':
			return ''

		if v[0] in ("'", '"'):
			v = re.sub(r'(?s)\\.|"', lambda m: {
				'"': '\\"',
				"\\'": "'",
				'\\\n': '',
				'\\x': '\\u00',
			}.get(m.group(0), m.group(0)), v[1:-1])

			return '"%s"' % v

		raise ValueError('Unknown value:', v)

	return re.sub(r'''(?sx)
		"(?:[^"\\]*(?:\\\\|\\['"nurtbfx/\n]))*[^"\\]*"|
		'(?:[^'\\]*(?:\\\\|\\['"nurtbfx/\n]))*[^'\\]*'|
		{comment}|,(?={skip}[\]}}])|
		(?:(?<![0-9])[eE]|[a-df-zA-DF-Z_])[.a-zA-Z_0-9]*|
		\b(?:0[xX][0-9a-fA-F]+|0+[0-7]+)(?:{skip}:)?|
		[0-9]+(?={skip}:)|
		!+
		'''.format(comment=COMMENT_RE, skip=SKIP_RE), fix_kv, code)


TIMEZONE_NAMES = {
	'UT': 0, 'UTC': 0, 'GMT': 0, 'Z': 0,
	'AST': -4, 'ADT': -3,  # Atlantic (used in Canada)
	'EST': -5, 'EDT': -4,  # Eastern
	'CST': -6, 'CDT': -5,  # Central
	'MST': -7, 'MDT': -6,  # Mountain
	'PST': -8, 'PDT': -7   # Pacific
}


DATE_FORMATS_MONTH_FIRST = (
	'%d %B %Y',
	'%d %b %Y',
	'%B %d %Y',
	'%B %dst %Y',
	'%B %dnd %Y',
	'%B %drd %Y',
	'%B %dth %Y',
	'%b %d %Y',
	'%b %dst %Y',
	'%b %dnd %Y',
	'%b %drd %Y',
	'%b %dth %Y',
	'%b %dst %Y %I:%M',
	'%b %dnd %Y %I:%M',
	'%b %drd %Y %I:%M',
	'%b %dth %Y %I:%M',
	'%Y %m %d',
	'%Y-%m-%d',
	'%Y.%m.%d.',
	'%Y/%m/%d',
	'%Y/%m/%d %H:%M',
	'%Y/%m/%d %H:%M:%S',
	'%Y%m%d%H%M',
	'%Y%m%d%H%M%S',
	'%Y%m%d',
	'%Y-%m-%d %H:%M',
	'%Y-%m-%d %H:%M:%S',
	'%Y-%m-%d %H:%M:%S.%f',
	'%Y-%m-%d %H:%M:%S:%f',
	'%d.%m.%Y %H:%M',
	'%d.%m.%Y %H.%M',
	'%Y-%m-%dT%H:%M:%SZ',
	'%Y-%m-%dT%H:%M:%S.%fZ',
	'%Y-%m-%dT%H:%M:%S.%f0Z',
	'%Y-%m-%dT%H:%M:%S',
	'%Y-%m-%dT%H:%M:%S.%f',
	'%Y-%m-%dT%H:%M',
	'%b %d %Y at %H:%M',
	'%b %d %Y at %H:%M:%S',
	'%B %d %Y at %H:%M',
	'%B %d %Y at %H:%M:%S',
	'%H:%M %d-%b-%Y',
	'%m-%d-%Y',
	'%m.%d.%Y',
	'%m/%d/%Y',
	'%m/%d/%y',
	'%m/%d/%Y %H:%M:%S',
)


def extract_timezone(date_str):
	m = re.search(
		r'''(?x)
			^.{8,}?  # >=8 char non-TZ prefix, if present
			(?P<tz>Z|  # just the UTC Z, or
				(?:(?<=.\b\d{4}|\b\d{2}:\d\d)|  # preceded by 4 digits or hh:mm or
					(?<!.\b[a-zA-Z]{3}|[a-zA-Z]{4}|..\b\d\d))  # not preceded by 3 alpha word or >= 4 alpha or 2 digits
					[ ]?  # optional space
				(?P<sign>\+|-)  # +/-
				(?P<hours>[0-9]{2}):?(?P<minutes>[0-9]{2})  # hh[:]mm
			$)
		''', date_str)
	if not m:
		m = re.search(r'\d{1,2}:\d{1,2}(?:\.\d+)?(?P<tz>\s*[A-Z]+)$', date_str)
		timezone = TIMEZONE_NAMES.get(m and m.group('tz').strip())
		if timezone is not None:
			date_str = date_str[:-len(m.group('tz'))]
		timezone = timedelta(hours=timezone or 0)
	else:
		date_str = date_str[:-len(m.group('tz'))]
		if not m.group('sign'):
			timezone = timedelta()
		else:
			sign = 1 if m.group('sign') == '+' else -1
			timezone = timedelta(
				hours=sign * int(m.group('hours')),
				minutes=sign * int(m.group('minutes')))
	return timezone, date_str


def unified_timestamp(date_str):
	date_str = re.sub(r'\s+', ' ', re.sub(
		r'(?i)[,|]|(mon|tues?|wed(nes)?|thu(rs)?|fri|sat(ur)?)(day)?', '', date_str))

	pm_delta = 12 if re.search(r'(?i)PM', date_str) else 0
	timezone, date_str = extract_timezone(date_str)

	# Remove AM/PM + timezone
	date_str = re.sub(r'(?i)\s*(?:AM|PM)(?:\s+[A-Z]+)?', '', date_str)

	for expression in DATE_FORMATS_MONTH_FIRST:
		try:
			dt = datetime.strptime(date_str, expression) - timezone + timedelta(hours=pm_delta)
			return timegm(dt.timetuple())
		except ValueError:
			pass

	timetuple = utils.parsedate_tz(date_str)
	if timetuple:
		return timegm(timetuple) + pm_delta * 3600 - timedelta.total_seconds(timezone)


def remove_quotes(s):
	if s is None or len(s) < 2:
		return s
	for quote in ('"', "'", ):
		if s[0] == quote and s[-1] == quote:
			return s[1:-1]
	return s


def float_or_none(v, default=None):
	if v is None:
		return default
	try:
		return float(v)
	except (ValueError, TypeError):
		return default


# NB In principle NaN cannot be checked by membership.
# Here all NaN values are actually this one, so _NaN is _NaN,
# although _NaN != _NaN. Ditto Infinity.

_NaN = float('nan')
_Infinity = float('inf')


class JSUndefined():
	pass


def _js_bit_op(op, is_shift=False):

	def zeroise(x, is_shift_arg=False):
		if isinstance(x, compat_integer_types):
			return (x % 32) if is_shift_arg else (x & 0xffffffff)
		try:
			x = float(x)
			if is_shift_arg:
				x = int(x % 32)
			elif x < 0:
				x = -compat_int(-x % 0xffffffff)
			else:
				x = compat_int(x % 0xffffffff)
		except (ValueError, TypeError):
			# also here for int(NaN), including float('inf') % 32
			x = 0
		return x

	def wrapped(a, b):
		return op(zeroise(a), zeroise(b, is_shift)) & 0xffffffff

	return wrapped


def _js_arith_op(op, div=False):

	def wrapped(a, b):
		if JSUndefined in (a, b):
			return _NaN
		# null, "" --> 0
		a, b = (float_or_none(
			(x.strip() if isinstance(x, compat_basestring) else x) or 0,
			default=_NaN) for x in (a, b))
		if _NaN in (a, b):
			return _NaN
		try:
			return op(a, b)
		except ZeroDivisionError:
			return _NaN if not (div and (a or b)) else _Infinity

	return wrapped


_js_arith_add = _js_arith_op(operator.add)


def _js_add(a, b):
	if not (isinstance(a, compat_basestring) or isinstance(b, compat_basestring)):
		return _js_arith_add(a, b)
	if not isinstance(a, compat_basestring):
		a = _js_to_string(a)
	elif not isinstance(b, compat_basestring):
		b = _js_to_string(b)
	return operator.concat(a, b)


_js_mod = _js_arith_op(operator.mod)
__js_exp = _js_arith_op(operator.pow)


def _js_exp(a, b):
	if not b:
		return 1  # even 0 ** 0 !!
	return __js_exp(a, b)


def _js_to_primitive(v):
	if isinstance(v, list):
		return ','.join(compat_map(_js_to_string, v))
	if isinstance(v, dict):
		return '[object Object]'
	if not isinstance(v, (compat_numeric_types, compat_basestring)):
		return compat_str(v)
	return v


def _js_to_string(v):
	if v is JSUndefined:
		return 'undefined'
	if v == _Infinity:
		return 'Infinity'
	if v is _NaN:
		return 'NaN'
	if v is None:
		return 'null'
	if isinstance(v, bool):
		return ('false', 'true')[v]
	if isinstance(v, compat_numeric_types):
		return '{0:.7f}'.format(v).rstrip('.0')
	return _js_to_primitive(v)


_nullish = frozenset((None, JSUndefined))


def _js_eq(a, b):
	# NaN != any
	if _NaN in (a, b):
		return False
	# Object is Object
	if isinstance(a, type(b)) and isinstance(b, (dict, list)):
		return operator.is_(a, b)
	# general case
	if a == b:
		return True
	# null == undefined
	a_b = set((a, b))
	if a_b & _nullish:
		return a_b <= _nullish
	a, b = _js_to_primitive(a), _js_to_primitive(b)
	if not isinstance(a, compat_basestring):
		a, b = b, a
	# Number to String: convert the string to a number
	# Conversion failure results in ... false
	if isinstance(a, compat_basestring):
		return float_or_none(a) == b
	return a == b


def _js_neq(a, b):
	return not _js_eq(a, b)


def _js_id_op(op):

	def wrapped(a, b):
		if _NaN in (a, b):
			return op(_NaN, None)
		if not isinstance(a, (compat_basestring, compat_numeric_types)):
			a, b = b, a
		# strings are === if ==
		# why 'a' is not 'a': https://stackoverflow.com/a/1504848
		if isinstance(a, (compat_basestring, compat_numeric_types)):
			return a == b if op(0, 0) else a != b
		return op(a, b)

	return wrapped


def _js_comp_op(op):

	def wrapped(a, b):
		if JSUndefined in (a, b):
			return False
		if isinstance(a, compat_basestring):
			b = compat_str(b or 0)
		elif isinstance(b, compat_basestring):
			a = compat_str(a or 0)
		return op(a or 0, b or 0)

	return wrapped


def _js_ternary(cndn, if_true=True, if_false=False):
	"""Simulate JS's ternary operator (cndn?if_true:if_false)"""
	if cndn in (False, None, 0, '', JSUndefined, _NaN):
		return if_false
	return if_true


def _js_unary_op(op):

	def wrapped(_, a):
		return op(a)

	return wrapped


# https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/typeof
def _js_typeof(expr):
	try:
		return {
			JSUndefined: 'undefined',
			_NaN: 'number',
			_Infinity: 'number',
			True: 'boolean',
			False: 'boolean',
			None: 'object',
		}[expr]
	except (TypeError, KeyError):
		pass
	for t, n in (
		(compat_basestring, 'string'),
		(compat_numeric_types, 'number'),
	):
		if isinstance(expr, t):
			return n
	if callable(expr):
		return 'function'
	return 'object'


# (op, definition) in order of binding priority, tightest first
# avoid dict to maintain order
# definition None => Defined in JSInterpreter._operator
_OPERATORS = (
	('>>', _js_bit_op(operator.rshift, True)),
	('<<', _js_bit_op(operator.lshift, True)),
	('+', _js_add),
	('-', _js_arith_op(operator.sub)),
	('*', _js_arith_op(operator.mul)),
	('%', _js_mod),
	('/', _js_arith_op(operator.truediv, div=True)),
	('**', _js_exp),
)

_COMP_OPERATORS = (
	('===', _js_id_op(operator.is_)),
	('!==', _js_id_op(operator.is_not)),
	('==', _js_eq),
	('!=', _js_neq),
	('<=', _js_comp_op(operator.le)),
	('>=', _js_comp_op(operator.ge)),
	('<', _js_comp_op(operator.lt)),
	('>', _js_comp_op(operator.gt)),
)

_LOG_OPERATORS = (
	('|', _js_bit_op(operator.or_)),
	('^', _js_bit_op(operator.xor)),
	('&', _js_bit_op(operator.and_)),
)

_SC_OPERATORS = (
	('?', None),
	('??', None),
	('||', None),
	('&&', None),
)

_UNARY_OPERATORS_X = (
	('void', _js_unary_op(lambda _: JSUndefined)),
	('typeof', _js_unary_op(_js_typeof)),
)

_OPERATOR_RE = '|'.join(compat_map(lambda x: re.escape(x[0]), _OPERATORS + _LOG_OPERATORS))

_NAME_RE = r'[a-zA-Z_$][\w$]*'
_MATCHING_PARENS = dict(zip(*zip('()', '{}', '[]')))
_QUOTES = '\'"/'


class JSBreak(Exception):
	pass


class JSContinue(Exception):
	pass


class JSThrow(Exception):
	pass


class LocalNameSpace(compat_chain_map):
	def __getitem__(self, key):
		try:
			return super(LocalNameSpace, self).__getitem__(key)
		except KeyError:
			return JSUndefined

	def __setitem__(self, key, value):
		for scope in self.maps:
			if key in scope:
				scope[key] = value
				return
		self.maps[0][key] = value

	def __repr__(self):
		return 'LocalNameSpace%s' % (self.maps, )


class JSInterpreter(object):
	__named_object_counter = 0

	OP_CHARS = None

	def __init__(self, code, objects=None):
		self.code, self._functions = code, {}
		self._objects = {} if objects is None else objects
		if type(self).OP_CHARS is None:
			type(self).OP_CHARS = self.OP_CHARS = self.__op_chars()

	@classmethod
	def __op_chars(cls):
		op_chars = set(';,[')
		for op in cls._all_operators():
			if op[0].isalpha():
				continue
			op_chars.update(op[0])
		return op_chars

	def _named_object(self, namespace, obj):
		self.__named_object_counter += 1
		name = '%s%d' % ('__youtube_jsinterp_obj', self.__named_object_counter)
		namespace[name] = obj
		return name

	@classmethod
	def _separate(cls, expr, delim=',', max_split=None, skip_delims=None):
		if not expr:
			return
		# collections.Counter() is ~10% slower in both 2.7 and 3.9
		counters = {k: 0 for k in _MATCHING_PARENS.values()}
		start, splits, pos, delim_len = 0, 0, 0, len(delim) - 1
		in_quote, escaping, after_op, in_regex_char_group = None, False, True, False
		skipping = 0
		if skip_delims and not isinstance(skip_delims, tuple):
			skip_delims = (skip_delims,)
		skip_txt = None
		for idx, char in enumerate(expr):
			if skip_txt and idx <= skip_txt[1]:
				continue
			paren_delta = 0
			if not in_quote:
				if char == '/' and expr[idx:idx + 2] == '/*':
					# skip a comment
					skip_txt = expr[idx:].find('*/', 2)
					skip_txt = [idx, idx + skip_txt + 1] if skip_txt >= 2 else None
					if skip_txt:
						continue
				if char in _MATCHING_PARENS:
					counters[_MATCHING_PARENS[char]] += 1
					paren_delta = 1
				elif char in counters:
					counters[char] -= 1
					paren_delta = -1
			if not escaping:
				if char in _QUOTES and in_quote in (char, None):
					if in_quote or after_op or char != '/':
						in_quote = None if in_quote and not in_regex_char_group else char
				elif in_quote == '/' and char in '[]':
					in_regex_char_group = char == '['
			escaping = not escaping and in_quote and char == '\\'
			after_op = not in_quote and (char in cls.OP_CHARS or paren_delta > 0 or (after_op and char.isspace()))

			if char != delim[pos] or any(counters.values()) or in_quote:
				pos = skipping = 0
				continue
			elif skipping > 0:
				skipping -= 1
				continue
			elif pos == 0 and skip_delims:
				here = expr[idx:]
				for s in skip_delims:
					if here.startswith(s) and s:
						skipping = len(s) - 1
						break
				if skipping > 0:
					continue
			if pos < delim_len:
				pos += 1
				continue
			if skip_txt and skip_txt[0] >= start and skip_txt[1] <= idx - delim_len:
				yield expr[start:skip_txt[0]] + expr[skip_txt[1] + 1: idx - delim_len]
			else:
				yield expr[start: idx - delim_len]
			skip_txt = None
			start, pos = idx + 1, 0
			splits += 1
			if max_split and splits >= max_split:
				break
		if skip_txt and skip_txt[0] >= start:
			yield expr[start:skip_txt[0]] + expr[skip_txt[1] + 1:]
		else:
			yield expr[start:]

	@classmethod
	def _separate_at_paren(cls, expr, delim=None):
		if delim is None:
			delim = expr and _MATCHING_PARENS[expr[0]]
		separated = list(cls._separate(expr, delim, 1))

		if len(separated) < 2:
			raise RuntimeError('No terminating paren %s in %s' % (delim, expr))
		return separated[0][1:].strip(), separated[1].strip()

	@staticmethod
	def _all_operators(_cached=[]):
		if not _cached:
			_cached.extend(chain(
				# Ref: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Operator_Precedence
				_SC_OPERATORS, _LOG_OPERATORS, _COMP_OPERATORS, _OPERATORS, _UNARY_OPERATORS_X))
		return _cached

	def _operator(self, op, left_val, right_expr, local_vars, allow_recursion):
		if op in ('||', '&&'):
			if (op == '&&') ^ _js_ternary(left_val):
				return left_val  # short circuiting
		elif op == '??':
			if left_val not in (None, JSUndefined):
				return left_val
		elif op == '?':
			right_expr = _js_ternary(left_val, *self._separate(right_expr, ':', 1))

		right_val = self.interpret_expression(right_expr, local_vars, allow_recursion)
		opfunc = op and next((v for k, v in self._all_operators() if k == op), None)
		if not opfunc:
			return right_val

		try:
			return opfunc(left_val, right_val)
		except Exception as e:
			raise RuntimeError('Failed to evaluate', left_val, op, right_val, e)

	def _index(self, obj, idx):
		if idx == 'length' and isinstance(obj, list):
			return len(obj)
		try:
			return obj[int(idx)] if isinstance(obj, list) else obj[compat_str(idx)]
		except (TypeError, KeyError, IndexError) as e:
			raise RuntimeError('Cannot get index', idx, e)

	def _dump(self, obj, namespace):
		try:
			return dumps(obj)
		except TypeError:
			return self._named_object(namespace, obj)

	# used below
	_VAR_RET_THROW_RE = re.compile(r'''(?x)
		(?:(?P<var>var|const|let)\s+|(?P<ret>return)(?:\s+|(?=["'])|$)|(?P<throw>throw)\s+)
		''')
	_COMPOUND_RE = re.compile(r'''(?x)
		(?P<try>try)\s*\{|
		(?P<if>if)\s*\(|
		(?P<switch>switch)\s*\(|
		(?P<for>for)\s*\(|
		(?P<while>while)\s*\(
		''')
	_FINALLY_RE = re.compile(r'finally\s*\{')
	_SWITCH_RE = re.compile(r'switch\s*\(')

	def handle_operators(self, expr, local_vars, allow_recursion):

		for op, _ in self._all_operators():
			# hackety: </> have higher priority than <</>>, but don't confuse them
			skip_delim = (op + op) if op in '<>*?' else None
			if op == '?':
				skip_delim = (skip_delim, '?.')
			separated = list(self._separate(expr, op, skip_delims=skip_delim))
			if len(separated) < 2:
				continue

			right_expr = separated.pop()
			# handle operators that are both unary and binary, minimal BODMAS
			if op in ('+', '-'):
				# simplify/adjust consecutive instances of these operators
				undone = 0
				separated = [s.strip() for s in separated]
				while len(separated) > 1 and not separated[-1]:
					undone += 1
					separated.pop()
				if op == '-' and undone % 2 != 0:
					right_expr = op + right_expr
				elif op == '+':
					while len(separated) > 1 and set(separated[-1]) <= self.OP_CHARS:
						right_expr = separated.pop() + right_expr
					if separated[-1][-1:] in self.OP_CHARS:
						right_expr = separated.pop() + right_expr
				# hanging op at end of left => unary + (strip) or - (push right)
				left_val = separated[-1] if separated else ''
				for dm_op in ('*', '%', '/', '**'):
					bodmas = tuple(self._separate(left_val, dm_op, skip_delims=skip_delim))
					if len(bodmas) > 1 and not bodmas[-1].strip():
						expr = op.join(separated) + op + right_expr
						if len(separated) > 1:
							separated.pop()
							right_expr = op.join((left_val, right_expr))
						else:
							separated = [op.join((left_val, right_expr))]
							right_expr = None
						break
				if right_expr is None:
					continue

			left_val = self.interpret_expression(op.join(separated), local_vars, allow_recursion)
			return self._operator(op, left_val, right_expr, local_vars, allow_recursion), True

	def interpret_statement(self, stmt, local_vars, allow_recursion=100):
		if allow_recursion < 0:
			raise RuntimeError('Recursion limit reached')
		allow_recursion -= 1

		should_return = False
		# fails on (eg) if (...) stmt1; else stmt2;
		sub_statements = list(self._separate(stmt, ';')) or ['']
		expr = stmt = sub_statements.pop().strip()
		for sub_stmt in sub_statements:
			ret, should_return = self.interpret_statement(sub_stmt, local_vars, allow_recursion)
			if should_return:
				return ret, should_return

		m = self._VAR_RET_THROW_RE.match(stmt)
		if m:
			expr = stmt[len(m.group(0)):].strip()
			if m.group('throw'):
				raise JSThrow()
			should_return = 'return' if m.group('ret') else False
		if not expr:
			return None, should_return

		if expr[0] in _QUOTES:
			inner, outer = self._separate(expr, expr[0], 1)
			if expr[0] == '/':
				inner = re.compile(inner[1:].replace('[[', r'[\['))
			else:
				inner = loads(js_to_json(inner + expr[0]))
			if not outer:
				return inner, should_return
			expr = self._named_object(local_vars, inner) + outer

		if expr.startswith('new '):
			obj = expr[4:]
			if obj.startswith('Date('):
				left, right = self._separate_at_paren(obj[4:])
				date = unified_timestamp(
					self.interpret_expression(left, local_vars, allow_recursion))
				if date is None:
					raise RuntimeError('Failed to parse date', left)
				expr = self._dump(int(date * 1000), local_vars) + right
			else:
				raise RuntimeError('Unsupported object', obj)

		for op, _ in _UNARY_OPERATORS_X:
			if not expr.startswith(op):
				continue
			operand = expr[len(op):]
			if not operand or operand[0] != ' ':
				continue
			op_result = self.handle_operators(expr, local_vars, allow_recursion)
			if op_result:
				return op_result[0], should_return

		if expr.startswith('{'):
			inner, outer = self._separate_at_paren(expr)
			# try for object expression (Map)
			sub_expressions = [list(self._separate(sub_expr.strip(), ':', 1)) for sub_expr in self._separate(inner)]
			if all(len(sub_expr) == 2 for sub_expr in sub_expressions):
				def dict_item(key, val):
					val = self.interpret_expression(val, local_vars, allow_recursion)
					if re.match(_NAME_RE, key):
						return key, val
					return self.interpret_expression(key, local_vars, allow_recursion), val

				return dict(dict_item(k, v) for k, v in sub_expressions), should_return
			# or statement list
			inner, should_abort = self.interpret_statement(inner, local_vars, allow_recursion)
			if not outer or should_abort:
				return inner, should_abort or should_return
			else:
				expr = self._dump(inner, local_vars) + outer

		if expr.startswith('('):
			m = re.match(r'\((?P<d>[a-z])%(?P<e>[a-z])\.length\+(?P=e)\.length\)%(?P=e)\.length', expr)
			if m:
				# short-cut eval of frequently used `(d%e.length+e.length)%e.length`, worth ~6% on `pytest -k test_nsig`
				outer = None
				inner, should_abort = self._offset_e_by_d(m.group('d'), m.group('e'), local_vars)
			else:
				inner, outer = self._separate_at_paren(expr)
				inner, should_abort = self.interpret_statement(inner, local_vars, allow_recursion)
			if not outer or should_abort:
				return inner, should_abort or should_return
			else:
				expr = self._dump(inner, local_vars) + outer

		if expr.startswith('['):
			inner, outer = self._separate_at_paren(expr)
			name = self._named_object(local_vars, [
				self.interpret_expression(item, local_vars, allow_recursion)
				for item in self._separate(inner)])
			expr = name + outer

		m = self._COMPOUND_RE.match(expr)
		md = m.groupdict() if m else {}
		if md.get('if'):
			cndn, expr = self._separate_at_paren(expr[m.end() - 1:])
			if expr.startswith('{'):
				if_expr, expr = self._separate_at_paren(expr)
			else:
				# may lose ... else ... because of ll.368-374
				if_expr, expr = self._separate_at_paren(' %s;' % (expr,), delim=';')
			else_expr = None
			m = re.match(r'else\s*(?P<block>\{)?', expr)
			if m:
				if m.group('block'):
					else_expr, expr = self._separate_at_paren(expr[m.end() - 1:])
				else:
					# handle subset ... else if (...) {...} else ...
					exprs = list(self._separate(expr[m.end():], delim='}', max_split=2))
					if len(exprs) > 1:
						if re.match(r'\s*if\s*\(', exprs[0]) and re.match(r'\s*else\b', exprs[1]):
							else_expr = exprs[0] + '}' + exprs[1]
							expr = (exprs[2] + '}') if len(exprs) == 3 else None
						else:
							else_expr = exprs[0]
							exprs.append('')
							expr = '}'.join(exprs[1:])
					else:
						else_expr = exprs[0]
						expr = None
					else_expr = else_expr.lstrip() + '}'
			cndn = _js_ternary(self.interpret_expression(cndn, local_vars, allow_recursion))
			ret, should_abort = self.interpret_statement(
				if_expr if cndn else else_expr, local_vars, allow_recursion)
			if should_abort:
				return ret, True

		elif md.get('try'):
			try_expr, expr = self._separate_at_paren(expr[m.end() - 1:])
			err = None
			try:
				ret, should_abort = self.interpret_statement(try_expr, local_vars, allow_recursion)
				if should_abort:
					return ret, True
			except Exception as e:
				# This works for now, but makes debugging future issues very hard
				err = e

			pending = (None, False)
			m = re.match(r'catch\s*(?P<err>\(\s*{_NAME_RE}\s*\))?\{{'.format(**globals()), expr)
			if m:
				sub_expr, expr = self._separate_at_paren(expr[m.end() - 1:])
				if err:
					catch_vars = {}
					if m.group('err'):
						catch_vars[m.group('err')] = err
					catch_vars = local_vars.new_child(m=catch_vars)
					err, pending = None, self.interpret_statement(sub_expr, catch_vars, allow_recursion)

			m = self._FINALLY_RE.match(expr)
			if m:
				sub_expr, expr = self._separate_at_paren(expr[m.end() - 1:])
				ret, should_abort = self.interpret_statement(sub_expr, local_vars, allow_recursion)
				if should_abort:
					return ret, True

			ret, should_abort = pending
			if should_abort:
				return ret, True

			if err:
				raise err

		elif md.get('for') or md.get('while'):
			init_or_cond, remaining = self._separate_at_paren(expr[m.end() - 1:])
			if remaining.startswith('{'):
				body, expr = self._separate_at_paren(remaining)
			else:
				switch_m = self._SWITCH_RE.match(remaining)
				if switch_m:
					switch_val, remaining = self._separate_at_paren(remaining[switch_m.end() - 1:])
					body, expr = self._separate_at_paren(remaining, '}')
					body = 'switch(%s){%s}' % (switch_val, body)
				else:
					body, expr = remaining, ''
			if md.get('for'):
				start, cndn, increment = self._separate(init_or_cond, ';')
				self.interpret_expression(start, local_vars, allow_recursion)
			else:
				cndn, increment = init_or_cond, None
			while _js_ternary(self.interpret_expression(cndn, local_vars, allow_recursion)):
				try:
					ret, should_abort = self.interpret_statement(body, local_vars, allow_recursion)
					if should_abort:
						return ret, True
				except JSBreak:
					break
				except JSContinue:
					pass
				if increment:
					self.interpret_expression(increment, local_vars, allow_recursion)

		elif md.get('switch'):
			switch_val, remaining = self._separate_at_paren(expr[m.end() - 1:])
			switch_val = self.interpret_expression(switch_val, local_vars, allow_recursion)
			body, expr = self._separate_at_paren(remaining, '}')
			items = body.replace('default:', 'case default:').split('case ')[1:]
			for default in (False, True):
				matched = False
				for item in items:
					case, stmt = (i.strip() for i in self._separate(item, ':', 1))
					if default:
						matched = matched or case == 'default'
					elif not matched:
						matched = (case != 'default' and switch_val == self.interpret_expression(case, local_vars, allow_recursion))
					if not matched:
						continue
					try:
						ret, should_abort = self.interpret_statement(stmt, local_vars, allow_recursion)
						if should_abort:
							return ret
					except JSBreak:
						break
				if matched:
					break

		if md:
			ret, should_abort = self.interpret_statement(expr, local_vars, allow_recursion)
			return ret, should_abort or should_return

		# Comma separated statements
		sub_expressions = list(self._separate(expr))
		if len(sub_expressions) > 1:
			for sub_expr in sub_expressions:
				ret, should_abort = self.interpret_statement(sub_expr, local_vars, allow_recursion)
				if should_abort:
					return ret, True
			return ret, False

		for m in re.finditer(r'''(?x)
				(?P<pre_sign>\+\+|--)(?P<var1>{_NAME_RE})|
				(?P<var2>{_NAME_RE})(?P<post_sign>\+\+|--)'''.format(**globals()), expr):
			var = m.group('var1') or m.group('var2')
			start, end = m.span()
			sign = m.group('pre_sign') or m.group('post_sign')
			ret = local_vars[var]
			local_vars[var] = _js_add(ret, 1 if sign[0] == '+' else -1)
			if m.group('pre_sign'):
				ret = local_vars[var]
			expr = expr[:start] + self._dump(ret, local_vars) + expr[end:]

		if not expr:
			return None, should_return

		m = re.match(r'''(?x)
			(?P<assign>
				(?P<out>{_NAME_RE})(?:\[(?P<out_idx>(?:.+?\]\s*\[)*.+?)\])?\s*
				(?P<op>{_OPERATOR_RE})?
				=(?!=)(?P<expr>.*)$
			)|(?P<return>
				(?!if|return|true|false|null|undefined|NaN|Infinity)(?P<name>{_NAME_RE})$
			)|(?P<indexing>
				(?P<in>{_NAME_RE})\[(?P<in_idx>(?:.+?\]\s*\[)*.+?)\]$
			)|(?P<attribute>
				(?P<var>{_NAME_RE})(?:(?P<nullish>\?)?\.(?P<member>[^(]+)|\[(?P<member2>[^\]]+)\])\s*
			)|(?P<function>
				(?P<fname>{_NAME_RE})\((?P<args>.*)\)$
			)'''.format(**globals()), expr)
		md = m.groupdict() if m else {}
		if md.get('assign'):
			left_val = local_vars.get(m.group('out'))

			if not m.group('out_idx'):
				local_vars[m.group('out')] = self._operator(
					m.group('op'), left_val, m.group('expr'), local_vars, allow_recursion)
				return local_vars[m.group('out')], should_return
			elif left_val in (None, JSUndefined):
				raise RuntimeError('Cannot index undefined variable', m.group('out'))

			indexes = re.split(r'\]\s*\[', m.group('out_idx'))
			for i, idx in enumerate(indexes, 1):
				idx = self.interpret_expression(idx, local_vars, allow_recursion)
				if i < len(indexes):
					left_val = self._index(left_val, idx)
			if isinstance(idx, float):
				idx = int(idx)
			left_val[idx] = self._operator(
				m.group('op'), self._index(left_val, idx) if m.group('op') else None,
				m.group('expr'), local_vars, allow_recursion)
			return left_val[idx], should_return

		elif expr.isdigit():
			return int(expr), should_return

		elif expr == 'break':
			raise JSBreak()
		elif expr == 'continue':
			raise JSContinue()

		elif expr == 'undefined':
			return JSUndefined, should_return
		elif expr == 'NaN':
			return _NaN, should_return
		elif expr == 'Infinity':
			return _Infinity, should_return

		elif md.get('return'):
			return local_vars[m.group('name')], should_return

		try:
			ret = loads(js_to_json(expr))
			if not md.get('attribute'):
				return ret, should_return
		except ValueError:
			pass

		if md.get('indexing'):
			val = local_vars[m.group('in')]
			for idx in re.split(r'\]\s*\[', m.group('in_idx')):
				idx = self.interpret_expression(idx, local_vars, allow_recursion)
				val = self._index(val, idx)
			return val, should_return

		op_result = self.handle_operators(expr, local_vars, allow_recursion)
		if op_result:
			return op_result[0], should_return

		if md.get('attribute'):
			variable, member, nullish = m.group('var', 'member', 'nullish')
			if not member:
				member = self.interpret_expression(m.group('member2'), local_vars, allow_recursion)
			arg_str = expr[m.end():]
			if arg_str.startswith('('):
				arg_str, remaining = self._separate_at_paren(arg_str)
			else:
				arg_str, remaining = None, arg_str

			def assertion(cndn, msg):
				""" assert, but without risk of getting optimized out """
				if not cndn:
					raise RuntimeError('{0} {1}'.format(member, msg))

			def eval_method(variable, member):
				if (variable, member) == ('console', 'debug'):
					return

				ARG_MSG = 'takes one or more arguments'
				ARG_TWO_MSG = 'takes two arguments'
				ARG_NOT_MSG = 'does not take any arguments'
				ARG_2_MSG = 'takes at most 2 arguments'
				LIST_MSG = 'must be applied on a list'
				STR_MSG = 'must be applied on a string'

				types = {
					'String': compat_str,
					'Math': float,
					'Array': list,
				}

				obj = local_vars.get(variable)
				if obj in (JSUndefined, None):
					obj = types.get(variable, JSUndefined)
				if obj is JSUndefined:
					try:
						if variable not in self._objects:
							self._objects[variable] = self.extract_object(variable)
						obj = self._objects[variable]
					except Exception:
						if not nullish:
							raise

				if nullish and obj is JSUndefined:
					return JSUndefined

				# Member access
				if arg_str is None:
					return self._index(obj, member)

				# Function call
				argvals = [
					self.interpret_expression(v, local_vars, allow_recursion)
					for v in self._separate(arg_str)]

				# Fixup prototype call
				if isinstance(obj, type):
					new_member, rest = member.partition('.')[0::2]
					if new_member == 'prototype':
						new_member, func_prototype = rest.partition('.')[0::2]
						assertion(argvals, ARG_MSG)
						assertion(isinstance(argvals[0], obj), 'must bind to type {0}'.format(obj))
						if func_prototype == 'call':
							obj = argvals.pop(0)
						elif func_prototype == 'apply':
							assertion(len(argvals) == 2, ARG_TWO_MSG)
							obj, argvals = argvals
							assertion(isinstance(argvals, list), 'second argument must be a list')
						else:
							raise RuntimeError('Unsupported Function method', func_prototype)
						member = new_member

				if obj is compat_str:
					if member == 'fromCharCode':
						assertion(argvals, ARG_MSG)
						return ''.join(compat_chr(int(n)) for n in argvals)
					raise RuntimeError('Unsupported string method', member)
				elif obj is float:
					if member == 'pow':
						assertion(len(argvals) == 2, ARG_TWO_MSG)
						return argvals[0] ** argvals[1]
					raise RuntimeError('Unsupported Math method', member)

				if member == 'split':
					assertion(len(argvals) <= 2, 'takes at most two arguments')
					return obj.split(argvals[0]) if argvals[0] else list(obj)
				elif member == 'join':
					assertion(isinstance(obj, list), LIST_MSG)
					assertion(len(argvals) <= 1, 'takes at most one argument')
					return (',' if len(argvals) == 0 else argvals[0]).join(
						('' if x in (None, JSUndefined) else _js_to_string(x))
						for x in obj)
				elif member == 'reverse':
					assertion(not argvals, ARG_NOT_MSG)
					obj.reverse()
					return obj
				elif member == 'slice':
					assertion(isinstance(obj, (list, str, compat_str)), 'must be applied on a list or string')
					# From [1]:
					# .slice() - like [:]
					# .slice(n) - like [n:] (not [slice(n)]
					# .slice(m, n) - like [m:n] or [slice(m, n)]
					# [1] https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/slice
					assertion(len(argvals) <= 2, 'takes between 0 and 2 arguments')
					if len(argvals) < 2:
						argvals += (None,)
					return obj[slice(*argvals)]
				elif member == 'splice':
					assertion(isinstance(obj, list), LIST_MSG)
					assertion(argvals, ARG_MSG)
					index, how_many = compat_map(int, (argvals + [len(obj)])[:2])
					if index < 0:
						index += len(obj)
					res = [obj.pop(index) for _ in range(index, min(index + how_many, len(obj)))]
					obj[index:index] = argvals[2:]
					return res
				elif member in ('shift', 'pop'):
					assertion(isinstance(obj, list), LIST_MSG)
					assertion(not argvals, ARG_NOT_MSG)
					if len(obj) > 0:
						return obj.pop(0 if member == 'shift' else -1)
					return JSUndefined
				elif member == 'unshift':
					assertion(isinstance(obj, list), LIST_MSG)
					# not enforced: assertion(argvals, ARG_MSG)
					obj[0:0] = argvals
					return len(obj)
				elif member == 'push':
					# not enforced: assertion(argvals, ARG_MSG)
					obj.extend(argvals)
					return len(obj)
				elif member == 'forEach':
					assertion(argvals, ARG_MSG)
					assertion(len(argvals) <= 2, ARG_2_MSG)
					f, this = (argvals + [''])[:2]
					return [f((item, idx, obj), {'this': this}, allow_recursion) for idx, item in enumerate(obj)]
				elif member == 'indexOf':
					assertion(argvals, ARG_MSG)
					assertion(len(argvals) <= 2, ARG_2_MSG)
					idx, start = (argvals + [0])[:2]
					try:
						return obj.index(idx, start)
					except ValueError:
						return -1
				elif member == 'charCodeAt':
					assertion(isinstance(obj, (str, compat_str)), STR_MSG)
					# assertion(len(argvals) == 1, 'takes exactly one argument') # but not enforced
					idx = argvals[0] if len(argvals) > 0 and isinstance(argvals[0], int) else 0
					if idx >= len(obj):
						return None
					return ord(obj[idx])

				idx = int(member) if isinstance(obj, list) else member
				return obj[idx](argvals, allow_recursion=allow_recursion)

			if remaining:
				ret, should_abort = self.interpret_statement(
					self._named_object(local_vars, eval_method(variable, member)) + remaining,
					local_vars, allow_recursion)
				return ret, should_return or should_abort
			else:
				return eval_method(variable, member), should_return

		elif md.get('function'):
			fname = m.group('fname')
			argvals = [self.interpret_expression(v, local_vars, allow_recursion) for v in self._separate(m.group('args'))]
			if fname in local_vars:
				return local_vars[fname](argvals, allow_recursion=allow_recursion), should_return
			elif fname not in self._functions:
				self._functions[fname] = self.extract_function_from_code(*self.extract_function_code(fname))
			return self._functions[fname](argvals, allow_recursion=allow_recursion), should_return

		raise RuntimeError('Unsupported JS expression', expr[:40])

	def interpret_expression(self, expr, local_vars, allow_recursion):
		ret, should_return = self.interpret_statement(expr, local_vars, allow_recursion)
		if should_return:
			raise RuntimeError('Cannot return from an expression')
		return ret

	def extract_object(self, objname):
		_FUNC_NAME_RE = r'''(?:{n}|"{n}"|'{n}')'''.format(n=_NAME_RE)
		obj = {}
		fields = None
		for obj_m in re.finditer(
			r'''(?xs)
				{0}\s*\.\s*{1}|{1}\s*=\s*\{{\s*
				(?P<fields>({2}\s*:\s*function\s*\(.*?\)\s*\{{.*?}}(?:,\s*)?)*)
				}}\s*;
			'''.format(_NAME_RE, re.escape(objname), _FUNC_NAME_RE),
			self.code):
			fields = obj_m.group('fields')
			if fields:
				break
		else:
			raise RuntimeError('Could not find object', objname)
		# Currently, it only supports function definitions
		for f in re.finditer(
			r'''(?x)
				(?P<key>%s)\s*:\s*function\s*\((?P<args>(?:%s|,)*)\){(?P<code>[^}]+)}
			''' % (_FUNC_NAME_RE, _NAME_RE),
			fields):
			argnames = self.build_arglist(f.group('args'))
			obj[remove_quotes(f.group('key'))] = self.build_function(argnames, f.group('code'))

		return obj

	@staticmethod
	def _offset_e_by_d(d, e, local_vars):
		""" Short-cut eval: (d%e.length+e.length)%e.length """
		try:
			d = local_vars[d]
			e = local_vars[e]
			e = len(e)
			return _js_mod(_js_mod(d, e) + e, e), False
		except Exception:
			return None, True

	def extract_function_code(self, funcname):
		""" @returns argnames, code """
		func_m = re.search(
			r'''(?xs)
				(?:
					function\s+%(name)s|
					[{;,]\s*%(name)s\s*=\s*function|
					(?:var|const|let)\s+%(name)s\s*=\s*function
				)\s*
				\((?P<args>[^)]*)\)\s*
				(?P<code>{.+})''' % {'name': re.escape(funcname)},
			self.code)
		if func_m is None:
			raise RuntimeError('Could not find JS function', funcname)
		code, _ = self._separate_at_paren(func_m.group('code'))  # refine the match
		return self.build_arglist(func_m.group('args')), code

	def extract_function_from_code(self, argnames, code, *global_stack):
		local_vars = {}
		while True:
			mobj = re.search(r'function\((?P<args>[^)]*)\)\s*{', code)
			if mobj is None:
				break
			start, body_start = mobj.span()
			body, remaining = self._separate_at_paren(code[body_start - 1:])
			name = self._named_object(local_vars, self.extract_function_from_code(
				[x.strip() for x in mobj.group('args').split(',')],
				body, local_vars, *global_stack))
			code = code[:start] + name + remaining
		return self.build_function(argnames, code, local_vars, *global_stack)

	@classmethod
	def build_arglist(cls, arg_text):
		if not arg_text:
			return []

		def valid_arg(y):
			y = y.strip()
			if not y:
				raise RuntimeError('Missing arg in "%s"' % arg_text)
			return y

		return [valid_arg(x) for x in cls._separate(arg_text)]

	def build_function(self, argnames, code, *global_stack):
		global_stack = list(global_stack) or [{}]
		argnames = tuple(argnames)

		def resf(args, kwargs=None, allow_recursion=100):
			kwargs = kwargs or {}
			global_stack[0].update(compat_zip_longest(argnames, args, fillvalue=JSUndefined))
			global_stack[0].update(kwargs)
			var_stack = LocalNameSpace(*global_stack)
			ret, should_abort = self.interpret_statement(code.replace('\n', ' '), var_stack, allow_recursion - 1)
			if should_abort:
				return ret
		return resf
