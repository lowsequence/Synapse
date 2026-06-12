# SynapseBot

SynapseBot is a multi-purpose Discord bot built using `discord.py`. It offers a wide range of features designed to manage, entertain, and secure your Discord servers.

## Features

- **Antinuke & Security**: Protect your server from malicious activities and unauthorized changes.
- **Moderation**: Essential tools for server administrators and moderators (kick, ban, mute, etc.).
- **Automod**: Automated moderation to keep chat clean and safe.
- **Economy**: A fun and engaging virtual economy system.
- **Games**: Interactive mini-games (including chess) to play with friends.
- **Utility & Admin**: Various utility commands and server administration tools.
- **Role Management**: Efficient tools for handling and assigning roles.
- **Social & Engagement**: Commands to boost server activity and user engagement.
- **Automation**: Setup automated tasks and routines for your server.

## Prerequisites

- Python 3.10+
- [Git](https://git-scm.com/)

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/lowsequence/Synapse.git
   cd Synapse
   ```

2. **Install dependencies:**
   Make sure you have your virtual environment activated, then run:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configuration:**
   Ensure you have a `info.json` file with the following variables:
   - `TOKEN` : Your Discord Bot Token
   - `whCL` : Webhook URL (if used)
   *Note: Other configuration for Lavalink or Database might be required depending on your setup.*

4. **Run the bot:**
   ```bash
   python app.py
   ```

## Technologies Used

- [discord.py](https://github.com/Rapptz/discord.py) - API Wrapper
- [aiosqlite](https://github.com/omnilib/aiosqlite) - Asynchronous SQLite
- [Jishaku](https://github.com/Gorialis/jishaku) - Debugging and cog management

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
