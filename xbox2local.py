"""
xbox2local: Downloads all Xbox screenshots and game captures from Xbox Live and
            stores copies in the specified local directory.
"""

import argparse
from datetime import datetime
import json
import os
import os.path as osp
import shutil
import subprocess as sp
import sys
from tqdm import tqdm


if __name__ == '__main__':
    # Parse command line arguments.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ids_json', default='ids.json', \
                        help='JSON file detailing your X API key and user ID')
    parser.add_argument('--local_dir', default='.', \
                        help='directory to download screenshots/game clips to')
    parser.add_argument('--media_type', default='both', \
                        choices=['screenshots', 'gameclips', 'both'], \
                        help='download screenshots, game clips, or both')
    args = parser.parse_args()

    # Other core variables.
    download_history_fname = 'download_history.json'
    num_screens = 0
    num_clips = 0

    # Load X API key and Xbox Profile User ID.
    with open(args.ids_json) as f_in:
        ids_json = json.load(f_in)
        xapi_key = ids_json['xapi_key']
        xuid = ids_json['xuid']

    # Validate the given X API key and xuid and catch Xbox Live login errors.
    output = sp.run(["curl", "-i", "-H", "X-AUTH: " + xapi_key, \
                     "https://xapi.us/v2/accountxuid"], capture_output=True)
    output = output.stdout.decode('utf-8').split('\r\n')
    http_status = output[0].split()[1]
    if http_status != '200':
        error_json = json.loads(output[-1])
        print('ERROR ' + str(error_json['error_code']) + ': ' + \
              error_json['error_message'])
        sys.exit()
    else:
        expected_xuid = str(json.loads(output[-1])['xuid'])
        assert xuid == expected_xuid, \
               "ERROR: Expected xuid " + expected_xuid + " but got " + xuid

    # Ensure that the given local directory exists, and create it if not.
    os.makedirs(args.local_dir, exist_ok=True)

    # Load download history.
    old_screen_ids = []
    old_clip_ids = []
    if osp.exists(download_history_fname):
        with open(download_history_fname) as f_in:
            download_history = json.load(f_in)
            old_screen_ids = download_history['screenshots']
            old_clip_ids = download_history['gameclips']

    # Download new screenshots.
    if args.media_type in ['both', 'screenshots']:
        tqdm.write('Downloading new screenshots...')
        screens_page = 1
        continuationToken = ''
        while True:
            # Call X API's screenshot endpoint.
            screens_endpoint = "https://xapi.us/v2/" + xuid + "/screenshots"
            if continuationToken != '':
                screens_endpoint += "?continuationToken=" + continuationToken
            output = sp.run(["curl", "-i", "-H", "X-AUTH: " + xapi_key, \
                             screens_endpoint], capture_output=True).stdout
            output = output.decode('utf-8').split('\r\n')
            # Download/move all new screenshots from this page of results.
            screens_data = json.loads(output[-1])
            for screen in tqdm(screens_data, \
                                desc='Page {}'.format(screens_page)):
                if screen['screenshotId'] not in old_screen_ids:
                    old_screen_ids.append(screen['screenshotId'])
                    num_screens += 1
                    utc = datetime.strptime(screen['dateTaken'], \
                                            "%Y-%m-%d %H:%M:%S")
                    epoch = int((utc - datetime(1970, 1, 1)).total_seconds())
                    fname = str(epoch) + ".png"
                    sp.run(["wget", "-q", "-o", "/dev/null", "-O", fname, \
                            screen['screenshotUris'][0]['uri']])
                    shutil.move(fname, osp.join(args.local_dir, fname))
            # Search for pagination in the header and stop if there is none.
            continuationToken = ''
            for line in output[0:-2]:
                if 'continuationToken' in line:
                    continuationToken = line.split()[-1]
                    screens_page += 1
                    break
            if continuationToken == '':
                break

    # Download new game clips.
    if args.media_type in ['both', 'gameclips']:
        tqdm.write('Downloading new game clips...')
        clips_page = 1
        continuationToken = ''
        while True:
            # Call X API's game clips endpoint.
            clips_endpoint = "https://xapi.us/v2/" + xuid + "/game-clips"
            if continuationToken != '':
                clips_endpoint += "?continuationToken=" + continuationToken
            output = sp.run(["curl", "-i", "-H", "X-AUTH: " + xapi_key, \
                             clips_endpoint], capture_output=True).stdout
            output = output.decode('utf-8').split('\r\n')
            # Download/move all new game clips from this page of results.
            clips_data = json.loads(output[-1])
            for clip in tqdm(clips_data, desc='Page {}'.format(clips_page)):
                if clip['gameClipId'] not in old_clip_ids:
                    old_clip_ids.append(clip['gameClipId'])
                    num_clips += 1
                    utc = datetime.strptime(clip['dateRecorded'], \
                                            "%Y-%m-%d %H:%M:%S")
                    epoch = int((utc - datetime(1970, 1, 1)).total_seconds())
                    fname = str(epoch) + ".mp4"
                    sp.run(["wget", "-q", "-o", "/dev/null", "-O", fname, \
                            clip['gameClipUris'][0]['uri']])
                    shutil.move(fname, osp.join(args.local_dir, fname))
            # Search for pagination in the header and stop if there is none.
            continuationToken = ''
            for line in output[0:-2]:
                if 'continuationToken' in line:
                    continuationToken = line.split()[-1]
                    clips_page += 1
                    break
            if continuationToken == '':
                break

    # Update the download history with IDs of all media downloaded.
    tqdm.write('Writing IDs of downloaded media to skip next time...')
    download_history = {'note' : 'These IDs have been downloaded previously', \
                        'screenshots' : old_screen_ids, \
                        'gameclips' : old_clip_ids}
    with open(download_history_fname, 'w') as f_out:
        json.dump(download_history, f_out)

    # Conclude and quit.
    if num_screens == 0 and num_clips == 0:
        tqdm.write('No new screenshots or game clips to download')
    else:
        tqdm.write('Downloaded {} screenshots and {} game clips to {}'.format( \
                   num_screens, num_clips, args.local_dir))
