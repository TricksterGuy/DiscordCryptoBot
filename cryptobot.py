import asyncio
import aiohttp
import datetime
import discord
import json
import coingecko_cog
import coingecko_helper
import traceback

from discord.ext import commands, tasks
from discord_slash import SlashCommand, SlashCommandOptionType
from discord_slash.utils.manage_commands import create_option, create_choice


client = commands.Bot(
    command_prefix='/',
    description='I do crypto stuff.',
    activity=discord.Game(name='\U0001F3B7')
)
slash = SlashCommand(client, sync_commands=True)
config = {}

cg = coingecko_helper.CoinGeckoAPI()

@client.event
async def on_error(event, *args, **kwargs):
    embed = discord.Embed(title=':x: Event Error', colour=0xe74c3c) #Red
    embed.add_field(name='Event', value=event)
    embed.description = '```py\n%s\n```' % traceback.format_exc()
    embed.timestamp = datetime.datetime.utcnow()
    if config.get('LOGGING_CHANNEL_ID'):
        channel = client.get_channel(config.get('LOGGING_CHANNEL_ID'))
    else:
        channel = bot.AppInfo.owner
    await channel.send(embed=embed)

@client.event
async def on_slash_command_error(ctx, error):
    if isinstance(error, discord.ext.commands.errors.MissingPermissions):
        await ctx.send('You do not have permission to execute this command')
    elif isinstance(error, discord.ext.commands.errors.NoPrivateMessage):
        await ctx.send('This command is only to be used on servers')
    elif isinstance(error, discord.NotFound):
        print(''.join(error.args))
    else:
        if not ctx.responded:
            try:
                embed = discord.Embed(title=':x: Event Error', colour=0xe74c3c) #Red
                embed.add_field(name='Event', value=event)
                embed.description = '```py\n%s\n```' % traceback.format_exc()
                embed.timestamp = datetime.datetime.utcnow()
                if config.get('LOGGING_CHANNEL_ID'):
                    channel = client.get_channel(config.get('LOGGING_CHANNEL_ID'))
                else:
                    channel = bot.AppInfo.owner
                await channel.send(embed=embed)
            except:
                # well...
                pass

        raise error

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))
    # Initialize coingecko coin lists to make commands work.
    await cg.new_coins()


def main():
    global config

    with open('.env') as f:
        config = json.load(f)

    #if 'ENABLE_LEAGUES' in config:
    #    cog = LeagueServer(bot)
    #    client.loop.create_task(cog.webserver())
    #    client.add_cog(cog)

    #if 'EMABLE_PAPER_TRADING' in config:
    #    client.add_cog(PaperTraderCog(client))

    cog = coingecko_cog.CoinGeckoCog(client, cg)
    client.add_cog(cog)

    client.run(config['TOKEN'])

if __name__ == '__main__':
    main()