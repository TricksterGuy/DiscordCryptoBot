import discord
import random

from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext, ComponentContext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.utils import manage_components
from discord_slash.model import SlashCommandOptionType, ButtonStyle
from markdownify import markdownify

GUILD_IDS = []

PRICE_CHANGE_DICT = {
    "price_change_percentage_24h": '24h',
    "price_change_percentage_7d": '7d',
    "price_change_percentage_14d": '14d',
    "price_change_percentage_30d": '30d',
    #"price_change_percentage_60d": '60d',
    #"price_change_percentage_200d": '200d',
    "price_change_percentage_1y": '1y',
}

TIMES = ['1y', '30d', '14d', '7d', '24h', '1h']

HTML_STRIP = [
'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
'p', 'br', 'ol', 'ul', 'hr', 'image', 'table', 'footer',
'header', 'html', 'href'
]


def price_str(price, max_decimals=18, target='USD'):
    format_str = f'%.{max_decimals}f'
    ret = str(price)
    if 'e' in ret:
        ret = (format_str % price).rstrip('0')
        if ret == '0.':
            ret = str(price)
    if len(ret) > 2 and ret[-2] == '.':
        ret += '0'
    return f'${ret}' if target == 'USD' else f'{ret} {target}'

def format_crypto_info(info_map):
    name = info_map.get('name')
    symbol = info_map.get('symbol', '').upper()
    id = info_map.get('id', '').lower()

    rank_n = info_map.get('market_cap_rank', None)
    rank = f' #{rank_n}' if rank_n else ''
    thumbnail = info_map.get('image', {}).get('small', '')

    description = info_map.get('description', {}).get('en')
    if not description:
        description = 'No description provided.'

    index = description.find('\r\n\r')
    description =  description[:index] if index != -1 else description
    description = markdownify(description, strip=HTML_STRIP)
    
    embed = discord.Embed(
        title=f'{name} ({symbol}){rank}',
        description=description,
        url=f'https://www.coingecko.com/en/coins/{id}')

    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    return embed

def format_crypto_price_info(info_map):
    name = info_map.get('name')
    symbol = info_map.get('symbol', '').upper()
    id = info_map.get('id', '').lower()

    rank_n = info_map.get('market_cap_rank', None)
    rank = f' #{rank_n}' if rank_n else ''
    thumbnail = info_map.get('image', {}).get('small', '')

    market_map = info_map.get('market_data', {})
    price = market_map.get('current_price', {}).get('usd', 0)
    high_24 = market_map.get('high_24h', {}).get('usd', 0)
    low_24 = market_map.get('low_24h', {}).get('usd', 0)

    price_changes = dict()
    price_changes['1h'] = market_map.get('price_change_percentage_1h_in_currency', {}).get('usd', 0)
    for pcp, key in PRICE_CHANGE_DICT.items():
        price_changes[key] = market_map.get(pcp, 0)

    embed = discord.Embed(
        title=f'{name} ({symbol}){rank}',
        url=f'https://www.coingecko.com/en/coins/{id}'
    )

    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    embed.add_field(name='Price', value=price_str(price))
    embed.add_field(name='24h High', value=price_str(high_24))
    embed.add_field(name='24h Low', value=price_str(low_24))
    
    invalid = True
    price_changes_str = dict()
    for name in TIMES:
        value = price_changes[name]
        if value == 0.0 or value == None and invalid:
            v = '---'
        else:
            v = f'{round(value, 2)}%' if value else '---'
            invalid = False
        price_changes_str[name] = v

    for name in reversed(TIMES):
        embed.add_field(name=name, value=price_changes_str[name])

    return embed    

class CoinGeckoCog(commands.Cog):
    def __init__(self, client, cg):
        self.client = client
        self.cg = cg

    @cog_ext.cog_slash(
        name="info",
        description="I will send back information about a single cryptocurrency.",
        options=[
            create_option(
                name="id",
                description="Coingecko id or symbol",
                option_type=SlashCommandOptionType.STRING,
                required=True
            ),
            create_option(
                name="is_id",
                description="Treat id as a coingecko id.",
                option_type=SlashCommandOptionType.BOOLEAN,
                required=False
            )
        ],
        guild_ids=GUILD_IDS)
    async def info(self, ctx, id, is_id=False):
        """Gets information/website for a crypto."""
        crypto = id
        if not is_id:
            crypto = self.cg.lookup(id, preferred=True)

        if not crypto:
            await ctx.send(f'Hi {ctx.author.mention}\n'
                           f'Unfortunately Coin/Token {id} doesn\'t appear to exist.')
            return

        warning = ''
        if isinstance(crypto, set):
            if len(crypto) > 1:
                id_str = '{%s}' % (', '.join(crypto))
                crypto = random.choice(list(crypto))
                warning = f'Warning multiple tokens map to this symbol.\nPicked {crypto} from {id_str}'
            else:
                crypto = next(iter(crypto))

        info = await self.cg.coin_by_id(crypto)
        website = info.get('links', {}).get('homepage', ['','',''])[0]
        embed = format_crypto_info(info)

        embed.set_footer(text=warning)
        row = []
        if website:
            buttons = [
                manage_components.create_button(
                    style=ButtonStyle.URL,
                    label='Website',
                    url=website)
            ]
            row = manage_components.create_actionrow(*buttons)
        await ctx.send(embed=embed, components=[row])
    
    @cog_ext.cog_slash(
        name="price",
        description="I will send back price info for a cryptocurrency.",
        options=[
            create_option(
                name="id",
                description="Coingecko id or symbol",
                option_type=SlashCommandOptionType.STRING,
                required=True
            ),
            create_option(
                name="is_id",
                description="Treat id as a coingecko id.",
                option_type=SlashCommandOptionType.BOOLEAN,
                required=False
            )
        ],
        guild_ids=GUILD_IDS)
    async def price(self, ctx, id, is_id=False):
        crypto = id
        if not is_id:
            crypto = self.cg.lookup(id, preferred=True)

        if not crypto:
            await ctx.send(f'Hi {ctx.author.mention}\n'
                           f'Unfortunately Coin/Token {id} doesn\'t appear to exist.')
            return

        warning = ''
        if isinstance(crypto, set):
            if len(crypto) > 1:
                id_str = '{%s}' % (', '.join(crypto))
                crypto = random.choice(list(crypto))
                warning = f'Warning multiple tokens map to this symbol.\nPicked {crypto} from {id_str}'
            else:
                crypto = next(iter(crypto))

        embed = format_crypto_price_info(await self.cg.coin_by_id(crypto))
        embed.set_footer(text=warning)
        await ctx.send(embed=embed)

    @cog_ext.cog_slash(
        name="set",
        description="I will set crypto symbol to return crypto with id.",
        options=[
            create_option(
                name="symbol",
                description="Cryptocurrency symbol",
                option_type=SlashCommandOptionType.STRING,
                required=True
            ),
            create_option(
                name="id",
                description="Coingecko id.",
                option_type=SlashCommandOptionType.STRING,
                required=True
            )
        ],
        guild_ids=GUILD_IDS)
    async def set_symbol(self, ctx, symbol: str, id: str):
        """Sets id to return for symbol."""
        symbol = symbol.upper()
        id = id.lower()

        ids = self.cg.lookup(symbol)

        if not ids or id not in ids:
            await ctx.send(f'Hi {ctx.author.mention}\n'
                           f'Unfortunately Coin/Token {symbol} doesn\'t appear to exist or {id} doesn\'t map to {symbol}')
            return

        self.cg.set_preferred(symbol, id)
        #write_symbol_override(symbol, id)

        await ctx.send(f"I've set {symbol} to specify {id}")