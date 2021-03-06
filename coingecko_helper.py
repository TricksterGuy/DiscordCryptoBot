import aiohttp
import collections
import random

API_URL_BASE = 'https://api.coingecko.com/api/v3/'

CoinInfo = collections.namedtuple('CoinInfo', 'id symbol name')

class CoinGeckoAPI:
    """Simple wrapper over Coingecko's API in using async."""

    def __init__(self, api_base_url=API_URL_BASE):
        self.api_base_url = api_base_url
        self.session = aiohttp.ClientSession(raise_for_status=True)
        # str (coin id) -> CoinInfo
        self.coins = dict()
        # str (symbol) -> set[coin_id]
        self.symbol_map = collections.defaultdict(set)
        # str (symbol) -> coin_id
        self.preferred_ids = dict()

    def get_symbols(self):
        return list(self.symbol_map.keys())

    def get_ids(self):
        return list(self.coins.keys())

    async def __request(self, url, params=None):
        if not params:
            params = dict()

        async with self.session.get(url, params=params) as r:
            if r.status == 200:
                return await r.json()

        return None

    async def ping(self):
        api_url = '{0}ping'.format(self.api_base_url)
        return await self.__request(api_url)

    async def prices(self, ids, **kwargs):
        api_url = '{0}simple/price'.format(self.api_base_url)
        kwargs['ids'] = ','.join([id.lower() for id in ids])
        kwargs['vs_currencies'] = 'usd'
        prices = await self.__request(api_url, params=kwargs)
        return {id: value['usd'] for id, value in prices.items()}

    async def coins_list(self):
        api_url = '{0}coins/list'.format(self.api_base_url)
        return await self.__request(api_url)

    async def coins_markets(self, **kwargs):
        api_url = '{0}coins/markets'.format(self.api_base_url)
        kwargs['vs_currency'] = 'usd'
        return await self.__request(api_url, params=kwargs)

    async def coin_by_id(self, id, **kwargs):
        api_url = '{0}coins/{1}/'.format(self.api_base_url, id.lower())
        return await self.__request(api_url, params=kwargs)

    async def coin_price_history(self, id, **kwargs):
        api_url = '{0}coins/{1}/market_chart/range'.format(self.api_base_url, id.lower())
        kwargs['vs_currency'] = 'usd'
        return await self.__request(api_url, params=kwargs)

    # Derived functions
    async def new_coins(self):
        new_coins_by_id = dict()
        new_coins = set()

        coins_list = await self.coins_list()
        for info_map in coins_list:
            id = info_map['id'].lower()
            symbol = info_map['symbol'].upper()
            name = info_map.get('name')

            if id:
                new_coins_by_id[id] = CoinInfo(id=id, symbol=symbol, name=name)
            if symbol:
                self.symbol_map[symbol].add(id)

        if self.coins:
            new_coins = set(new_coins_by_id.keys()) - set(self.coins.keys())

        self.coins = new_coins_by_id

        return new_coins

    async def random_coin(self):
        id = random.choice(list(self.coins.keys()))
        return await self.coin_by_id(id)

    def lookup(self, symbol, preferred=False):
        if symbol in self.preferred_ids:
            return self.preferred_ids.get(symbol)

        return self.symbol_map.get(symbol, set())
    
    def get_coin_info(self, id):
        return self.coins.get(id)

    def set_preferred(self, symbol, id):
        self.preferred_ids[symbol] = id.lower()