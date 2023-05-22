"""
update: Helper scripts for backwards compatible updates.
"""

from xbox2local import *


def set_accmod_datetime(username):
    """
    Updates all last access/modification times for downloaded media to those
    media's capture datetime. All media downloaded with xbox2local v2.1 or later
    will reflect this behavior automatically.

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
        accmod_dt = datetime.strptime(media.capture_dt, DT_FMT)
        os.utime(fpath + ext, (accmod_dt.timestamp(), accmod_dt.timestamp()))


if __name__ == '__main__':
    # Parse command line arguments.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-U', '--username', required=True,
                        help='The users/ subdirectory with your data')
    parser.add_argument('-F', '--function', choices=['set_accmod_datetime'],
                        help='The update function to run')
    args = parser.parse_args()

    if args.function == 'set_accmod_datetime':
        set_accmod_datetime(args.username)
