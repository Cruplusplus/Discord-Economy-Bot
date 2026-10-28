import asyncio
import os
import shutil
import tempfile
import time
import unittest

from economy.config import (
    LOTTERY_TICKET_PRICE,
    LOTTERY_MAX_TICKETS_PER_USER,
    LOTTERY_BASE_JACKPOT,
    COFFEE_WORK_COOLDOWN,
    COFFEE_DURATION_SECONDS,
    KUDZU_DURATION_SECONDS,
    KUDZU_DROP_BONUS_PERCENT,
    LOCKPICK_FAIL_THRESHOLD,
    ROB_FAIL_THRESHOLD,
    PRISON_DURATION,
    ITEM_PRICE_COFFEE,
    ITEM_PRICE_STONE_CHARM,
    ITEM_PRICE_LOCKPICK,
    ITEM_PRICE_BAIL_BOND,
    ITEM_PRICE_PARADOX_CHRONO,
    PARADOX_REWIND_WINDOW_SECONDS,
)
from economy.database import DataManager
from economy.shop import (
    CATALOG,
    get_item,
    get_user_inventory,
    get_user_buffs,
)
from economy.lottery import LotteryManager


class DummyCog:
    def __init__(self, db: DataManager):
        self.db = db


class TestShopAndLottery(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_file = os.path.join(self.test_dir, "test_stats.json")
        self.db = DataManager(self.db_file)
        self.cog = DummyCog(self.db)
        self.lottery = LotteryManager(self.cog)
        self.cog.lottery = self.lottery

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_database_initialization(self):
        user = self.db.get_user_data(12345)
        self.assertIn("inventory", user)
        self.assertIn("buffs", user)
        self.assertIsInstance(user["inventory"], dict)
        self.assertIsInstance(user["buffs"], dict)

        lottery_data = self.db.get_lottery_data()
        self.assertEqual(lottery_data["jackpot"], LOTTERY_BASE_JACKPOT)
        self.assertEqual(lottery_data["tickets"], {})

    def test_shop_catalog_and_aliases(self):
        self.assertIn("carlos_coffee", CATALOG)
        self.assertIn("stone_charm", CATALOG)
        self.assertIn("lockpick", CATALOG)
        self.assertIn("bail_bond", CATALOG)
        self.assertIn("kudzu_seeds", CATALOG)
        self.assertIn("megaphone", CATALOG)

        self.assertEqual(get_item("cafe").item_id, "carlos_coffee")
        self.assertEqual(get_item("piedra").item_id, "stone_charm")
        self.assertEqual(get_item("amuleto").item_id, "stone_charm")
        self.assertEqual(get_item("ganzua").item_id, "lockpick")
        self.assertEqual(get_item("fianza").item_id, "bail_bond")
        self.assertEqual(get_item("kudzu").item_id, "kudzu_seeds")
        self.assertEqual(get_item("megafono").item_id, "megaphone")
        self.assertIsNone(get_item("item_inexistente"))

    def test_item_purchase_and_stack_limits(self):
        user = self.db.get_user_data(100)
        user["wallet"] = 50000

        item = get_item("stone_charm")
        self.assertIsNotNone(item)
        self.assertEqual(item.price, ITEM_PRICE_STONE_CHARM)

        inv = get_user_inventory(user)
        self.assertEqual(inv.get("stone_charm", 0), 0)

        # Simular compra de 1 amuleto
        cost = item.price * 1
        user["wallet"] -= cost
        inv[item.item_id] = inv.get(item.item_id, 0) + 1
        self.assertEqual(user["wallet"], 50000 - 20000)
        self.assertEqual(inv["stone_charm"], 1)

        # Límite máximo de stack (max_stack = 5 para stone_charm)
        inv[item.item_id] = 5
        self.assertEqual(inv["stone_charm"], item.max_stack)
        self.assertTrue(inv["stone_charm"] + 1 > item.max_stack)

    def test_carlos_coffee_buff_and_cooldown(self):
        user = self.db.get_user_data(200)
        inv = get_user_inventory(user)
        buffs = get_user_buffs(user)

        inv["carlos_coffee"] = 2
        now = time.time()

        # Activar café
        inv["carlos_coffee"] -= 1
        buffs["coffee_until"] = now + COFFEE_DURATION_SECONDS

        self.assertEqual(inv["carlos_coffee"], 1)
        self.assertGreater(buffs["coffee_until"], now)

        # Verificar cooldown efectivo
        is_coffee = buffs.get("coffee_until", 0.0) > now
        effective_cd = COFFEE_WORK_COOLDOWN if is_coffee else 300
        self.assertEqual(effective_cd, 15)

    def test_kudzu_seeds_drop_bonus(self):
        user = self.db.get_user_data(300)
        buffs = get_user_buffs(user)
        now = time.time()

        buffs["kudzu_until"] = now + KUDZU_DURATION_SECONDS
        base_drop = 1000

        bonus = 0
        if buffs.get("kudzu_until", 0.0) > now:
            bonus = int(round(base_drop * KUDZU_DROP_BONUS_PERCENT))

        self.assertEqual(bonus, 500)
        self.assertEqual(base_drop + bonus, 1500)

    def test_stone_charm_defense_in_rob(self):
        robber = self.db.get_user_data(400)
        victim = self.db.get_user_data(500)

        robber["wallet"] = 10000
        victim["wallet"] = 50000
        victim_inv = get_user_inventory(victim)
        victim_inv["stone_charm"] = 1

        now = time.time()

        # Al robar, el amuleto de la victima se consume y el ladron va a carcel
        if victim_inv.get("stone_charm", 0) > 0:
            victim_inv["stone_charm"] -= 1
            robber["prison_until"] = now + PRISON_DURATION
            multa = min(robber["wallet"], 3000)
            robber["wallet"] -= multa

        self.assertEqual(victim_inv["stone_charm"], 0)
        self.assertEqual(victim["wallet"], 50000)  # No perdio dinero
        self.assertEqual(robber["wallet"], 7000)   # Pago multa
        self.assertGreater(robber["prison_until"], now)

    def test_bail_bond_auto_freedom(self):
        robber = self.db.get_user_data(600)
        robber_inv = get_user_inventory(robber)
        robber_inv["bail_bond"] = 1

        now = time.time()
        # Ladron cae preso
        robber["prison_until"] = now + PRISON_DURATION

        # Pero fianza policial se activa
        if robber_inv.get("bail_bond", 0) > 0:
            robber_inv["bail_bond"] -= 1
            robber["prison_until"] = 0.0

        self.assertEqual(robber_inv["bail_bond"], 0)
        self.assertEqual(robber["prison_until"], 0.0)  # Libre al instante

    def test_lockpick_threshold_reduction(self):
        robber = self.db.get_user_data(700)
        robber_inv = get_user_inventory(robber)
        robber_inv["lockpick"] = 1

        if robber_inv.get("lockpick", 0) > 0:
            robber_inv["lockpick"] -= 1
            threshold = LOCKPICK_FAIL_THRESHOLD
        else:
            threshold = ROB_FAIL_THRESHOLD

        self.assertEqual(threshold, 8)
        self.assertEqual(robber_inv["lockpick"], 0)

    def test_stone_charm_in_robin_hood(self):
        magnate = self.db.get_user_data(800)
        magnate["wallet"] = 100000
        magnate_inv = get_user_inventory(magnate)
        magnate_inv["stone_charm"] = 1

        stolen = 20000  # 20%
        if magnate_inv.get("stone_charm", 0) > 0:
            magnate_inv["stone_charm"] -= 1
            stolen = int(round(stolen * 0.5))

        self.assertEqual(stolen, 10000)  # Absorbió 50%
        self.assertEqual(magnate_inv["stone_charm"], 0)

    def test_lottery_buy_tickets_and_cap(self):
        async def run_test():
            user = self.db.get_user_data(900)
            user["wallet"] = 100000

            half_tix = max(1, LOTTERY_MAX_TICKETS_PER_USER // 2)
            ok, msg, user_tix, pot = await self.lottery.buy_tickets(900, half_tix)
            self.assertTrue(ok)
            self.assertEqual(user_tix, half_tix)
            self.assertEqual(user["wallet"], 100000 - (half_tix * LOTTERY_TICKET_PRICE))
            self.assertEqual(pot, LOTTERY_BASE_JACKPOT + (half_tix * LOTTERY_TICKET_PRICE))

            # Intenta comprar más de los permitidos por el tope anti-monopolio
            ok, msg, user_tix, pot = await self.lottery.buy_tickets(900, LOTTERY_MAX_TICKETS_PER_USER + 1)
            self.assertFalse(ok)
            self.assertIn("anti-monopolio", msg.lower())

            # Compra los restantes para alcanzar el límite exacto
            remaining = LOTTERY_MAX_TICKETS_PER_USER - half_tix
            ok, msg, user_tix, pot = await self.lottery.buy_tickets(900, remaining)
            self.assertTrue(ok)
            self.assertEqual(user_tix, LOTTERY_MAX_TICKETS_PER_USER)

            # Intenta comprar 1 más teniendo el tope
            ok, msg, user_tix, pot = await self.lottery.buy_tickets(900, 1)
            self.assertFalse(ok)

        asyncio.run(run_test())

    def test_lottery_draw_and_payout(self):
        async def run_test():
            user1 = self.db.get_user_data(1001)
            user2 = self.db.get_user_data(1002)
            user1["wallet"] = 20000
            user2["wallet"] = 20000

            await self.lottery.buy_tickets(1001, 3)
            await self.lottery.buy_tickets(1002, 2)

            pot_before = self.lottery.get_lottery_data()["jackpot"]
            self.assertEqual(pot_before, LOTTERY_BASE_JACKPOT + (5 * LOTTERY_TICKET_PRICE))

            won, winner_member, jackpot_won, total_tix = await self.lottery.draw_lottery(guild=None)
            self.assertTrue(won)
            self.assertEqual(total_tix, 5)
            self.assertEqual(jackpot_won, pot_before)

            # Verificar que el pozo se reseteo al fondo base
            lottery_after = self.lottery.get_lottery_data()
            self.assertEqual(lottery_after["jackpot"], LOTTERY_BASE_JACKPOT)
            self.assertEqual(lottery_after["tickets"], {})
            self.assertIsNotNone(lottery_after["last_winner"])

            # Uno de los dos gano
            u1_wallet = self.db.get_user_data(1001)["wallet"]
            u2_wallet = self.db.get_user_data(1002)["wallet"]
            winner_id = lottery_after["last_winner"]["user_id"]
            if winner_id == 1001:
                self.assertEqual(u1_wallet, (20000 - 3 * LOTTERY_TICKET_PRICE) + jackpot_won)
            else:
                self.assertEqual(u2_wallet, (20000 - 2 * LOTTERY_TICKET_PRICE) + jackpot_won)

        asyncio.run(run_test())


    def test_paradox_chrono_catalog_and_aliases(self):
        item = get_item("paradox_chrono")
        self.assertIsNotNone(item)
        self.assertEqual(item.price, ITEM_PRICE_PARADOX_CHRONO)
        self.assertEqual(item.max_stack, 2)
        self.assertTrue(item.usable)

        # Aliases
        self.assertEqual(get_item("paradox").item_id, "paradox_chrono")
        self.assertEqual(get_item("bucle").item_id, "paradox_chrono")
        self.assertEqual(get_item("cronometro").item_id, "paradox_chrono")
        self.assertEqual(get_item("reloj").item_id, "paradox_chrono")
        self.assertEqual(get_item("rewind").item_id, "paradox_chrono")
        self.assertEqual(get_item("rebobinar").item_id, "paradox_chrono")

    def test_paradox_chrono_rewind_logic(self):
        from economy.cog import Economy

        # Crear un cog simulado con base de datos real
        class MockBot:
            pass

        cog = Economy(MockBot())
        cog.db = self.db

        async def run_rewind_tests():
            user = self.db.get_user_data(2001)
            user["wallet"] = 100000
            inv = get_user_inventory(user)
            inv["paradox_chrono"] = 1

            # Simular pérdida de 50,000 en coin flip
            user["wallet"] -= 50000
            user["stats"]["gambles_lost"] = 1
            now = time.time()
            user["last_loss"] = {
                "amount": 50000,
                "game": "Cara o Cruz (CRUZ)",
                "timestamp": now,
                "reverted": False,
            }

            # 1. Rebobinar con éxito dentro de la ventana de 120s
            ok, res = await cog.execute_temporal_rewind(2001)
            self.assertTrue(ok)
            self.assertEqual(res["amount"], 50000)
            self.assertEqual(res["wallet"], 100000)
            self.assertEqual(inv["paradox_chrono"], 0)
            self.assertTrue(user["last_loss"]["reverted"])
            self.assertEqual(user["stats"]["gambles_lost"], 0)

            # 2. Intento de re-rebobinar la misma tirada (debe fallar)
            inv["paradox_chrono"] = 1
            ok, err = await cog.execute_temporal_rewind(2001)
            self.assertFalse(ok)
            self.assertIn("ya fue rebobinada", err)

            # 3. Intento de rebobinar con tiempo expirado (>120s)
            user["last_loss"] = {
                "amount": 30000,
                "game": "Ruleta (ROJO)",
                "timestamp": now - 300,  # 5 minutos atras
                "reverted": False,
            }
            ok, err = await cog.execute_temporal_rewind(2001)
            self.assertFalse(ok)
            self.assertIn("se enfrió", err)

            # 4. Intento sin tener el ítem en la mochila
            inv["paradox_chrono"] = 0
            user["last_loss"]["timestamp"] = time.time()
            ok, err = await cog.execute_temporal_rewind(2001)
            self.assertFalse(ok)
            self.assertIn("No tienes ningún", err)

        asyncio.run(run_rewind_tests())

    def test_coin_and_ruleta_commands_execution(self):
        from economy.cog import Economy
        from unittest.mock import AsyncMock, MagicMock

        class MockBot:
            pass

        cog = Economy(MockBot())
        cog.db = self.db

        async def run_game_tests():
            # Setup user
            user_id = 3001
            user = self.db.get_user_data(user_id)
            user["wallet"] = 10000
            inv = get_user_inventory(user)
            inv["paradox_chrono"] = 1

            # Mock Context
            ctx = MagicMock()
            ctx.author.id = user_id
            ctx.prefix = "%"
            ctx.guild = None
            ctx.reply = AsyncMock()

            # Test 1: coin with 'x' (cruz) and 'all'
            await cog.coin.callback(cog, ctx, "x", "all")
            ctx.reply.assert_called()

            # Test 2: ruleta with 'r' (rojo) and 'all'
            user["wallet"] = 10000  # replenish
            ctx.reply.reset_mock()
            await cog.ruleta.callback(cog, ctx, "r", "all")
            ctx.reply.assert_called()

        asyncio.run(run_game_tests())

    def test_get_all_users_and_rank_with_metadata(self):
        from economy.cog import Economy
        from unittest.mock import AsyncMock, MagicMock

        # Insert user accounts and metadata key like _lottery
        u1 = self.db.get_user_data(4001)
        u1["wallet"] = 25000
        u2 = self.db.get_user_data(4002)
        u2["wallet"] = 15000
        lottery = self.db.get_lottery_data()
        lottery["jackpot"] = 75000

        # Verify get_all_users filters out _lottery
        all_users = self.db.get_all_users()
        self.assertNotIn("_lottery", all_users)
        self.assertIn("4001", all_users)
        self.assertIn("4002", all_users)
        for k in all_users.keys():
            self.assertTrue(k.isdigit())

        # Test rank command directly
        class MockBot:
            pass

        cog = Economy(MockBot())
        cog.db = self.db

        async def run_rank():
            ctx = MagicMock()
            ctx.author.id = 4001
            ctx.guild = None
            ctx.reply = AsyncMock()

            # Calling rank must not raise ValueError
            await cog.rank.callback(cog, ctx)
            ctx.reply.assert_called()

        asyncio.run(run_rank())

if __name__ == "__main__":
    unittest.main()
