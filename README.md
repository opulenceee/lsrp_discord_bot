# LSRP Discord Bot

## **This bot is provided as-is; you'll need to modify the code to fit your environment. No support will be provided.**

This bot tracks logged-in players, shows online admins and testers, and allows status checks via Discord commands. It’s recommended to use a VPS (I use Hetzner) that can run 24/7. This should work on Debian or any Linux distribution.

Create a Python virtual environment using [this guide](https://www.freecodecamp.org/news/how-to-setup-virtual-environments-in-python/)

Install dependencies with:

```bash
pip install -r /path/to/requirements.txt
```

Next, configure your `.env` file with your bot token and credentials. Here’s an example of what the `.env` file should contain:

```env
DISCORD_TOKEN=your_discord_bot_token
API_URL=https://example.com/api
DATABASE_URL=postgres://user:password@localhost/dbname
```

To register a Discord bot and invite it to your server, search for a guide online.

---

## Feel free to fork the project if you want to contribute or make changes.
