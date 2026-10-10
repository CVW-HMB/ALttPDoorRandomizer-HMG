import unittest

from CLI import parse_cli
from Main import main
from source.classes.BabelFish import BabelFish


def generate(seed, *extra):
    args = parse_cli(['--suppress_rom', '--spoiler', 'none', '--loglevel', 'warning', '--logic', 'hybridglitches', *extra])
    main(args=args, seed=seed, fish=BabelFish(lang='en'))


class TestHmgKeyPlacement(unittest.TestCase):
    # seeds 1-4 cover Swamp pot keys and Ice Palace lobby clip keylocks under hybrid glitches
    def testPotKeys(self):
        for seed in range(1, 5):
            generate(seed, '--pottery', 'keys')

    def testUnderworldDrops(self):
        for seed in range(1, 5):
            generate(seed, '--pottery', 'lottery', '--dropshuffle', 'underworld')

    def testPotKeysAndDropKeys(self):
        for seed in range(1, 5):
            generate(seed, '--pottery', 'keys', '--dropshuffle', 'keys')


if __name__ == '__main__':
    unittest.main()
