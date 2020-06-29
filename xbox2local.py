"""
xbox2local: Downloads all Xbox screenshots and game captures from Xbox Live and
            stores copies in the specified local directory.
"""

import argparse
from datetime import datetime
import json
import os
import os.path as osp
import subprocess as sp
import sys
from tqdm import tqdm


def make_xapi_call(xapi_key, endpoint):
    """
    Makes a call to X API using the specified X API key and endpoint. If the
    request is successful, its output is returned as a dict and any
    continuation token in its header is returned as a string. If unsuccessful,
    the error code and message are displayed and the script exits.
    """
    # Make the X API call.
    output = sp.run(["curl", "-i", "-H", "X-AUTH: " + xapi_key, \
                     "https://xapi.us" + endpoint], capture_output=True).stdout
    output = output.decode('utf-8').split('\r\n')
    http_status = output[0].split()[1]
    http_output = json.loads(output[-1])
    if http_status != '200':
        # Report any errors and quit.
        tqdm.write('ERROR ' + http_status + ': ' + http_output['error_message'])
        sys.exit()
    else:
        # Search for continuation token.
        cont_token = ''
        for line in output[0:-2]:
            if 'continuationToken' in line:
                cont_token = line.split()[-1]
                break
        # Return request output and the continuation token.
        return http_output, cont_token


def download_uri(uri, path, fname):
    """
    Downloads the content at the specified URI to {path}/{fname}.
    """
    os.makedirs(path, exist_ok=True)
    sp.run(['curl', '-s', '-o', osp.join(path, fname), uri])


if __name__ == '__main__':
    # Parse command line arguments.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='config.json', \
                        help='JSON file with your X API key and media folder')
    parser.add_argument('--media_type', default='both', \
                        choices=['screenshots', 'gameclips', 'both'], \
                        help='download screenshots, game clips, or both')
    args = parser.parse_args()

    # Other core variables.
    history_fname = 'history.json'
    history = {'note' : 'These IDs have been downloaded previously', \
               'screens': [], 'clips': []}
    downloads = {'screens': [], 'clips': []}

    # Load X API key, Xbox Profile User ID (xuid), and media directory.
    with open(args.config) as f_in:
        config = json.load(f_in)
        xapi_key = config['xapi_key']
        xuid = str(make_xapi_call(xapi_key, '/v2/accountxuid')[0]['xuid'])
        media_dir = config['media_dir']

    # Load download history.
    if osp.exists(history_fname):
        with open(history_fname) as f_in:
            history = json.load(f_in)

    # Scan for new screenshots.
    if args.media_type in ['both', 'screenshots']:
        tqdm.write('Scanning for new screenshots...')
        cont_token = ''
        while True:
            # Call X API's screenshot endpoint.
            screens_endpoint = '/v2/' + xuid + '/screenshots'
            if cont_token != '':
                screens_endpoint += "?continuationToken=" + cont_token
            screens, cont_token = make_xapi_call(xapi_key, screens_endpoint)
            # Collect metadata for new screenshots on this page of results.
            for screen in screens:
                if screen['screenshotId'] not in history['screens']:
                    history['screens'].append(screen['screenshotId'])
                    utc = datetime.strptime(screen['dateTaken'], \
                                            "%Y-%m-%d %H:%M:%S")
                    epoch = int((utc - datetime(1970, 1, 1)).total_seconds())
                    screen_info = {'time': str(epoch), \
                                   'game': screen['titleName'], \
                                   'uri': screen['screenshotUris'][0]['uri']}
                    downloads['screens'].append(screen_info)
            # Break out of the while loop if all pages have been scanned.
            if cont_token == '':
                break

    # Scan for new game clips.
    if args.media_type in ['both', 'gameclips']:
        tqdm.write('Scanning for new game clips...')
        cont_token = ''
        while True:
            # Call X API's game clips endpoint.
            clips_endpoint = '/v2/' + xuid + '/game-clips'
            if cont_token != '':
                clips_endpoint += "?continuationToken=" + cont_token
            clips, cont_token = make_xapi_call(xapi_key, clips_endpoint)
            # Collect metadata for new game clips on this page of results.
            for clip in clips:
                if clip['gameClipId'] not in history['clips']:
                    history['clips'].append(clip['gameClipId'])
                    utc = datetime.strptime(clip['dateRecorded'], \
                                            "%Y-%m-%d %H:%M:%S")
                    epoch = int((utc - datetime(1970, 1, 1)).total_seconds())
                    clip_info = {'time': str(epoch), \
                                 'game': clip['titleName'], \
                                 'uri': clip['gameClipUris'][0]['uri']}
                    downloads['clips'].append(clip_info)
            # Break out of the while loop if all pages have been scanned.
            if cont_token == '':
                break

    # Download the new screenshots and game clips.
    if len(downloads['screens']) > 0:
        tqdm.write('Downloading new screenshots...')
        for screen in tqdm(downloads['screens']):
            path = osp.join(media_dir, screen['game'])
            fname = screen['time'] + '.png'
            download_uri(screen['uri'], path, fname)
    if len(downloads['clips']) > 0:
        tqdm.write('Downloading new game clips...')
        for clip in tqdm(downloads['clips']):
            path = osp.join(media_dir, clip['game'])
            fname = clip['time'] + '.mp4'
            download_uri(clip['uri'], path, fname)

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
