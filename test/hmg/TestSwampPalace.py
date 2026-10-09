from Items import ItemFactory
from test.TestBase import TestBase, build_vanilla_world


class TestSwampPalace(TestBase):
    def setUp(self):
        self.world = build_vanilla_world(mode='open', logic='hybridglitches')
        self.world.precollected_items.clear()
        self.world.itempool.append(ItemFactory('Pegasus Boots', 1))

    def testBigChestWithoutSwampBigKey(self):
        # Ether is the Mire medallion in the test world; without it the Mire state routes are closed
        self.run_location_tests([
            ["Swamp Palace - Big Chest", True, [], ['Big Key (Swamp Palace)']],
            ["Swamp Palace - Big Chest", True, [], ['Big Key (Swamp Palace)', 'Ether']],
            ["Swamp Palace - Big Chest", False, [], ['Big Key (Swamp Palace)', 'Ether', 'Big Key (Tower of Hera)']],
            ["Swamp Palace - Big Chest", False, [], ['Big Key (Swamp Palace)', 'Ether', 'Flippers']],
        ])
