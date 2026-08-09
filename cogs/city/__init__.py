# -*- coding: utf-8 -*-
from .cog import CareerCity

async def setup(bot):
    await bot.add_cog(CareerCity(bot))
