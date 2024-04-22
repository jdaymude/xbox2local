"""
update: Helper scripts for backwards compatible updates.
"""

from xbox2local import *


def set_accmod_datetime(username):
    """
    IMPORTANT: Only run this function if updating from v2.0.0!

    Updates all last access/modification times for downloaded media to those
    media's capture datetime. All media downloaded with xbox2local v2.1.0 or
    later will do this automatically.

    :param username: a string username whose media should be updated
    """
    # Load API key and media directory.
    with open(osp.join('users', username, 'config.json')) as f_in:
        config = json.load(f_in)
        try:
            validate_filepath(config['media_dir'], platform="auto")
            media_dir = config['media_dir']
        except ValidationError as err:
            tqdm.write(f"ERROR: media_dir path is invalid\n{err}")
            sys.exit()

    # Load history of previously downloaded media.
    history_fpath = osp.join('users', username, 'history.csv')
    if osp.exists(history_fpath):
        history_df = pd.read_csv(history_fpath, index_col='id')
    else:
        tqdm.write(f"No downloaded media to update")
        sys.exit()

    # Set all media's last accessed and modified times to their capture times.
    tqdm.write('Updating downloaded media\'s last access/modify times...')
    for media in tqdm(list(history_df.itertuples())):
        fpath = osp.join(media_dir, media.game, media.capture_dt)
        ext = '.png' if media.type == 'screenshot' else '.mp4'
        accmod_dt = datetime.strptime(media.capture_dt, '%Y-%m-%dT%H-%M-%S')
        os.utime(fpath + ext, (accmod_dt.timestamp(), accmod_dt.timestamp()))


def set_timezone_awareness(username):
    """
    IMPORTANT: Only run this function if (1) you are updating from v2.1.0 or (2)
    if you are updating from v2.0.0 and have already run set_accmod_datetime!

    Updates all filenames and last access/modify times for downloaded media to
    those media's capture datetime, correctly converting from UTC to local time.
    Then updates history.json so all 'capture_dt' date/time strings are in UTC
    and all 'download_dt' date/time strings are in local time. All media
    downloaded with xbox2local v2.1.1 or later will do this automatically.

    :param username: a string username whose media should be updated
    """
    # Load API key and media directory.
    with open(osp.join('users', username, 'config.json')) as f_in:
        config = json.load(f_in)
        try:
            validate_filepath(config['media_dir'], platform="auto")
            media_dir = config['media_dir']
        except ValidationError as err:
            tqdm.write(f"ERROR: media_dir path is invalid\n{err}")
            sys.exit()

    # Load history of previously downloaded media.
    history_fpath = osp.join('users', username, 'history.csv')
    if osp.exists(history_fpath):
        history_df = pd.read_csv(history_fpath, index_col='id')
    else:
        tqdm.write(f"No downloaded media to update")
        sys.exit()

    # Correct time zones in all media's filenames and last access/modify times.
    tqdm.write('Updating downloaded media\'s last access/modify time zones...')
    for media in tqdm(list(history_df.itertuples())):
        # Locate the file.
        fpath = osp.join(media_dir, media.game, media.capture_dt)
        ext = '.png' if media.type == 'screenshot' else '.mp4'

        # Rename the file.
        cap_dt = datetime.strptime(media.capture_dt, '%Y-%m-%dT%H-%M-%S')
        cap_dt = cap_dt.replace(tzinfo=timezone.utc)
        new_fpath = osp.join(media_dir, media.game, cap_dt.strftime(DT_FMT))
        os.rename(fpath + ext, new_fpath + ext)

        # Correct the time zones in the last access/modify times.
        accmod_ts = cap_dt.astimezone().timestamp()
        os.utime(new_fpath + ext, (accmod_ts, accmod_ts))

        # Do the same for the HDR version, if it exists.
        if media.hdr_filesize > 0:
            os.rename(fpath + '_hdr.jxr', new_fpath + '_hdr.jxr')
            os.utime(new_fpath + '_hdr.jxr', (accmod_ts, accmod_ts))

    # Set all capture date/time metadata to UTC.
    tqdm.write('Updating time zones in history.json capture/download times...')
    fmt_utc = lambda x: datetime.strptime(x, '%Y-%m-%dT%H-%M-%S').replace(tzinfo=timezone.utc).strftime(DT_FMT)
    history_df.capture_dt = history_df.capture_dt.apply(fmt_utc)

    # Set all download date/time metadata to local time zone.
    fmt_loc = lambda x: datetime.strptime(x, '%Y-%m-%dT%H-%M-%S').astimezone().strftime(DT_FMT)
    history_df.download_dt = history_df.download_dt.apply(fmt_loc)

    # Save updated download history.
    tqdm.write('Writing updated history.json...')
    history_df.sort_values(by='capture_dt', ascending=False).to_csv(history_fpath)


if __name__ == '__main__':
    # Parse command line arguments.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-U', '--username', required=True,
                        help='The users/ subdirectory with your data')
    parser.add_argument('-V', '--version', required=True,
                        help='The version you are updating from')
    args = parser.parse_args()

    if args.version == '2.0.0':
        set_accmod_datetime(args.username)
        set_timezone_awareness(args.username)
    elif args.version == '2.1.0':
        set_timezone_awareness(args.username)
    else:
        tqdm.write(f"ERROR: No updates required from version {args.version}")
