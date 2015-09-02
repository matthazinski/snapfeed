Snapfeed
========

A utility to generate dynamic RSS feeds from Snapchat stories. 

Installation
------------

You must have the following `python2` packages installed:

* requests
* [snapy](https://github.com/tatosaurus/snapy)
* feedgen
* docopt

Additionally, a web server is required, which is outside the scope of this
document. I like nginx.

Usage
-----

Syntax is subject to change. Run `python2 ./snapfeed.py -h` for the latest 
syntax.

``
  snapfeed.py [-d <delay>] -u <username> [-p <password>] --gmail=<gmail> --gpasswd=<gpasswd> -U <base-url> -f <feed> <path> [<whitelist>...]

Options:
  -d --delay=<delay>            Delay in minutes to wait before re-downloading
  -h --help                     Show usage
  -u --username=<username>      Snapchat username
  -p --password=<password>      Snapchat password
     --gmail=<gmail>            Gmail address
     --gpasswd=<gpasswd>        Gmail password
  -U --base-url=<base-url>      Base url, e.g. http://localhost/snaps/
  -f --feed=<feed>              Feed filename, e.g. rss.xml.
``

Note that you must provide a webserver where `<path>` is available at 
`<base-url>`. This information is used to generate RSS feeds. The feed file
itself will be written within `<path>`.

The `whitelist` parameter is used to specify zero or more usernames to filter
on. If none are specified, the feed will not be filtered at all. If one or
more are specified, then the media file corresponding to a story will be 
added to the feed if the username is in the whitelist. Regardless, the 
media will be saved in the `<path>` directory.


Warning
-------

This is mentioned in the [snapy readme](https://github.com/tatosaurus/snapy/blob/master/README.md)
but bears repeating: your Snapchat credentials are sent to a third party, 
[https://api.casper.io](Casper's API).

Also it should be noted that this currently downloads ALL friend stories you 
have access to, irrespective of the username whitelist in the command line 
options. Snap IDs are saved by the username and Unix timestamp, which are 
probably easily guessable by an adversary. This behavior will likely change in
the future when I get around to implementing a separate config file.
