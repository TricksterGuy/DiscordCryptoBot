import asyncio
import discord
import datetime
import dateparser
import io
import logging
import random
import time
import uuid

import matplotlib.pyplot as plt

from discord.ext import commands, tasks
from discord.commands import Option, slash_command
from markdownify import markdownify
from PIL import ImageFont
from PIL import Image
from PIL import ImageDraw


GUILD_IDS = []

logger = logging.getLogger(__name__)

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


# TODO allow disabling sentiment bar images.
# TODO move into a class and optimize.
def create_sentiment_bar(w, h, love):
    text_size = 12
    font = ImageFont.truetype('assets/Courier-Prime.ttf', text_size)

    out = Image.new("RGBA", (w, h + 2 * text_size), (255, 255, 255, 0))
    d = ImageDraw.Draw(out)
    d.rectangle((0, text_size, w, h + text_size), fill="black")
    
    mid = round((w - 4) * love)
    if love != 0:
        d.rectangle((2, 2 + text_size, mid, h - 2 + text_size), fill="green")
    if love != 1:
        d.rectangle((mid, 2 + text_size, w - 3, h - 2 + text_size), fill="red")

    d.text((0, 1), "Good", "white", font=font)
    d.text((1, 2 + h + text_size), f"{round(love * 100)}%", "white", font=font)

    c_width = font.getsize("-")[0]
    d.text((w - c_width * 4 + 7, 1), "Bad", "white", font=font)
    hate_str = f"{round((1-love) * 100)}%"
    d.text((w - c_width * len(hate_str) - 2, 2 + h + text_size), hate_str, "white", font=font)

    arr = io.BytesIO()
    out.save(arr, format='PNG')
    arr.seek(0)

    return arr


def format_crypto_info(info_map):
    name = info_map.get('name')
    symbol = info_map.get('symbol', '').upper()
    id = info_map.get('id', '').lower()

    rank_n = info_map.get('market_cap_rank', None)
    rank = f' #{rank_n}' if rank_n else ''
    thumbnail = info_map.get('image', {}).get('small', '')

    description = info_map.get('description', {}).get('en')
    if not description or description == "\r\n":
        description = 'No description provided.'
    else:
        index = description.find('\r\n\r')
        description =  description[:index] if index != -1 else description
        description = markdownify(description, strip=HTML_STRIP)
    
    embed = discord.Embed(
        title=f'{name} ({symbol}){rank}',
        description=description,
        url=f'https://www.coingecko.com/en/coins/{id}')

    if thumbnail and thumbnail != 'missing_small.png':
        embed.set_thumbnail(url=thumbnail)

    love = info_map.get('sentiment_votes_up_percentage')
    fp = None
    if love:
        myid = uuid.uuid4()
        bio = create_sentiment_bar(160, 16, love / 100.0)
        embed.set_image(url=f"attachment://sentiment{myid}.png")
        fp = discord.File(bio, f'sentiment{myid}.png')

    return (embed, fp)


def format_crypto_price_info(info_map):
    if not info_map:
        return discord.Embed(
            title=f'Error',
            description=f'Could not get price info for coin'
        )
    
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


def fig2buf(fig):
    """Convert a Matplotlib figure to a buffer and return it"""
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    return buf


