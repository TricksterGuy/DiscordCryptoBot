import json

import discord
from discord.ext import commands, tasks
from discord_slash import SlashCommand
from discord_slash.utils.manage_commands import create_option, create_choice


client = commands.Bot(
    command_prefix='/',
    description='I do crypto stuff.',
    activity=discord.Game(name='\U0001F3B7')
)
slash = SlashCommand(client, sync_commands=True)


@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))


def main():
    with open('.env') as f:
        config = json.load(f)
    
    client.run(config['TOKEN'])

if __name__ == '__main__':
    main()