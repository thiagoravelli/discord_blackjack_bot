# Discord Blackjack Bot

Discord Blackjack Bot is an asynchronous Discord bot built with Python that lets users play a game of Blackjack directly in their Discord server. The bot supports multi-player tables with betting, player turns (hit/stand), dealer actions, and automated round management. It uses an SQLite database to store user data (such as chip balance, daily rewards, and inactivity tracking) and leverages asynchronous programming via discord.py to handle game state transitions smoothly. The bot also utilizes a .env file to securely manage the bot token.

Setup and Installation
Prerequisites

Python 3.8 or higher: Ensure you have Python installed. You can download it from python.org.
Pip: Python’s package installer should be available.
Discord

Installation Steps      

Clone the Repository:

  git clone https://github.com/yourusername/discord-blackjack-bot.git
  cd discord-blackjack-bot

Create a Virtual Environment (Optional but Recommended):

  python -m venv venv
  source venv/bin/activate  # On Windows use: venv\Scripts\activate

Install Dependencies:

  pip install -r requirements.txt

Create a Discord Bot

Visit Discord Developer Portal and log in with your Discord account.

Create a New Application:
Click the "New Application" button.
Enter a name for your bot (e.g., "Blackjack Bot") and click "Create".

Copy the Bot Token:

In your application’s dashboard, navigate to the "Bot" tab on the left sidebar.
Under the "TOKEN" section, click "Reset Token" then "Copy". This token is your bot’s key to connecting to Discord.
Important: Do not share this token with anyone. You will store it in a .env file for security.

Create a .env File:

In the root directory of the project, create a file named .env and add your Discord bot token:

  DISCORD_BOT_TOKEN=YOUR_DISCORD_BOT_TOKEN

Replace YOUR_DISCORD_BOT_TOKEN with the actual token from the Discord Developer Portal.

Invite Your Bot to Your Server:

In your application’s dashboard, navigate to the "General Informations" tab on the left sidebar.
Copy the Application's Id
Paste the following URL into your browser, replacing YOUR_CLIENT_ID with your Application's Id
  https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=8&scope=bot%20applications.commands
Select the server you want to add your bot to (you must have the necessary permissions in that server).
Click "Authorize" and complete any required CAPTCHA challenge.

Run the Bot:

Start the bot by running:

  python bot.py

You should see a message in the console indicating that the bot has connected to Discord.