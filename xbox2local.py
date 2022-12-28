"""
xbox2local: Downloads all Xbox screenshots and game captures from Xbox Live and
            stores copies in the specified local directory.
"""

import argparse
from datetime import datetime
import json
import os
import os.path as osp
from pathvalidate import sanitize_filepath, validate_filepath, ValidationError
import subprocess as sp
import sys
from tqdm import tqdm


def make_api_call(api_key, endpoint):
    """
    Makes a call to OpenXBL API using the specified API key and endpoint. If the
    request is successful, its output is returned as a dict and any
    continuation token in its header is returned as a string. If unsuccessful,
    the error code and message are displayed and the script exits.
    :param api_key: a string API key from https://xbl.io/profile
    :param endpoint: a string API endpoint from https://xbl.io/console
    :returns: a string HTTP reponse from the API call
    :returns: a string continuation token (see XAPI documentation, "Pagination")
    """
    # Make and parse the OpenXBL API call.
    output = sp.run(["curl", "-i", "-H", "X-Authorization: " + api_key, \
                     "https://xbl.io" + endpoint], capture_output=True).stdout
    output = output.decode('utf-8').split('\r\n')
    http_status = output[0].split()[1]
    http_output = json.loads(output[-1])
    if http_status != '200':
        # Report any errors and quit.
        error_msg = http_output['error'] if 'error' in http_output else '?'
        tqdm.write('ERROR ' + http_status + ': ' + error_msg)
        sys.exit()
    else:
        # Return request output and the continuation token if it exists.
        cont_token = ''
        if 'continuationToken' in http_output:
            cont_token = http_output['continuationToken']

        return http_output, cont_token


def fmt_datetime(datestr):
    """
    Reformats a date/time string so that it avoids any special characters.
    :param datestr: a string representing a date/time in 'YYYY-mm-dd HH:MM:SS'
                    or 'YYYY-mm-ddTHH:MM:SS' format
    :returns: a string representing a date/time in 'YYYY-mm-ddTHH-MM-SS' format
    """
    for fmt in ['%Y-%m-%d %H:%M:%SZ', '%Y-%m-%dT%H:%M:%SZ']:
        try:
            dt = datetime.strptime(datestr, fmt)
            return dt.strftime('%Y-%m-%dT%H-%M-%S')
        except ValueError:
            pass
    raise ValueError('No valid date format found')


def download_uri(uri, fpath):
    """
    Downloads the content at the specified URI to {path}/{fname}.
    :param uri: a string URI for the media to download
    :param fpath: a string file path to download the media to
    """
    fpath = sanitize_filepath(fpath, platform="auto")
    os.makedirs(osp.split(fpath)[0], exist_ok=True)
    sp.run(['curl', '-s', '-o', fpath, uri])


if __name__ == '__main__':
    # Parse command line arguments.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-U', '--username', required=True, \
                        help='The users/ subdirectory with your data')
    parser.add_argument('-M', '--media_type', default='both', \
                        choices=['screenshots', 'gameclips', 'both'], \
                        help='download screenshots, game clips, or both')
    args = parser.parse_args()

    # Load API key and media directory.
    with open(osp.join('users', args.username, 'config.json')) as f_in:
        config = json.load(f_in)
        api_key = config['api_key']
        try:
            validate_filepath(config['media_dir'], platform="auto")
            media_dir = config['media_dir']
        except ValidationError as e:
            tqdm.write("ERROR: media_dir path is invalid\n{}".format(e))
            sys.exit()

    # Load download history.
    history_fname = osp.join('users', args.username, 'history.json')
    if osp.exists(history_fname):
        with open(history_fname) as f_in:
            history = json.load(f_in)
    else:
        history = {'note' : 'These IDs have been downloaded previously', \
                   'screens': [], 'clips': []}

    # Scan for new screenshots.
    downloads = {'screens': [], 'clips': []}
    if args.media_type in ['both', 'screenshots']:
        tqdm.write('Scanning for new screenshots...')
        cont_token = ''
        while True:
            # Call OpenXBL API's screenshot endpoint.
            screens_endpoint = '/api/v2/dvr/screenshots'
            if cont_token != '':
                screens_endpoint += "?continuationToken=" + cont_token
            screens, cont_token = make_api_call(api_key, screens_endpoint)
            # Collect metadata for new screenshots on this page of results.
            for screen in screens['values']:
                if screen['contentId'] not in history['screens']:
                    history['screens'].append(screen['contentId'])
                    info = {'time': fmt_datetime(screen['captureDate']), \
                            'game': sanitize_filepath(screen['titleName']), \
                            'uri': screen['contentLocators'][0]['uri']}
                    downloads['screens'].append(info)
            # Break out of the while loop if all pages have been scanned.
            if cont_token == '':
                break

    # Scan for new game clips.
    if args.media_type in ['both', 'gameclips']:
        tqdm.write('Scanning for new game clips...')
        cont_token = ''
        while True:
            # Call OpenXBL API's game clips endpoint.
            clips_endpoint = '/api/v2/dvr/gameclips'
            if cont_token != '':
                clips_endpoint += "?continuationToken=" + cont_token
            clips, cont_token = make_api_call(api_key, clips_endpoint)
            # Collect metadata for new game clips on this page of results.
            for clip in clips['values']:
                if clip['contentId'] not in history['clips']:
                    history['clips'].append(clip['contentId'])
                    info = {'time': fmt_datetime(clip['contentSegments'][0]['recordDate']), \
                            'game': sanitize_filepath(clip['titleName']), \
                            'uri': clip['contentLocators'][0]['uri']}
                    downloads['clips'].append(info)
            # Break out of the while loop if all pages have been scanned.
            if cont_token == '':
                break

    # Download the new screenshots and game clips.
    if len(downloads['screens']) > 0:
        tqdm.write('Downloading new screenshots...')
        for screen in tqdm(downloads['screens']):
            fpath = osp.join(media_dir, screen['game'], screen['time'] + '.png')
            download_uri(screen['uri'], fpath)
    if len(downloads['clips']) > 0:
        tqdm.write('Downloading new game clips...')
        for clip in tqdm(downloads['clips']):
            fpath = osp.join(media_dir, clip['game'], clip['time'] + '.mp4')
            download_uri(clip['uri'], fpath)

    # Update the download history with IDs of all media downloaded.
    tqdm.write('Writing IDs of downloaded media to skip next time...')
    with open(history_fname, 'w') as f_out:
        json.dump(history, f_out)

    # Conclude and quit.
    if len(downloads['screens']) == 0 and len(downloads['clips']) == 0:
        tqdm.write('No new screenshots or game clips to download')
    else:
        tqdm.write('Downloaded {} screenshots and {} game clips to {}'.format( \
                   len(downloads['screens']), len(downloads['clips']), \
                   media_dir))
