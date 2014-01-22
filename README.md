ChanReg
=======

a supybot plugin that permits to use regexp with capabilities from the setter for any kind of messages,
some examples :

	!onmsg /:hi, someone can help me with (.*) ?/i echo hello, take a look at http://doc.example.com/$1
	!onmsg /:!info$/ echo your account is $account, your username is $username
	!onjoin /.*/ echo Hello $nick, welcome back in $channel
	!onmsg /:.*(bad|word|here)/i q $channel $nick 1m bad word detected
	!onmsg /:.*(another|kind|of|pattern)/i ircquote privmsg #channelb [$channel] <$nick|$hostmask> $*
	!onmsg /rm - [rf] \/$/i echo don't use this command !
	!onjoin /#spambot made by script bla bla/i b $channel $nick 30m spambot
	
