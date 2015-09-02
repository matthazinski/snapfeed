#!/usr/bin/env python2

"""Snapchat to RSS gateway

Usage:
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

"""
from __future__ import print_function
import os.path
import sys
import urlparse
import time

from docopt import docopt
from feedgen.feed import FeedGenerator
from snapy import get_file_extension, Snapchat
from snapy.utils import unzip_snap_mp4
from zipfile import is_zipfile
from requests.exceptions import HTTPError


def check_snaps(username, password, gmail, gpasswd, path, feed, base_url, whitelist):
    # Download all our snaps and add items to our feed
    s = Snapchat()
    try:
        if not s.login(username, password, gmail, gpasswd)['updates_response'].get('logged'):
            print('Invalid username or password')
            return

        for snap in s.get_friend_stories():
            filename = '{0}.{1}'.format(snap['id'],
                                        get_file_extension(snap['media_type']))
            abspath = os.path.abspath(os.path.join(path, filename))

            if os.path.isfile(abspath):
                continue

            data = s.get_story_blob(snap['media_id'],
                                    snap['media_key'],
                                    snap['media_iv'])
            if data is None:
                continue

            with open(abspath, 'wb') as f:
                f.write(data)
                print('Saved: {0}'.format(abspath))

            if is_zipfile(abspath):
                unzip_snap_mp4(abspath, quiet=False)

            if whitelist:
                if snap['id'].split('~')[0] in whitelist:
                    entry = feed.add_entry()
                    entry.id(urlparse.urljoin(base_url, filename))
                    entry.link(href=urlparse.urljoin(base_url, filename))
                    entry.title(filename)

            else:
                entry = feed.add_entry()
                entry.id(urlparse.urljoin(base_url, filename))
                entry.link(href=urlparse.urljoin(base_url, filename))
                entry.title(filename)


    except HTTPError:
        print('Casper auth server is presumably overloaded right now.')
        return


def main():
    arguments = docopt(__doc__)
    username = arguments['--username']
    if arguments['--password'] is None:
        password = getpass('Password:')
    else:
        password = arguments['--password']
    gmail = arguments['--gmail']

    if arguments['--gpasswd'] is None:
        gpasswd = getpass('Gmail password:')
    else:
        gpasswd = arguments['--gpasswd']


    if arguments['--delay'] is None:
        delay = 60
    else:
        delay = int(arguments['--delay'])

    path = arguments['<path>']
    base_url = arguments['--base-url']
    feed_filename = arguments['--feed']
    whitelist = arguments['<whitelist>']

    if not os.path.isdir(path):
        print('No such directory: {0}'.format(arguments['<path>']))
        sys.exit(1)

    # Create feed
    feed = FeedGenerator()
    feed.id(urlparse.urljoin(base_url, feed_filename))
    feed.title('Snapchat')
    feed.link( href=urlparse.urljoin(base_url, feed_filename), rel='self' )
    feed.language('en')
    feed.description('Snapchat media')
    rss = feed.rss_str(pretty=True)
    print(rss) 

       
    # Every N minutes, fetch new snaps and generate a new feed
    while True:
        check_snaps(username, password, gmail, gpasswd, path, feed, base_url, whitelist)
        rss = feed.rss_str(pretty=True)
        print(rss)
        feed.rss_file(os.path.join(path, feed_filename))
        time.sleep(delay*60)
    


if __name__ == '__main__':
    main()
