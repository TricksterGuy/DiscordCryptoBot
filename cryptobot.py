import argparse
import asyncio
import aiohttp
import coingecko_cog
import coingecko_helper
import datetime
import discord
import json
import logging
import sys
import traceback
import yaml


from discord.ext import commands, tasks

client = commands.Bot(
    command_prefix='/',
    description='I do crypto stuff.',
    activity=discord.Game(name='\U0001F3B7')
)

config = {}
cg = coingecko_helper.CoinGeckoAPI()

@client.event
async def on_error(event, *args, **kwargs):
    embed = discord.Embed(title=':x: Event Error', colour=0xe74c3c) #Red
    embed.add_field(name='Event', value=event)
    embed.description = '```py\n%s\n```' % traceback.format_exc()
    embed.timestamp = datetime.datetime.utcnow()
    channel_id = config.get('channels', {}).get('logging', {}).get('channel')
    if channel_id:
        channel = client.get_channel(channel_id)
    else:
        channel = bot.AppInfo.owner
    await channel.send(embed=embed)

@client.event
async def on_application_command_error(ctx, error):
    if isinstance(error, discord.ext.commands.errors.MissingPermissions):
        await ctx.send('You do not have permission to execute this command')
    elif isinstance(error, discord.ext.commands.errors.NoPrivateMessage):
        await ctx.send('This command is only to be used on servers')
    elif isinstance(error, discord.NotFound):
        print(''.join(error.args))
    else:
        try:
            embed = discord.Embed(title=':x: Event Error', colour=0xe74c3c) #Red
            embed.add_field(name='Event', value=event)
            embed.description = '```py\n%s\n```' % traceback.format_exc()
            embed.timestamp = datetime.datetime.utcnow()
            channel_id = config.get('channels', {}).get('logging', {}).get('channel')
            if channel_id:
                channel = client.get_channel(channel_id)
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
    # Updates handled in CoinGeckoCog.


def main():
    parser = argparse.ArgumentParser(description='Discord Cryptobot.')
    parser.add_argument('-c', '--config', type=str, default='cryptobot-config.yaml', help='Config file location.')
    parser.add_argument('-l', '--loglevel', default='info', help='Logging level.')

    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel.upper())
    config_file = args.config

    global config
    with open(config_file) as f:
        config = yaml.safe_load(f)

    #if 'ENABLE_LEAGUES' in config:
    #    cog = LeagueServer(bot)
    #    client.loop.create_task(cog.webserver())
    #    client.add_cog(cog)

    #if 'ENABLE_PAPER_TRADING' in config:
    #    client.add_cog(PaperTraderCog(client))

    channel_config = config.get('channels', {})
    new_crypto_config = channel_config.get('new_crypto')

    cog = coingecko_cog.CoinGeckoCog(client, cg, new_crypto_config=new_crypto_config)
    client.add_cog(cog)

    client.run(config['token'])

if __name__ == '__main__':
    main()