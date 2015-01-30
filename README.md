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
    
This fork was created to accommodate the following use case:

- Channel #foo has a quiet set on unregistered users.
- Those users cannot speak and may be confused about why that is
- We would like an automated means of targeting those users, and informing them of how to register
  their nick.

The change made to plugin.py facilitates that change. 

Example:
    !onjoin /  \*$/ ircquote privmsg $nick :Welcome to #foo- Please register your nick to speak: https://freenode.net/faq.shtml#nicksetup
	