class CoinGeckoCog(commands.Cog):
    def __init__(self, client, cg, new_crypto_config=None):
        self.client = client
        self.cg = cg
        
        self.new_crypto_channel = new_crypto_config.get('channel')
        self.new_crypto_interval = new_crypto_config.get('interval', {'hours': 1})
        self.update_cryptocurrencies.start()

    async def symbol_searcher(self, ctx: discord.AutocompleteContext):
        symbols = self.cg.get_symbols()
        return [s for s in symbols if s.startswith(ctx.value.upper())]

    async def id_searcher(self, ctx: discord.AutocompleteContext):
        ids = self.cg.get_ids()
        return [s for s in ids if s.startswith(ctx.value.lower())]

    async def symbol_id_searcher(self, ctx: discord.AutocompleteContext):
        symbols = await self.symbol_searcher(ctx)
        ids = await self.id_searcher(ctx)
        all = symbols + ids
        return sorted(all)
    
    @slash_command()
    async def info(
        self,
        ctx,
        id: Option(str, 'Coingecko ID or Symbol', autocomplete=symbol_id_searcher),
        is_id: Option(bool, 'True if Coingecko ID', required=False, default=False),
    ):
        """Gets information/website for a cryptocurrency."""
        crypto = id
        if not is_id:
            crypto = self.cg.lookup(id, preferred=True)

        if not crypto:
            await ctx.respond(f'Hi {ctx.author.mention}\n'
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
        await self.do_send_info(ctx.respond, info, warning=warning)
    
    @slash_command()
    async def price(
        self,
        ctx,
        id: Option(str, 'Coingecko id or Symbol', autocomplete=symbol_id_searcher),
        is_id: Option(bool, 'True if Coingecko id', required=False, default=False),
    ):
        """Gets price information about a cryptocurrency."""
        crypto = id

        if not is_id:
            crypto = self.cg.lookup(id, preferred=True)

        if not crypto:
            await ctx.respond(f'Hi {ctx.author.mention}\n'
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
        await ctx.respond(embed=embed)

    @slash_command(name='history')
    async def price_history(
        self,
        ctx,
        id: Option(str, 'Coingecko id or Symbol', autocomplete=symbol_id_searcher),
        is_id: Option(bool, 'True if Coingecko id', required=False, default=False),
        start: Option(str, 'Start time', required=False, default='1 year ago'),
        end: Option(str, 'End time', required=False, default=None),
    ):
        """Gets price history for a cryptocurrency."""
        crypto = id

        if not is_id:
            crypto = self.cg.lookup(id, preferred=True)

        if not crypto:
            await ctx.respond(f'Hi {ctx.author.mention}\n'
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

        from_time = dateparser.parse(start)
        end_time = dateparser.parse(end) if end else datetime.datetime.now()
        
        kwargs = dict()
        kwargs['from'] = int(time.mktime(from_time.timetuple()))
        kwargs['to'] = int(time.mktime(end_time.timetuple()))
        price_data = await self.cg.coin_price_history(crypto, **kwargs)
        
        history = [price for _, price in price_data['prices']]
        times = [datetime.datetime.fromtimestamp(ts / 1000) for ts, _ in price_data['prices']]

        fig1, ax1 = plt.subplots()
        
        ax1.plot(times, history, label=crypto)
        ax1.legend(bbox_to_anchor=(1.04, 1), loc="upper left")
        fig1.tight_layout()
        fig1.autofmt_xdate()
        
        buf = fig2buf(fig1)
        plt.close(fig1)
        
        coin_info = self.cg.get_coin_info(crypto)

        embed = discord.Embed(
            title='{0} price history from {1} to {2}'.format(coin_info.name, from_time.strftime('%Y-%m-%d %H:%M:%S'), end_time.strftime('%Y-%m-%d %H:%M:%S'))
        )
        embed.set_image(url="attachment://history.png")
        embed.set_footer(text=warning)
        await ctx.respond(file=discord.File(buf, 'history.png'), embed=embed)


    @slash_command()
    async def random(self, ctx):
        """Gets information about a random cryptocurrency."""
        info = await self.cg.random_coin()
        await self.do_send_info(ctx.respond, info, warning='')

    async def do_send_info(self, func, info, warning=None):
        if not info:
            await func('Could not query info for coin')
            return

        website = info.get('links', {}).get('homepage', ['','',''])[0]
        embed, fp = format_crypto_info(info)

        if warning:
            embed.set_footer(text=warning)

        view = None
        if website:
            component = discord.ui.Button(
                    style=discord.ButtonStyle.link,
                    label='Website',
                    url=website)
            view = discord.ui.View(component, timeout=None)

        files = [fp] if fp else None
        await func(files=files, embed=embed, view=view)

    @slash_command(name='set')
    async def set_symbol(
        self,
        ctx,
        symbol: Option(str, 'Symbol for cryptocurrency', autocomplete=symbol_searcher),
        id: Option(str, 'Coingecko id', autocomplete=id_searcher),
    ):
        """Sets id to return for symbol. *NOTE* currently doesn't persist."""
        symbol = symbol.upper()
        id = id.lower()

        ids = self.cg.lookup(symbol)

        if not ids or id not in ids:
            await ctx.respond(f'Hi {ctx.author.mention}\n'
                           f'Unfortunately Coin/Token {symbol} doesn\'t appear to exist or {id} doesn\'t map to {symbol}')
            return

        self.cg.set_preferred(symbol, id)
        # TODO implement writing to database
        #write_symbol_override(symbol, id)

        await ctx.respond(f"I've set {symbol} to specify {id}")

    @tasks.loop(hours=1)
    async def update_cryptocurrencies(self):
        try:
            logger.info('Updating crypto from coingecko')
            await self.do_update_cryptocurrencies()
            logger.info('Received latest coin update from coingecko')
        except Exception as e:
            logger.exception(e)

    @update_cryptocurrencies.before_loop
    async def before_update_cryptocurrencies(self):
        await self.client.wait_until_ready()
        self.update_cryptocurrencies.change_interval(**self.new_crypto_interval)

    async def do_update_cryptocurrencies(self):
        new_coins = await self.cg.new_coins()
        if not new_coins or not self.new_crypto_channel:
            return
        channel = self.client.get_channel(self.new_crypto_channel)
        for id in new_coins:
            info = await self.cg.coin_by_id(id)
            await self.do_send_info(channel.send, info, warning='')
