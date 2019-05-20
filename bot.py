import argparse
import os
from multiprocessing.pool import ThreadPool
from shutil import copyfile, move

from src.costants import SCREENSHOT, INPUT_SENTENCE
from src.image_to_text import img_to_text
from src.switch import Switch
from src.utlity import files, timeit


def do_screenshot():
    return os.system("adb exec-out screencap -p > " + SCREENSHOT)


@timeit
def do_question(pool: ThreadPool, file: str = SCREENSHOT, debug: bool = False):
    instance = img_to_text(file, pool, debug)
    print(instance.question)
    switch = Switch(pool)
    switch.run(instance)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run a bootstrap node')
    sp = parser.add_mutually_exclusive_group()
    sp.add_argument('--live', help='Live game', action='store_true')
    sp.add_argument('--test', help='Test screens', action='store_true')
    sp.add_argument('--dump', help='Dump screens', action='store_true')
    sp.add_argument('--feature', help='Test single screen', action='store_true')
    sp.add_argument('--test-id', help='Test single question', type=int)
    args = parser.parse_args()

    pool = ThreadPool(3)

    try:
        if args.live:
            while True:
                key = input(INPUT_SENTENCE)
                if not key:
                    screen = do_screenshot()
                    if screen == 0:
                        do_question(pool)
                if key == 'q':
                    pool.close()
                    pool.join()
        if args.feature:
            for index, file in enumerate(files('feature')):
                if file.split('.')[1] == 'jpg' or file.split('.')[1] == 'png':
                    do_question(pool, file, debug=False)
                    key = input()
                    if key == 'y':
                        move(file, 'screenshot/' + file.split('/')[1])
    except KeyboardInterrupt as _:
        pool.close()
        pool.join()
        exit(0)
