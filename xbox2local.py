"""
xbox2local: Downloads all Xbox screenshots and game captures from the Xbox
            network and stores copies in the specified local directory.
"""

import argparse
from collections import namedtuple
from datetime import datetime, timezone
import json
import os
import os.path as osp
import pandas as pd
from pathvalidate import sanitize_filepath, validate_filepath, ValidationError
import subprocess as sp
import sys
from tqdm import tqdm

# Define formats and data types.
DT_FMT = '%Y-%m-%dT%H-%M-%S%z'
media_cols = ['id', 'game', 'type', 'capture_dt', 'download_dt', 'xboxnetwork',\
              'width', 'height', 'sdr_filesize', 'hdr_filesize']
Media = namedtuple('Media', media_cols + ['sdr_uri', 'hdr_uri'])


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
    output = sp.run(["curl", "-i", "-H", "X-Authorization: " + api_key,
                     "https://xbl.io" + endpoint], capture_output=True).stdout
    output = output.decode('utf-8').split('\r\n')
    http_status = output[0].split()[1]
    if http_status == '200':
        # Return request output and the continuation token if it exists.
        http_output = json.loads(output[-1])
        cont_token = ''
        if 'continuationToken' in http_output:
            cont_token = http_output['continuationToken']
    elif http_status == '202':
        # Request will be fulfilled asynchronously, so there is no output.
        http_output, cont_token = '', ''
    else:
        # Raise an error.
        http_output, error_msg = json.loads(output[-1]), ''
        if 'error' in http_output:
            error_msg = ': ' + http_output['error']
        raise ValueError('ERROR: OpenXBL endpoint \'' + endpoint + '\' ' +
                         'returned ' + http_status + error_msg)

    return http_output, cont_token


def fmt_xboxdt(datestr):
    """
    Reformats an Xbox date/time string so that it avoids any special characters.

    :param datestr: a string representing a date/time in 'YYYY-mm-dd HH:MM:SSZ',
                    'YYYY-mm-ddTHH:MM:SSZ', or 'YYYY-mm-ddTHH:MM:SS.fffZ' format
    :returns: a string representing a date/time in 'YYYY-mm-ddTHH-MM-SS' format
    """
    for fmt in ['%Y-%m-%d %H:%M:%SZ', '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%dT%H:%M:%S.%fZ']:
        try:
            dt = datetime.strptime(datestr, fmt)  # Parse date/time string.
            dt = dt.replace(tzinfo=timezone.utc)  # Mark this date/time in UTC.
            return dt.strftime(DT_FMT)  # Return formatted date/time string.
        except ValueError:
            pass
    raise ValueError('ERROR: No valid date format for \'' + datestr + '\'')


def fmt_sizeof(num, suffix="B"):
    """
    Formats a number in a human-readable order of magnitude using base-1024.

    :param num: an int or float number
    :param suffix: an optional string suffix; by default "B" for bytes
    :returns: a formatted string representation of the input number
    """
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0

    return f"{num:.1f}Yi{suffix}"


def download_uri(uri, fpath, accmod_dt):
    """
    Downloads the content at the specified URI to {path}/{fname} and then set
    the last accessed and modified times to the specified datetime.

    :param uri: a string URI for the media to download
    :param fpath: a string file path to download the media to
    :param accmod_dt: a datetime object for the file's last access/modify time
    """
    fpath = sanitize_filepath(fpath, platform="auto")
    os.makedirs(osp.split(fpath)[0], exist_ok=True)
    sp.run(['curl', '-s', '-o', fpath, uri])
    os.utime(fpath, (accmod_dt.timestamp(), accmod_dt.timestamp()))


