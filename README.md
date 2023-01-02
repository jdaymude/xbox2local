# xbox2local

Welcome to **xbox2local**, a command line utility written in Python for downloading all your Xbox [screenshots and game clips](https://support.xbox.com/help/friends-social-activity/share-socialize/capture-game-clips-and-screenshots) to your computer.
As of this writing, Microsoft only allows automatic uploads of screenshots and game clips to the Xbox network, where [subtle rules](https://support.xbox.com/help/games-apps/my-games-apps/manage-clips-with-upload-studio) dictate how long your content sticks around.

The goal of **xbox2local** is to make the process of saving your screenshots and game clips much faster.
Each time you run it, it (1) detects all your media on the Xbox network that it hasn't saved before, (2) copies them to a local folder of your choosing, and (3) gives you the option of deleting them from the Xbox network to free up storage.


## A Note on the Xbox November 2022 Update

As of the [Xbox November 2022 Update](https://news.xbox.com/en-us/2022/11/16/xbox-november-2022-update-rolls-out-today/), Team Xbox has finally provided official support for bulk media backups to OneDrive or external storage in addition to the older clip-by-clip [sharing options](https://support.xbox.com/help/games-apps/my-games-apps/share-clips-xbox-one).
On your Xbox, navigate to *Captures > Manage > Select all > Upload to OneDrive* or *Copy to external storage*.
For many users, this functionality can (and should!) replace the functionality of the **xbox2local** script.
For power users, **xbox2local** still offers the following benefits over the native Xbox functionality:

- Game media can be downloaded to any local folder, independent of OneDrive storage limits and without manually transferring an external drive.
- Downloaded media are automatically organized by game and capture date, whereas Xbox only differentiates screenshots (`OneDrive/Pictures/Xbox Screenshots`) and game clips (`OneDrive/Videos/Xbox Game DVR`).
- Metadata for all downloaded game media are stored locally.

However, using **xbox2local** has the following drawbacks:

- Installation requires some technical knowledge (installing python, packages, etc.).
- Dependence on the [OpenXBL](https://xbl.io/) API means that: (1) underlying changes to the API can break existing functionality, (2) adding new functionality depends on upstream API updates, and (3) request limits apply; see Issue [#3](https://github.com/jdaymude/xbox2local/issues/3).


## Getting Started

1. You'll need a command line (Unix-based, Windows Command Prompt, or macOS Terminal) and any [Python](https://www.python.org/downloads/) installation version 3.6 or newer. You will also need the [pandas](https://pandas.pydata.org/), [tqdm](https://github.com/tqdm/tqdm#installation), and [pathvalidate](https://github.com/thombashi/pathvalidate#installation) packages.

2. Have your Xbox Live (Microsoft) account email and password on hand. Both Free and Gold accounts are supported.

3. Navigate to [OpenXBL](https://xbl.io/), the API that **xbox2local** uses to interface with the Xbox network to download your media. Log in using your Microsoft account.

4. On your OpenXBL [profile page](https://xbl.io/profile), scroll down to the box labeled "API KEYS" and press the "Create +" button. Copy the newly created API key (a string of letters, numbers, and hyphens) before navigating away from the page.

5. Clone this repository or download the latest [release](https://github.com/jdaymude/xbox2local/releases). Your directory structure will look like:
```
xbox2local
|--- users
|   |--- example_user
|   |   |--- config.json
|--- ...
|--- xbox2local.py
```

6. Rename the `users/example_user` directory to `users/<your username>`. (If you need to download game media for multiple users, make multiple copies of this `users/example_user` directory.)

7. Update the contents of your `config.json` file with the following contents:
    - Copy the *API Key* from your OpenXBL API [profile page](https://xbl.io/profile) into the `api_key` field.
    - Set the `media_dir` field to the local directory to download screenshots and game clips to (e.g., your OneDrive folder).
    - Update the `gameclip_expiration_days` field if desired. This value controls the age of game clips that **xbox2local** will suggest deleting from the Xbox network to free up storage. By default, this is set to 365 days.

8. Run **xbox2local** with `python xbox2local.py --username <your username>`.


## Usage

**xbox2local** provides the following command line arguments:

- `--username <USERNAME>` allows you to specify an alternative user to load your config file (containing your OpenXBL API key and media directory), which is potentially useful if you have multiple accounts.

After running **xbox2local** at least once in which it succeeds in downloading your media, a `history.csv` file will be created in your `users/<your username>` directory.
This file stores the metadata of every screenshot and game clip that **xbox2local** has previously downloaded so that, on subsequent runs, it does not download duplicates.
If for whatever reason you want to start fresh and redownload all media currently stored on the Xbox network, simply delete/move this file.


## Troubleshooting

**xbox2local** does its best to notify you if anything goes wrong when communicating with the OpenXBL API or your Xbox account.
Some common errors include:

#### ERROR 401: X-Authorization header misssing or Invalid API Key

This means that either you did not provide your OpenXBL API key in `config.json` or the API key you provided is invalid.

#### ERROR 403: API Rate Limit Exceeded

This means that you have made more calls to OpenXBL API than your subscription plan allows.
TL;DR: this limit can be violated if you have a huge number of screenshots and game clips.
As of this writing, the free tier allows 150 requests per hour and there are larger quotas available via paid subscriptions.
You can track your usage in real time on your OpenXBL [profile page](https://xbl.io/profile).

In detail, **xbox2local** makes the following calls to OpenXBL API each time it's run:
- One call to the `/api/v2/dvr/screenshots` endpoint per page of screenshot results (OpenXBL uses pagination to ensure that no single request is too big).
- One call to the `/api/v2/dvr/gameclips` endpoint per page of game clip results.
- One call to the `/api/v2/dvr/gameclips/delete` endpoint per deleted game clip.

See Issue [#3](https://github.com/jdaymude/xbox2local/issues/3) for further discussion.

#### ERROR: media_dir path is invalid

This means that the `media_dir` path you provided in `config.json` is not valid for your platform (Linux, Windows, or macOS).
The pathvalidate [validate_filepath()](https://pathvalidate.readthedocs.io/en/latest/pages/examples/validate.html#validate-a-file-path) function will print a more detailed error message.
Note: because sanitization rules differ slightly between platforms, running **xbox2local** with multiple command lines for the same media library may create different, similarly-named subfolders for the same game.

#### No new screenshots or game clips to download

This message is expected behavior when there really isn't anything new to download.
However, if you receive this message unexpectedly, check your *Settings > Preferences > Capture & share > Automatically upload* settings on your Xbox.
This should be set to something other than *Don't upload*; otherwise, all screenshots and game clips you capture stay on your Xbox's local storage and are not uploaded to the Xbox network, so **xbox2local** cannot access them.


## Upgrading from Prior Versions

Updating an older version of **xbox2local** to a [new release](https://github.com/jdaymude/xbox2local/releases) requires a basic understanding of [semantic versioning](https://semver.org/), where version numbers are written as `MAJOR.MINOR.PATCH`.
If your older version and the updated version have the same `MAJOR` number, you can replace your `xbox2local.py` file with the [newest version](https://github.com/jdaymude/xbox2local/blob/master/xbox2local.py) and things should just work.
If you are updating to a new `MAJOR` version (e.g., from `v1.#.#` to `v2.#.#`), there may be additional changes you need to make manually.
The release notes for the corresponding major update (e.g., `v2.0.0`) will have instructions for those changes, if applicable.


## Contributing

If you'd like to leave feedback, feel free to open a [new issue](https://github.com/jdaymude/xbox2local/issues/new/choose).
If you'd like to contribute, please submit your code via a [pull request](https://github.com/jdaymude/xbox2local/pulls).
