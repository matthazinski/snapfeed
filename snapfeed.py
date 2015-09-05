#!/usr/bin/env python2

"""Snapchat to RSS gateway

Usage:
  snapfeed.py [-d <delay>] -u <username> [-p <password> | -a <auth_token>] --gmail=<gmail> --gpasswd=<gpasswd> -U <base-url> <path> [<whitelist>...]

Options:
  -d --delay=<delay>            Delay in minutes to wait before re-downloading
  -h --help                     Show usage
  -u --username=<username>      Snapchat username
  -p --password=<password>      Snapchat password
     --gmail=<gmail>            Gmail address
     --gpasswd=<gpasswd>        Gmail password
  -U --base-url=<base-url>      Base url, e.g. http://localhost/snaps/
  -a --auth-token=<auth_token>  Auth token from Snapchat session
"""
from __future__ import print_function
import os.path, os
import sys
import urlparse
import time, datetime

from docopt import docopt
from feedgen.feed import FeedGenerator
from snapy import get_file_extension, Snapchat
from snapy.utils import unzip_snap_mp4
from zipfile import is_zipfile
from requests.exceptions import HTTPError


def check_snaps(s, path, whitelist, base_url):
    # Download all our snaps and add items to our feed

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
        
        # in_whitelist determines whether we should publish this story
        # or just download it. In this case, chmod so nginx can read.
        in_whitelist = False

        if whitelist:
            if snap['id'].split('~')[0] in whitelist:
                in_whitelist = True
        else:
            in_whitelist = True

        with open(abspath, 'wb') as f:
            # Let webserver read it if we publish it
            if not in_whitelist:
                os.chmod(abspath, 0o600)
            else:
                os.chmod(abspath, 0o644)

            f.write(data)

            date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            print('{0}  Saved {1}'.format(date, urlparse.urljoin(base_url, 
                                                                    filename)))

        if is_zipfile(abspath):
            unzip_snap_mp4(abspath, quiet=False)


def gen_feed(user, base_url, path):
    # Create feed
    feed = FeedGenerator()
    feed.id(urlparse.urljoin(base_url, user + '.xml'))
    feed.title('Snapchat story for ' + user)
    feed.link( href=urlparse.urljoin(base_url, user + '.xml'), rel='self' )
    feed.language('en')
    feed.description('Snapchat media')


    # Iterate through files in path, sort by unix timestamp (newest first), then add to feed
    files = sorted(os.listdir(path), reverse=True)

    for filename in files:
        split = filename.split('~')

        if split[0] != user:
            continue
        
        if os.path.splitext(filename)[1] in ['.mp4', '.jpg']:
            entry = feed.add_entry()
            entry.id(urlparse.urljoin(base_url, filename))
            entry.link(href=urlparse.urljoin(base_url, filename))
            entry.title(filename)

    
    # Write feed to disk
    feed.rss_file(os.path.join(path, user + '.xml'))
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    print('{0}  Regenerated {1}'.format(date, urlparse.urljoin(base_url, 
                                                               user + '.xml')))
    

def main():
    arguments = docopt(__doc__)
    username = arguments['--username']
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
    auth_token = arguments['--auth-token']

    whitelist = arguments['<whitelist>']

    if not os.path.isdir(path):
        print('No such directory: {0}'.format(arguments['<path>']))
        sys.exit(1)
    
    s = Snapchat()

    if auth_token:
        s.restore_token(username, auth_token, gmail, gpasswd)

    else:
        if arguments['--password'] is None:
            password = getpass('Password:')
        else:
            password = arguments['--password']

        if not s.login(username, password, gmail, gpasswd)['updates_response'].get('logged'):
            print('Invalid username or password')
            sys.exit(1)

       
    # Every N minutes, fetch new snaps and generate a new feed
    while True:
        check_snaps(s, path, whitelist, base_url)

        for u in whitelist:
            gen_feed(u, base_url, path)
        
        time.sleep(delay*60)
    


if __name__ == '__main__':
    main()
