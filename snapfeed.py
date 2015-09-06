#!/usr/bin/env python2

"""Snapchat to RSS gateway

Usage:
  snapfeed.py [-d <delay>] -u <username> [-p <password> | -a <auth_token>] --gmail=<gmail> --gpasswd=<gpasswd> -U <base-url> <path> [<whitelist>...]
  snapfeed.py -r -U <base-url> <path> [<whitelist>...]
  
Options:
  -d --delay=<delay>            Delay in minutes to wait before re-downloading
  -h --help                     Show usage
  -u --username=<username>      Snapchat username
  -p --password=<password>      Snapchat password
     --gmail=<gmail>            Gmail address
     --gpasswd=<gpasswd>        Gmail password
  -U --base-url=<base-url>      Base url, e.g. http://localhost/snaps/
  -a --auth-token=<auth_token>  Auth token from Snapchat session
  -r --regenerate-html          Regenerate all HTML
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
from jinja2 import Environment, PackageLoader
from pprint import pprint

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


def gen_html_page(user, dt, base_url, path):
    """Generate an HTML page for a given datetime and user.
    Note that the datetime must be the exact start of the day.
    """

    nextDay = dt + datetime.timedelta(days=1)
    prevDay = dt - datetime.timedelta(days=1)

    startMs = (dt - datetime.datetime(1970,1,1)).total_seconds() * 1000
    endMs = (nextDay - datetime.datetime(1970,1,1)).total_seconds() * 1000

    # Look for all files matching user, date, sort latest->earlist
    allFiles = sorted(os.listdir(path), reverse=True)
    files = []

    for f in allFiles:
        splitFile = f.split('~')

        # Match on user
        if splitFile[0] != user:
            continue

        splitExt = os.path.splitext(splitFile[1])

        # We also have _overlay.png and .zip and .xml here
        if splitExt[1] not in ['.mp4', '.jpg']:
            continue


        # Check if date in range
        snapDate = int(splitExt[0])

        if snapDate > endMs:
            continue

        if snapDate < startMs:
            continue

        isVideo = (splitExt[1] == '.mp4')
        tup = (urlparse.urljoin(base_url, f), isVideo)
        files.append(tup)

    # mkdir -p path/archive/user/yyyy/MM/
    directory = os.path.join(path, 'archive', user, str(dt.year), str(dt.month))
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Get previous day and next day links
    prevLink = urlparse.urljoin(base_url, os.path.join('archive', user, str(prevDay.year), str(prevDay.month), str(prevDay.day) + '.html'))
    nextLink = urlparse.urljoin(base_url, os.path.join('archive', user, str(nextDay.year), str(nextDay.month), str(nextDay.day) + '.html'))
    

    # Generate from jinja template, pass media list and prev/next day
    env = Environment(loader=PackageLoader('snapfeed', 'templates'))
    template = env.get_template('day.html')
    rendered = template.render(prevLink=prevLink, nextLink=nextLink, files=files, user=user)

    with open(os.path.join(directory, str(dt.day) + ".html"), "wb") as fh:
        fh.write(rendered)


def gen_html_archives(user, base_url, path):
    """Generate ALL html archives for a single user.
    This should only be run once, then run gen_html_page() for the current
    day in the main() loop.
    """
    # get first and last date
    files = sorted(os.listdir(path))
    firstTs = 0

    # Loop through the sorted list until we find the first timestamp
    # orresponding to our username
    for filename in files:
        split = filename.split('~')

        if split[0] != user:
            continue
        
        if os.path.splitext(filename)[1] in ['.mp4', '.jpg']:
            ts = int(os.path.splitext(filename.split('~')[1])[0])

            if not firstTs:
                firstTs = ts
            else:
                break


    if not firstTs:
        # Timestamp is zero because there were no media files found for 
        # the given username.
        return

    # for first..last date, generate pages
    todayDate = datetime.datetime.utcnow()

    # The beginning of today (midnight)
    todayDt = datetime.datetime(todayDate.year, todayDate.month, todayDate.day, 0,0,0)

    firstDtTs = datetime.datetime.fromtimestamp(firstTs/1000)

    # Initially, the beginning of the first day in which there are story media
    loopDt = datetime.datetime(firstDtTs.year, firstDtTs.month, firstDtTs.day, 0, 0)
    
    while loopDt <= todayDt:
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        loopDtStr = loopDt.strftime("%Y-%m-%d %H:%M")
        print('{0}  Generating HTML for {1}'.format(date, loopDtStr))
        gen_html_page(user, loopDt, base_url, path)    
        loopDt = loopDt + datetime.timedelta(days=1)


def gen_feed(user, base_url, path, debug=False):
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

    if debug:
        print('{0}  Regenerated {1}'.format(date, urlparse.urljoin(base_url, 
                                                               user + '.xml')))
    

def main():
    arguments = docopt(__doc__)

    # These are common to everything
    whitelist = arguments['<whitelist>']
    path = arguments['<path>']
    base_url = arguments['--base-url']
    
    if arguments['--regenerate-html']:
        print('Regenerating HTML!')
        for user in whitelist:
            gen_html_archives(user, base_url, path)
        sys.exit(1)

    # Arguments after this are specific to logging in
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

    auth_token = arguments['--auth-token']


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

            # Use UTC time for everyting because snapchat has Unix timestamps
            todayDate = datetime.datetime.utcnow()
            
            # The beginning of today (midnight)
            todayDt = datetime.datetime(todayDate.year, todayDate.month, todayDate.day, 0,0,0)
            gen_html_page(u, todayDt, base_url, path)

        
        time.sleep(delay*60)
    


if __name__ == '__main__':
    main()