if __name__ == '__main__':
    # Parse command line arguments.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-U', '--username', required=True,
                        help='The users/ subdirectory with your data')
    args = parser.parse_args()

    # Load API key and media directory.
    with open(osp.join('users', args.username, 'config.json')) as f_in:
        config = json.load(f_in)
        api_key = config['api_key']
        exp_days = config['gameclip_expiration_days']
        try:
            validate_filepath(config['media_dir'], platform="auto")
            media_dir = config['media_dir']
        except ValidationError as err:
            tqdm.write(f"ERROR: media_dir path is invalid\n{err}")
            sys.exit()

    # Load history of previously downloaded media.
    history_fpath = osp.join('users', args.username, 'history.csv')
    if osp.exists(history_fpath):
        history_df = pd.read_csv(history_fpath, index_col='id')
    else:
        history_df = pd.DataFrame(columns=media_cols).set_index('id')

    # Scan the Xbox network for all screenshots.
    xnet_media = []
    tqdm.write('Scanning the Xbox network for screenshots...')
    cont_token = ''
    while True:
        # Call OpenXBL API's screenshots endpoint.
        screens_endpoint = '/api/v2/dvr/screenshots'
        if cont_token != '':
            screens_endpoint += "?continuationToken=" + cont_token
        screens, cont_token = make_api_call(api_key, screens_endpoint)
        # Collect metadata for all screenshots on this page of results.
        for screen in screens['values']:
            # Detect SDR and HDR screenshots.
            sdr_uri, sdr_filesize, hdr_uri, hdr_filesize = '', 0, '', 0
            for cl in screen['contentLocators']:
                if cl['locatorType'] == 'Download':
                    sdr_uri, sdr_filesize = cl['uri'], cl['fileSize']
                elif cl['locatorType'] == 'Download_HDR':
                    hdr_uri, hdr_filesize = cl['uri'], cl['fileSize']
            # Add screenshot to the list of media.
            xnet_media.append(Media(
                id=screen['contentId'],
                game=sanitize_filepath(screen['titleName']),
                type='screenshot',
                capture_dt=fmt_xboxdt(screen['captureDate']),
                download_dt='',
                xboxnetwork=True,
                width=screen.get('resolutionWidth'),
                height=screen.get('resolutionHeight'),
                sdr_filesize=sdr_filesize, hdr_filesize=hdr_filesize,
                sdr_uri=sdr_uri, hdr_uri=hdr_uri))
        # Break out of the while loop if all pages have been scanned.
        if cont_token == '':
            break

    # Scan the Xbox network for all game clips.
    tqdm.write('Scanning the Xbox network for game clips...')
    cont_token = ''
    while True:
        # Call OpenXBL API's game clips endpoint.
        clips_endpoint = '/api/v2/dvr/gameclips'
        if cont_token != '':
            clips_endpoint += "?continuationToken=" + cont_token
        clips, cont_token = make_api_call(api_key, clips_endpoint)
        # Collect metadata for all game clips on this page of results.
        for clip in clips['values']:
            # Detect SDR game clip (Xbox doesn't record HDR game clips).
            sdr_uri, sdr_filesize = '', 0
            for cl in clip['contentLocators']:
                if cl['locatorType'] == 'Download':
                    sdr_uri, sdr_filesize = cl['uri'], cl['fileSize']
                    break
            # Add game clip to the list of media.
            xnet_media.append(Media(
                id=clip['contentId'],
                game=sanitize_filepath(clip['titleName']),
                type='gameclip',
                capture_dt=fmt_xboxdt(clip['contentSegments'][0]['recordDate']),
                download_dt='',
                xboxnetwork=True,
                width=clip.get('resolutionWidth'),
                height=clip.get('resolutionHeight'),
                sdr_filesize=sdr_filesize, hdr_filesize=0,
                sdr_uri=sdr_uri, hdr_uri=''))
        # Break out of the while loop if all pages have been scanned.
        if cont_token == '':
            break

    # Collect media scanned from the Xbox network, identify new media to
    # download, and identify previously downloaded media that are no longer on
    # the Xbox network.
    xnet_df = pd.DataFrame(xnet_media).set_index('id')
    dl_df = xnet_df.loc[~xnet_df.index.isin(history_df.index)]
    history_df.loc[~history_df.index.isin(xnet_df.index), 'xboxnetwork'] = False

    # Download new game media from the Xbox network.
    if len(dl_df) > 0:
        tqdm.write('Downloading new media...')
        for media in tqdm(list(dl_df.itertuples())):
            # Setup file path and download the SDR version.
            fpath = osp.join(media_dir, media.game, media.capture_dt)
            ext = '.png' if media.type == 'screenshot' else '.mp4'
            accmod_dt = datetime.strptime(media.capture_dt, DT_FMT).astimezone()
            download_uri(media.sdr_uri, fpath + ext, accmod_dt)
            # If there is an HDR version, download that too.
            if media.hdr_uri != '':
                download_uri(media.hdr_uri, fpath + '_hdr.jxr', accmod_dt)
            # Timestamp the download.
            dl_df.loc[media.Index, 'download_dt'] = datetime.now().astimezone().strftime(DT_FMT)
        # Update the download history with the new media metadata.
        history_df = pd.concat([history_df,
                                dl_df.drop(columns=['sdr_uri', 'hdr_uri'])])
        # Report final download status.
        screen_sdr_dls = len(dl_df[dl_df.type == 'screenshot'])
        screen_hdr_dls = len(dl_df[(dl_df.type == 'screenshot') &
                                   (dl_df.hdr_uri != '')])
        clip_dls = len(dl_df[dl_df.type == 'gameclip'])
        tqdm.write(f"Downloaded {screen_sdr_dls} screenshots " +
                   f"({screen_hdr_dls} HDR) and {clip_dls} game clips to " +
                   media_dir)
    else:
        tqdm.write('No new screenshots or game clips to download')

    # Report current Xbox network storage usage.
    screen_storage = xnet_df[xnet_df.type == 'screenshot']['sdr_filesize'].sum()
    clip_storage = xnet_df[xnet_df.type == 'gameclip']['sdr_filesize'].sum()
    percent_usage = (screen_storage + clip_storage) / (10 * 1024**3) * 100
    tqdm.write('You are using ' + fmt_sizeof(screen_storage + clip_storage) +
               f"/10GiB ({percent_usage:3.1f}%) of your Xbox network storage:" +
               '\n  Screenshots: ' + fmt_sizeof(screen_storage) +
               '\n  Game Clips:  ' + fmt_sizeof(clip_storage))

    # Detect expired game clips on the Xbox network and optionally delete them.
    expclips_df = xnet_df[(xnet_df.type == 'gameclip') &
        (xnet_df.capture_dt.apply(lambda x:
            (datetime.now().astimezone() - datetime.strptime(x, DT_FMT)).days
            > exp_days))]
    if len(expclips_df) > 0:
        tqdm.write(f"The Xbox network is storing {len(expclips_df)} game clips"+
                   ' (' + fmt_sizeof(expclips_df['sdr_filesize'].sum()) + ') ' +
                   f"that are >{exp_days} days old.")
        delete_yn = ''
        while delete_yn not in ['Y', 'n']:
            delete_yn = input('Delete expired game clips from the Xbox network?'
                              + ' [Y/n]\n>>> ')
        if delete_yn == 'Y':
            delete_yn = ''
            while delete_yn not in ['Y', 'n']:
                delete_yn = input('Are you sure? This can\'t be undone. [Y/n]' +
                                  '\n>>> ')
            if delete_yn == 'Y':
                tqdm.write('Deleting expired game clips...')
                for clipid in tqdm(expclips_df.index):
                    delete_endpoint = '/api/v2/dvr/gameclips/delete/'
                    try:
                        _, _ = make_api_call(api_key, delete_endpoint + clipid)
                        history_df.loc[clipid, 'xboxnetwork'] = False
                    except ValueError as err:
                        # This error likely means we hit the request limit and
                        # should quit gracefully, recording any deletions we
                        # succeeded in so far.
                        tqdm.write(err)
                        break

    # Save updated download history.
    tqdm.write('Writing metadata of downloaded media to skip next time...')
    history_df.sort_values(by='capture_dt', ascending=False).to_csv(history_fpath)
