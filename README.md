
In the browser where you're signed into your gmail, visit [the gmail api quickstart guide for python](https://developers.google.com/gmail/api/quickstart/python).

Under Step 1 of that guide, there is a bright blue button titled "Enable the Gmail API".
Click that button and follow the prompts (you'll have to pick a name for the project, but we won't be using the name).
It will also display authentication tokens, offer to let you download them.  No need to do this.

## Install

```sh
git clone git@github.com:cfmeyers/gmail-api.git
python3 -m venv venv
source venv/bin/activate
mkdir data

pip install -r requirements.txt

```

The first time you run `gmail.py`, you should be redirected to your browser where you'll be prompted to authorize this app.  Do that.
You should only have to do that once (after you do that, it will save your credentials in `token.pickle`).


Running `python gmail.py` will grab the last 2 days worth of emails and download their attachments in the data directory.
You can run it as many times as you like; it will not duplicate the files.
A list of the emails it's already searched is available at "already_visited.csv"


Note that `get_emails()` takes an optional `query` parameter that lets you filter by a gmail query.
See [these docs](https://support.google.com/mail/answer/7190?hl=en) for example queries (we're using "newer_than:2d" for filtering just the last 2 days, but you could use "from:example@example.com" or "subject:dinner tonight", etc)
