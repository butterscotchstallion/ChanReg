###
# Copyright (c) 2013, Nicolas Coevoet
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

import os
import time
import supybot.utils as utils
from supybot.commands import *
import supybot.commands as commands
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.ircmsgs as ircmsgs
import supybot.callbacks as callbacks
import supybot.ircdb as ircdb
import supybot.log as log
import supybot.schedule as schedule
import socket
import re
import sqlite3
import collections

try:
	from supybot.i18n import PluginInternationalization
	_ = PluginInternationalization('ChanReg')
except:
	# Placeholder that allows to run the plugin on a bot
	# without the i18n module
	_ = lambda x:x

import threading
import supybot.world as world

def _getRe(f):
	def get(irc, msg, args, state):
		original = args[:]
		s = args.pop(0)
		def isRe(s):
			try:
				foo = f(s)
				return True
			except ValueError:
				return False
		try:
			while len(s) < 512 and not isRe(s):
				s += ' ' + args.pop(0)
			if len(s) < 512:
				state.args.append([s,f(s)])
			else:
				state.errorInvalid('regular expression', s)
		except IndexError:
			args[:] = original
			state.errorInvalid('regular expression', s)
	return get

getPatternAndMatcher = _getRe(utils.str.perlReToPythonRe)

addConverter('getPatternAndMatcher', getPatternAndMatcher)

class Chan (object):
	def __init__(self,name):
		object.__init__(self)
		self.name = name
		self.kinds = {}
		self.nicks = {}
	
	def add (self,prefix,pattern,regexp,action,kind,db):
		c = db.cursor()
		c.execute("""INSERT INTO regexps VALUES (NULL, ?, ?, ?, ?, ?, ?, ?)""", (self.name,prefix,float(time.time()),kind,pattern,action,'1'))
		db.commit()
		c.close()
		if not kind in self.kinds:
			self.kinds[kind] = {}
		i = Item()
		i.uid = int(c.lastrowid)
		i.channel = self.name
		i.re = regexp
		i.pattern = pattern
		i.action = action
		i.kind = kind
		i.enable = 1
		i.owner = prefix
		self.kinds[kind][i.pattern] = i
		return i.uid

class Item (object):
	def __init__(self):
		object.__init__(self)
		self.uid = None
		self.channel = None
		self.re = None
		self.pattern = None
		self.action = None
		self.kind = None
		self.enable = 0
		self.owner = None

class ChanReg(callbacks.Plugin,plugins.ChannelDBHandler):
	"""Add the help for "@plugin help ChanReg" here
	This should describe *how* to use this plugin."""
	threaded = True
	noIgnore = True

	def __init__(self, irc):
		self.__parent = super(ChanReg, self)
		self.__parent.__init__(irc)
		callbacks.Plugin.__init__(self, irc)
		plugins.ChannelDBHandler.__init__(self)
		self.regexps = {}
		self._ircs = {}

	def onmsg (self,irc,msg,args,channel,regexp,action):
		"""[<channel>] <regexp> <action> 
		
		regexp should match userhostmask#user?name account :text,
		if bot doesn't support CAPS, it's userhostmask :text
		for action you can use $id, $channel, $nick, $hostmask, $account, $username, $*, $1, etc
		"""
		db = self.getDb(channel)
		chan = self.getChan(irc,channel)
		irc.reply('#%s added' % chan.add(msg.prefix,regexp[0],regexp[1],action,'text',db))
	onmsg = wrap(onmsg,['op','getPatternAndMatcher','text'])

	def onnick (self,irc,msg,args,channel,regexp,action):
		"""[<channel>] <regexp> <action> 
		
		regexp should match userhostmask#user?name account :oldNick newNick,
		if bot doesn't support CAPS, it's userhostmask :oldNick newNick
		for action you can use $id, $channel, $nick, $hostmask, $account, $username, $*, $1, etc
		"""
		db = self.getDb(channel)
		chan = self.getChan(irc,channel)
		irc.reply('#%s added' % chan.add(msg.prefix,regexp[0],regexp[1],action,'nick',db))
	onnick = wrap(onnick,['op','getPatternAndMatcher','text'])

	def onjoin (self,irc,msg,args,channel,regexp,action):
		"""[<channel>] <regexp> <action> 
		
		regexp should match userhostmask#user?name account,
		if bot doesn't support CAPS, it's userhostmask
		for action you can use $id, $channel, $nick, $hostmask, $account, $username, $*, $1, etc
		"""
		db = self.getDb(channel)
		chan = self.getChan(irc,channel)
		irc.reply('#%s added' % chan.add(msg.prefix,regexp[0],regexp[1],action,'join',db))
	onjoin = wrap(onjoin,['op','getPatternAndMatcher','text'])
	
	def onquit (self,irc,msg,args,channel,regexp,action):
		"""[<channel>] <regexp> <action> 
		
		regexp should match userhostmask#user?name account :reason (if there is one)
		if bot doesn't support CAPS, it's userhostmask :reason
		for action you can use $id, $channel, $nick, $hostmask, $account, $username, $*, $1, etc
		"""
		db = self.getDb(channel)
		chan = self.getChan(irc,channel)
		irc.reply('#%s added' % chan.add(msg.prefix,regexp[0],regexp[1],action,'quit',db))
	onquit = wrap(onquit,['op','getPatternAndMatcher','text'])
	
	def list (self,irc,msg,args,channel):
		"""[<channel>] 
		
		return list of regular expression for that channel
		"""
		chan = self.getChan(irc,channel)
		L = []
		for k in chan.kinds:
			L.append('for %s' % k)
			for i in list(chan.kinds[k].keys()):
				p = chan.kinds[k][i]
				L.append('[#%s %s %s %s %s]' % (p.uid,p.kind,p.pattern,p.action,p.enable))
		irc.reply(', '.join(L), private=True)
	list = wrap(list,['op'])
	
	def regquery (self,irc,msg,args,channel,text):
		"""[<channel>] <text>
		
		return matched items
		"""
		db = self.getDb(channel)
		c = db.cursor()
		glob = '*%s*' % text
		like = '%'+text+'%'
		c.execute ("""SELECT id, kind, regexp, action, enable FROM regexps WHERE channel=? AND (regexp GLOB ? OR regexp LIKE ? OR action GLOB ? or action GLOB ?) ORDER BY id DESC""",(channel,glob,like,glob,like))
		items = c.fetchall()
		c.close()
		L = []
		if len(items):
			for item in items:
				(uid,kind,regexp,action,enable) = item
				L.append('[#%s %s %s %s %s]' % (uid,kind,regexp,action,enable))
		irc.reply(', '.join(L))
	regquery = wrap(regquery,['op','text'])
	
	def regtoggle (self,irc,msg,args,channel,uids,flag):
		"""[<channel>] <id>,[<id>] <boolean>
		
		enable or disable a regexp
		"""
		db = self.getDb(channel)
		c = db.cursor()
		n = 0
		if flag:
			flag = '1'
		else:
			flag = '0'
		for uid in uids:
			c.execute ("""SELECT channel,kind,enable FROM regexps WHERE id=?""",(uid,))
			items = c.fetchall()
			if len(items):
				(channel,kind,enable) = items[0]
				chan = self.getChan(irc,channel)
				c.execute("""UPDATE regexps SET enable=? WHERE id=?""",(flag,uid))
				for k in list(chan.kinds[kind].keys()):
					if chan.kinds[kind][k].uid == uid:
						chan.kinds[kind][k].enable = flag
						break
				n = n + 1
		if n > 0:
			db.commit()
		if len(uids) == n:
			irc.replySuccess()
		else:
			irc.reply('item not found')
		c.close()
	regtoggle = wrap(regtoggle,['op',commalist('int'),'boolean'])
	
	def regremove (self,irc,msg,args,channel,uids):
		"""[<channel>] <id>,[<id>]
		
		remove regexps
		"""
		db = self.getDb(channel)
		c = db.cursor()
		n = 0
		for uid in uids:
			c.execute ("""SELECT channel,kind,enable FROM regexps WHERE id=?""",(uid,))
			items = c.fetchall()
			if len(items):
				(channel,kind,enable) = items[0]
				chan = self.getChan(irc,channel)
				c.execute("""DELETE FROM regexps WHERE id=?""",(uid,))
				for k in list(chan.kinds[kind].keys()):
					if chan.kinds[kind][k].uid == uid:
						del chan.kinds[kind][k]
						break
				n = n + 1
		if n > 0:
			db.commit()
		if len(uids) == n:
			irc.replySuccess()
		else:
			irc.reply('item not found')
		c.close()
	regremove = wrap(regremove,['op',commalist('int')])
	
	def reginfo (self,irc,msg,args,channel,uid):
		"""[<channel>] <id>
		
		return info about the regexp
		"""
		if not ircdb.checkCapability(msg.prefix, 'owner'):
			return
		db = self.getDb(channel)
		c = db.cursor()
		c.execute ("""SELECT channel,oper,at,kind,regexp,action,enable FROM regexps WHERE id=?""",(uid,))
		items = c.fetchall()
		c.close()
		if len(items):
			(channel,oper,at,kind,regexp,action,enable) = items[0]
			irc.reply('[#%s %s %s %s %s %s %s %s]' % (uid,channel,oper,time.strftime('%Y-%m-%d %H:%M:%S GMT',time.gmtime(float(at))),kind,regexp,action,enable))
		else:
			irc.reply('item not found')
	reginfo = wrap(reginfo,['op','int'])
	
	def makeDb(self, filename):
		"""Create a database and connect to it."""
		if os.path.exists(filename):
			db = sqlite3.connect(filename,timeout=10)
			db.text_factory = str
			return db
		db = sqlite3.connect(filename)
		db.text_factory = str
		c = db.cursor()
		c.execute("""CREATE TABLE regexps (
				id INTEGER PRIMARY KEY,
				channel VARCHAR(1000) NOT NULL,
				oper VARCHAR(1000) NOT NULL,
				at TIMESTAMP NOT NULL,
				kind VARCHAR(4) NOT NULL,
				regexp VARCHAR(1000) NOT NULL,
				action VARCHAR(1000) NOT NULL,
				enable VARCHAR(1) NOT NULL
				)""")
		db.commit()
		return db
	
	def getDb(self,channel):
		currentThread = threading.currentThread()
		if channel not in self.dbCache and currentThread == world.mainThread:
			self.dbCache[channel] = self.makeDb(self.makeFilename(channel))
		if currentThread != world.mainThread:
			db = self.makeDb(self.makeFilename(channel))
		else:
			db = self.dbCache[channel]
			db.isolation_level = None
		return db 
	
	def getIrc (self,irc):
		if not irc in self._ircs:
			self._ircs[irc] = {}
		return self._ircs[irc]
	
	def getChan (self,irc,channel):
		i = self.getIrc(irc)
		if not channel in i:
			i[channel] = Chan(channel)
			db = self.getDb(channel)
			c = db.cursor()
			c.execute("""SELECT id,channel,regexp,action,kind,enable,oper from regexps where channel=?""",(channel,))
			items = c.fetchall()
			c.close()
			if len(items):
				self.log.debug('restoring %s items for %s' % (len(items),channel))
				for item in items:
					(uid,channel,pattern,action,kind,enable,prefix) = item
					o = Item()
					o.uid = uid
					o.channel = channel
					o.re = utils.str.perlReToPythonRe(pattern)
					o.pattern = pattern
					o.action = action
					o.kind = kind
					o.enable = enable
					o.owner = prefix
					if not kind in i[channel].kinds:
						i[channel].kinds[kind] = {}
					i[channel].kinds[kind][pattern] = o
		return i[channel]
	
	def do352(self, irc, msg):
		chan = self.getChan(irc,msg.args[1])
		(nick, ident, host) = (msg.args[5], msg.args[2], msg.args[3])
		if not nick in chan.nicks:
			chan.nicks[nick] = ['%s!%s@%s' % (nick,ident,host),'','']
	
	def do354 (self,irc,msg):
		# WHO $channel %tnuhiar,42
		# irc.nick 42 ident ip host nick account realname
		if msg.args[1] == '42':
			(garbage,digit,ident,ip,host,nick,account,realname) = msg.args
			if account == '0':
				account = ''
			for channel in irc.state.channels:
				if nick in irc.state.channels[channel].users:
					chan = self.getChan(irc,channel)
					chan.nicks[nick] = ['%s!%s@%s' % (nick,ident,host),account,realname.replace(' ','?')]
	
	def act (self, irc, msg, channel, command, owner):
		tokens = callbacks.tokenize(command)
		#if ircdb.checkCapability(owner, 'owner') or ircdb.checkCapability(owner, '%s,op' % channel):
		#	owner = irc.prefix
		#elif ircdb.checkCapability(irc.prefix, 'owner') or ircdb.checkCapability(irc.prefix, '%s,op' % channel):
		#	owner = irc.prefix
		msg.command = 'PRIVMSG'
		msg.prefix = owner
		self.Proxy(irc.irc, msg, tokens)
	
	def checkAndAct (self,irc,prefix,chan,kind,items,text,msg):
		for pattern in list(items.keys()):
			item = chan.kinds[kind][pattern]
			if item.enable == '1':
				for match in re.finditer(item.re, text):
					if match:
						act = item.action
						account = ''
						gecos = ''
						if prefix.split('!')[0] in chan.nicks:
							(prefix,account,gecos) = chan.nicks[prefix.split('!')[0]]
						act = act.replace('$nick',prefix.split('!')[0])
						act = act.replace('$hostmask',prefix)
						act = act.replace('$account',account)
						act = act.replace('$username',gecos)
						act = act.replace('$id',str(item.uid))
						act = act.replace('$channel',chan.name)
						act = act.replace('$*',text)
						for (i, j) in enumerate(match.groups()):
							act = re.sub(r'\$' + str(i+1), match.group(i+1), act)
						self.act(irc,msg,chan.name,act,item.owner)
						break
	
	def checkMessage (self,irc,msg):
		(channels, text) = msg.args
		for channel in channels.split(','):
			if irc.isChannel(channel) and channel in irc.state.channels:
				chan = self.getChan(irc,channel)
				if 'text' in chan.kinds:
					s = msg.prefix
					if not msg.nick in chan.nicks:
						chan.nicks[msg.nick] = [msg.prefix,'','']
					if chan.nicks[msg.nick][2] != '':
						s += '#' + chan.nicks[msg.nick][2]
					if chan.nicks[msg.nick][1] != '':
						s += ' ' + chan.nicks[msg.nick][1]
					s += ' :' + text
					self.checkAndAct(irc,msg.prefix,chan,'text',chan.kinds['text'],s,msg)
	
	def doPrivmsg (self,irc,msg):
		self.checkMessage(irc,msg)
		
	def doNotice (self,irc,msg):
		self.checkMessage(irc,msg)
	
	def doAccount (self,irc,msg):
		if ircutils.isUserHostmask(msg.prefix):
			nick = ircutils.nickFromHostmask(msg.prefix)
			for channel in irc.state.channels:
				chan = self.getChan(irc,channel)
				if nick in chan.nicks:
					a = chan.nicks[nick]
					account = msg.args[0]
					if account == '*':
						account = ''
					a[1] = account
					chan.nicks[nick] = a
	
	def doNick (self,irc,msg):
		oldNick = msg.prefix.split('!')[0]
		newNick = msg.args[0]
		for channel in irc.state.channels:
			if ircutils.isChannel(channel):
				chan = self.getChan(irc,channel)
				if oldNick in chan.nicks:
					item = chan.nicks[oldNick]
					(n,i,h) = ircutils.splitHostmask(item[0])
					item[0] = ircutils.joinHostmask(newNick,i,h)
					if 'nick' in chan.kinds:
						text = item[0]
						self.checkAndAct(irc,msg.prefix,chan,'nick',chan.kinds['nick'],'%s %s' % (oldNick,newNick),msg)
					del chan.nicks[oldNick]
					chan.nicks[newNick] = item
		
	def doJoin (self,irc,msg):
		channels = msg.args[0].split(',')
		for channel in channels:
			if ircutils.isChannel(channel) and channel in irc.state.channels:
				chan = self.getChan(irc,channel)
				if len(msg.args) == 3:
					#extended join
					account = msg.args[1]
					if account == '*':
						account = ''
					chan.nicks[msg.nick] = [msg.prefix,account,msg.args[2].replace(' ','?')]
				else:
					chan.nicks[msg.nick] = [msg.prefix,'','']
				if 'join' in chan.kinds:
					text = msg.prefix
					if chan.nicks[msg.nick][2] != '':
						text += '#'+chan.nicks[msg.nick][2]
					if chan.nicks[msg.nick][1] != '':
						text += ' '+chan.nicks[msg.nick][1]
					self.checkAndAct(irc,msg.prefix,chan,'join',chan.kinds['join'],text,msg)
	
	def doPart (self,irc,msg):
		reason = None
		if len(msg.args) == 2:
			reason = msg.args[1].lstrip().rstrip()
		for channel in msg.args[0].split(','):
			chan = self.getChan(irc,channel)
			if 'quit' in chan.kinds:
				s = msg.prefix
				if reason:
					s += ' :' + reason
				self.checkAndAct(irc,msg.prefix,chan,'quit',chan.kinds['quit'],s,msg)
			if msg.nick in chan.nicks:
				del chan.nicks[msg.nick]
	
	def doQuit (self,irc,msg):
		reason = None
		if len(msg.args) == 1:
			reason = msg.args[0].lstrip().rstrip()
		for channel in irc.state.channels:
			chan = self.getChan(irc,channel)
			if msg.nick in chan.nicks:
				if 'quit' in chan.kinds:
					s = msg.prefix
					if reason:
						s += ' :' + reason
					self.checkAndAct(irc,msg.prefix,chan,'quit',chan.kinds['quit'],s,msg)
				del chan.nicks[msg.nick]
	


Class = ChanReg

